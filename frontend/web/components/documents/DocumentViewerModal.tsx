'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Loader2, FileText, Copy, Check, BookOpen, Layers } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import Mark from 'mark.js';
import { useUIStore } from '@/store/ui-store';
import { documentService } from '@/services/document.service';
import type { ChunkRef } from '@/types';

/**
 * Strip Hugo shortcodes and HTML comments from markdown content
 * so react-markdown can render it cleanly.
 */
function cleanMarkdown(raw: string): string {
  if (!raw) return '';

  let text = raw;

  // Remove HTML comments: <!-- ... -->
  text = text.replace(/<!--[\s\S]*?-->/g, '');

  // Remove Hugo block shortcodes: {{% ... %}} ... {{% /... %}}
  text = text.replace(/\{\{%\s*\/?\w+[\s\S]*?%\}\}/g, '');

  // Remove Hugo inline shortcodes: {{< ... >}} ... {{< /... >}}
  text = text.replace(/\{\{<\s*\/?[\s\S]*?>\}\}/g, '');

  // Remove standalone {{% %}} and {{< >}} that may span multiple lines
  text = text.replace(/\{\{[%<][\s\S]*?[%>]\}\}/g, '');

  // Remove frontmatter if present (--- ... ---)
  if (text.startsWith('---')) {
    const end = text.indexOf('---', 3);
    if (end !== -1) {
      text = text.slice(end + 3).trim();
    }
  }

  // Clean <details markdown="1"> → <details> (strip non-standard attributes)
  text = text.replace(/<details[^>]*>/gi, '<details>');

  // Match ingestion standardizer: collapse tabs/multiple spaces to single space
  text = text.replace(/[ \t]+/g, ' ');

  // Match ingestion standardizer: collapse 3+ newlines to exactly 2
  text = text.replace(/\n{3,}/g, '\n\n');

  return text.trim();
}

/**
 * Strip Markdown formatting to get pure text for search matching.
 */
function stripMarkdownForSearch(raw: string): string {
  if (!raw) return '';
  let text = raw;

  // Remove HTML comments
  text = text.replace(/<!--[\s\S]*?-->/g, '');

  // Remove Hugo shortcodes
  text = text.replace(/\{\{%\s*\/?\w+[\s\S]*?%\}\}/g, '');
  text = text.replace(/\{\{<\s*\/?[\s\S]*?>\}\}/g, '');
  text = text.replace(/\{\{[%<][\s\S]*?[%>]\}\}/g, '');

  // Strip ALL HTML tags: <details>, <summary>, <div>, etc.
  text = text.replace(/<[^>]+>/g, '');

  // Strip bold/italic wrappers
  text = text.replace(/[\*_]{1,3}(.*?)[\*_]{1,3}/g, '$1');

  // Strip links: [text](url) -> text
  text = text.replace(/\[(.*?)\]\(.*?\)/g, '$1');

  // Strip headers: # Header -> Header
  text = text.replace(/^#+\s+/gm, '');

  // Strip list bullet/number prefixes at start of lines: * item or 1. item -> item
  text = text.replace(/^[\s]*[\*\-]\s+/gm, '');
  text = text.replace(/^[\s]*\d+\.\s+/gm, '');

  // Strip blockquote prefixes
  text = text.replace(/^>\s+/gm, '');

  // Normalize whitespace: replace multiple spaces/newlines with a single space
  text = text.replace(/\s+/g, ' ').trim();

  return text;
}

interface MinimapPosition {
  percent: number;
  label: string;
  index: number;
}

export function DocumentViewerModal() {
  const { activeDocumentViewer, closeDocumentViewer } = useUIStore();
  const { isOpen, documentId, documentName, highlights, chunks } = activeDocumentViewer;

  const [cleanedContent, setCleanedContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [marksApplied, setMarksApplied] = useState(false);
  const [minimapPositions, setMinimapPositions] = useState<MinimapPosition[]>([]);

  const hasFullText = cleanedContent.trim().length > 0;

  const contentRef = useRef<HTMLDivElement>(null);
  const markdownRef = useRef<HTMLDivElement>(null);

  // Fetch content
  useEffect(() => {
    if (!isOpen || !documentId) return;

    let cancelled = false;
    const fetchContent = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const text = await documentService.getDocumentContent(documentId);
        if (!cancelled) {
          setCleanedContent(cleanMarkdown(text));
        }
      } catch {
        if (!cancelled) {
          setCleanedContent('');
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchContent();
    return () => { cancelled = true; };
  }, [isOpen, documentId]);

  // Apply mark.js highlights after markdown renders
  // Uses character offsets when available, falls back to text matching
  useEffect(() => {
    if (!markdownRef.current || !cleanedContent) return;

    setMarksApplied(false);
    const markInstance = new Mark(markdownRef.current);
    markInstance.unmark();

    // Determine search strings: prefer offset-based extraction, fallback to fullContent
    const searchStrings: string[] = [];
    const hasOffsets = chunks && chunks.length > 0 && chunks.some((c: ChunkRef) => c.startCharIndex != null && c.endCharIndex != null);

    if (hasOffsets && chunks) {
      // Use character offsets to extract exact text from cleanedContent
      chunks.forEach((chunk: ChunkRef) => {
        if (chunk.startCharIndex != null && chunk.endCharIndex != null) {
          const start = Math.min(chunk.startCharIndex, cleanedContent.length);
          const end = Math.min(chunk.endCharIndex, cleanedContent.length);
          if (start < end) {
            searchStrings.push(cleanedContent.substring(start, end));
          }
        } else if (chunk.fullContent) {
          // Fallback for chunks without offsets
          searchStrings.push(chunk.fullContent);
        }
      });
    } else if (chunks && chunks.length > 0) {
      // No offsets available, use fullContent
      searchStrings.push(...chunks.map((c: ChunkRef) => c.fullContent));
    } else if (highlights) {
      // Legacy highlights fallback
      searchStrings.push(...highlights);
    }

    if (searchStrings.length === 0) {
      setMarksApplied(true);
      return;
    }

    let completedCount = 0;
    const totalChunks = searchStrings.length;

    searchStrings.forEach((chunkText, index) => {
      // Split chunk into sentences for more granular matching
      const sentences = chunkText
        .split(/[.\n]+/)
        .map(s => stripMarkdownForSearch(s).trim())
        .filter(s => s.length >= 15 && s.length <= 150);

      if (sentences.length === 0) {
        completedCount++;
        if (completedCount === totalChunks) {
          setMarksApplied(true);
        }
        return;
      }

      let matchedSentences = 0;
      sentences.forEach((sentence) => {
        markInstance.mark(sentence, {
          className: 'chunk-highlight',
          accuracy: 'exactly',
          separateWordSearch: false,
          acrossElements: false,
          element: 'mark',
          each: (element: HTMLElement) => {
            element.setAttribute('data-highlight-index', String(index));
          },
          done: () => {
            matchedSentences++;
            if (matchedSentences === sentences.length) {
              completedCount++;
              if (completedCount === totalChunks) {
                setMarksApplied(true);
              }
            }
          },
        });
      });
    });

    return () => {
      markInstance.unmark();
    };
  }, [cleanedContent, chunks, highlights]);

  // Compute minimap positions after marks are applied
  useEffect(() => {
    if (!marksApplied || !markdownRef.current || !hasFullText) return;

    const container = markdownRef.current;
    const marks = container.querySelectorAll('mark.chunk-highlight');
    if (marks.length === 0) {
      setMinimapPositions([]);
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const positions: MinimapPosition[] = [];
    const seen = new Set<number>();

    marks.forEach((mark) => {
      const idx = parseInt(mark.getAttribute('data-highlight-index') || '0', 10);
      if (seen.has(idx)) return;
      seen.add(idx);

      const rect = mark.getBoundingClientRect();
      const top = rect.top - containerRect.top + container.scrollTop;
      const percent = container.scrollHeight > 0 ? (top / container.scrollHeight) * 100 : 0;

      const chunkText = (chunks && chunks.length > 0)
        ? chunks[idx]?.fullContent ?? highlights[idx] ?? ''
        : highlights[idx] ?? '';

      positions.push({
        percent: Math.max(4, Math.min(96, percent)),
        label: chunkText.slice(0, 60) + (chunkText.length > 60 ? '\u2026' : ''),
        index: idx,
      });
    });

    setMinimapPositions(positions);
  }, [marksApplied, chunks, highlights, hasFullText]);

  // Scroll to a specific highlight
  const scrollToHighlight = useCallback((index: number) => {
    if (!markdownRef.current) return;
    const marks = markdownRef.current.querySelectorAll('mark.chunk-highlight');
    const el = marks[index] as HTMLElement;
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  // Escape key to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDocumentViewer();
    };
    if (isOpen) window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, closeDocumentViewer]);

  if (!isOpen) return null;

  const handleCopyChunk = async (text: string, idx: number) => {
    await navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const chunkCount = chunks?.length || highlights.length;

  // ── Render markdown content ──
  const renderMarkdownContent = () => (
    <div
      ref={markdownRef}
      className="doc-viewer-content prose prose-sm max-w-none dark:prose-invert"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
        {cleanedContent}
      </ReactMarkdown>
    </div>
  );

  // ── Chunks-only fallback ──
  const renderChunksView = () => {
    const chunkData = chunks && chunks.length > 0
      ? chunks
      : highlights.map((excerpt, i) => ({
          chunkId: `chunk-${i}`,
          excerpt,
          fullContent: excerpt,
          sectionTitle: '',
          similarityScore: 0,
        }));

    if (chunkData.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-3">
          <BookOpen size={32} className="opacity-40" />
          <p className="text-sm">Không có nội dung để hiển thị.</p>
        </div>
      );
    }

    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 mb-5 px-1">
          <Layers size={14} className="text-primary" />
          <p className="text-xs text-muted-foreground">
            Hiển thị <span className="font-medium text-foreground">{chunkData.length}</span> đoạn
            trích từ tài liệu này được sử dụng để tạo câu trả lời.
          </p>
        </div>

        {chunkData.map((chunk, idx) => {
          const fullText = `${chunk.sectionTitle ? chunk.sectionTitle + '\n' : ''}${chunk.fullContent || chunk.excerpt}`;

          return (
            <div
              key={chunk.chunkId}
              className="
                group relative
                rounded-xl border border-border/50
                bg-gradient-to-br from-muted/30 to-transparent
                hover:border-primary/30 hover:shadow-sm
                transition-all duration-200
                overflow-hidden
              "
            >
              <div className="absolute top-0 left-0 w-1 h-full bg-primary/20 group-hover:bg-primary/50 transition-colors" />

              <div className="pl-4 pr-3 py-3">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-bold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    {chunk.sectionTitle ? (
                      <p className="text-xs font-semibold text-primary/90 truncate">
                        {chunk.sectionTitle}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground/60 italic">
                        Đoạn trích #{idx + 1}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {chunk.similarityScore > 0 && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                        {(chunk.similarityScore * 100).toFixed(0)}%
                      </span>
                    )}
                    <button
                      onClick={() => handleCopyChunk(fullText, idx)}
                      className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent opacity-0 group-hover:opacity-100 transition-all duration-150"
                      title="Sao chép"
                    >
                      {copiedIdx === idx ? (
                        <Check size={12} className="text-green-600" />
                      ) : (
                        <Copy size={12} />
                      )}
                    </button>
                  </div>
                </div>

                <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap pl-7">
                  {chunk.fullContent || chunk.excerpt}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-[95vw] max-w-6xl h-[90vh] bg-background rounded-2xl border border-border shadow-2xl flex flex-col overflow-hidden">
        {/* Title bar */}
        <div className="flex items-center gap-3 px-6 py-3 border-b border-border bg-muted/30 flex-shrink-0">
          <FileText size={18} className="text-primary" />
          <h2 className="text-sm font-semibold text-foreground truncate flex-1">
            {documentName}
          </h2>
          {chunkCount > 0 && (
            <span className="text-xs text-muted-foreground">
              {chunkCount} chunk{chunkCount !== 1 ? 's' : ''} tham chiếu
              {!hasFullText && ' · Chế độ đoạn trích'}
            </span>
          )}
          <button
            onClick={closeDocumentViewer}
            className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Đóng"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Content area */}
          <div
            ref={contentRef}
            className="flex-1 overflow-y-auto px-8 py-6"
            style={{ width: minimapPositions.length > 0 ? '92%' : '100%' }}
          >
            {isLoading && (
              <div className="flex items-center justify-center h-64">
                <Loader2 size={24} className="animate-spin text-primary" />
                <span className="ml-3 text-muted-foreground text-sm">Đang tải nội dung...</span>
              </div>
            )}
            {error && (
              <div className="flex items-center justify-center h-64 text-sm text-red-500">
                {error}
              </div>
            )}
            {!isLoading && !error && hasFullText && renderMarkdownContent()}
            {!isLoading && !error && !hasFullText && renderChunksView()}
          </div>

          {/* Minimap */}
          {minimapPositions.length > 0 && (
            <div
              className="flex-shrink-0 border-l border-border bg-muted/10 flex flex-col items-center py-4 relative"
              style={{ width: '60px' }}
            >
              <div className="absolute left-1/2 -translate-x-1/2 top-4 bottom-4 w-px bg-border" />

              {minimapPositions.map((pin) => (
                <div
                  key={pin.index}
                  className="absolute left-1/2 -translate-x-1/2 group cursor-pointer"
                  style={{ top: `${pin.percent}%` }}
                  onClick={() => scrollToHighlight(pin.index)}
                >
                  <div className="w-3 h-3 rounded-full bg-amber-400 dark:bg-amber-500 border-2 border-background shadow-sm hover:scale-125 transition-transform duration-150" />
                  <div className="absolute right-6 top-1/2 -translate-y-1/2 hidden group-hover:flex bg-popover text-popover-foreground border border-border rounded-lg shadow-lg px-3 py-2 max-w-xs whitespace-nowrap text-xs z-10">
                    <span>Chunk #{pin.index + 1}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DocumentViewerModal;

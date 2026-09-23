'use client';

import React from 'react';
import { X, ZoomIn, ZoomOut, AlertCircle, FileText, Download } from 'lucide-react';
import mammoth from 'mammoth';
import DOMPurify from 'dompurify';

interface PreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  version?: number;
  filename: string;
  fileType: string;
  getPreviewUrl: (documentId: string, version?: number) => Promise<string>;
}

export default function PreviewModal({
  isOpen,
  onClose,
  documentId,
  version,
  filename,
  fileType,
  getPreviewUrl,
}: PreviewModalProps) {
  const [state, setState] = React.useState<'idle' | 'loading' | 'preview' | 'error'>('idle');
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
  const [scale, setScale] = React.useState(100);
  const fetchControllerRef = React.useRef<AbortController | null>(null);

  const normalizedFileType = typeof fileType === 'string' ? fileType.toUpperCase() : (fileType ?? 'UNKNOWN');
  const isPdf = normalizedFileType === 'PDF';
  const isWord = ['DOCX', 'DOC'].includes(normalizedFileType);

  const cleanup = React.useCallback(() => {
    if (fetchControllerRef.current) {
      fetchControllerRef.current.abort();
      fetchControllerRef.current = null;
    }
    if (previewUrl && previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setState('idle');
    setErrorMsg(null);
  }, [previewUrl]);

  const handleClose = React.useCallback(() => {
    cleanup();
    onClose();
  }, [cleanup, onClose]);

  React.useEffect(() => {
    if (!isOpen || !documentId) return;

    cleanup();
    setState('loading');
    setErrorMsg(null);
    setScale(100);
    setPreviewUrl(null);

    const controller = new AbortController();
    fetchControllerRef.current = controller;

    // 30-second timeout
    const timeout = setTimeout(() => {
      controller.abort();
      setState('error');
      setErrorMsg('Hết thời gian tải (30s). Vui lòng thử lại.');
    }, 30_000);

    getPreviewUrl(documentId, version)
      .then((url) => {
        clearTimeout(timeout);
        setPreviewUrl(url);
        setState('preview');
      })
      .catch((err) => {
        clearTimeout(timeout);
        if ((err as Error).name === 'AbortError') {
          setState('idle');
        } else {
          setState('error');
          setErrorMsg('Không thể tải tài liệu. Vui lòng thử lại.');
        }
      });

    return () => {
      clearTimeout(timeout);
      cleanup();
    };
  }, [isOpen, documentId, getPreviewUrl]);

  const handleZoomIn = () => setScale((s) => Math.min(s + 25, 300));
  const handleZoomOut = () => setScale((s) => Math.max(s - 25, 25));

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col"
      style={{ backgroundColor: 'rgba(0,0,0,0.85)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <FileText className="w-5 h-5 text-blue-400 flex-shrink-0" />
          <span className="text-white font-medium truncate">{filename}</span>
          <span className="px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-300 flex-shrink-0">
            {fileType?.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleZoomOut}
            className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700 transition-colors"
            title="Thu nhỏ"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-sm text-gray-400 w-12 text-center">{scale}%</span>
          <button
            onClick={handleZoomIn}
            className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700 transition-colors"
            title="Phóng to"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          {/* Cancel / Close button */}
          <button
            onClick={handleClose}
            className="ml-2 px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded transition-colors flex items-center gap-1.5"
          >
            <X className="w-4 h-4" />
            Đóng
          </button>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-hidden relative">
        {/* Loading state */}
        {state === 'loading' && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-400 text-lg">Đang tải tài liệu...</p>
            <p className="text-gray-600 text-sm">Vui lòng đợi trong giây lát</p>
            <button
              onClick={handleClose}
              className="mt-4 px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
            >
              Hủy
            </button>
          </div>
        )}

        {/* Error state */}
        {state === 'error' && (
          <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
            <AlertCircle className="w-16 h-16 text-red-500" />
            <p className="text-red-400 text-lg text-center">{errorMsg || 'Không thể tải tài liệu xem trước'}</p>
            <div className="flex items-center gap-3 mt-2">
              <button
                onClick={() => {
                  // Re-trigger load
                  setState('loading');
                  setErrorMsg(null);
                  const controller = new AbortController();
                  fetchControllerRef.current = controller;
                  const timeout = setTimeout(() => {
                    controller.abort();
                    setState('error');
                    setErrorMsg('Hết thời gian tải (30s). Vui lòng thử lại.');
                  }, 30_000);
                  getPreviewUrl(documentId, version)
                    .then((url) => {
                      clearTimeout(timeout);
                      setPreviewUrl(url);
                      setState('preview');
                    })
                    .catch((err) => {
                      clearTimeout(timeout);
                      setState('error');
                      setErrorMsg('Không thể tải tài liệu. Vui lòng thử lại.');
                    });
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
              >
                Thử lại
              </button>
              <button
                onClick={handleClose}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        )}

        {/* Preview content */}
        {state === 'preview' && previewUrl && (
          <>
            {/* PDF: Use iframe with blob URL */}
            {isPdf && (
              <iframe
                src={previewUrl}
                className="w-full h-full border-0 bg-white"
                title={`Xem trước: ${filename}`}
              />
            )}

            {/* DOCX/DOC: Use mammoth to render as HTML */}
            {isWord && <DocxPreview url={previewUrl} />}

            {/* Fallback for unsupported types */}
            {!isPdf && !isWord && (
              <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
                <FileText className="w-16 h-16 text-gray-500" />
                <p className="text-gray-400 text-lg">Định dạng {fileType} không hỗ trợ xem trước</p>
                <a
                  href={previewUrl}
                  download={filename}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Tải xuống để xem
                </a>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-900 border-t border-gray-700 text-center text-xs text-gray-500 flex-shrink-0">
        {state === 'preview' && (
          isPdf ? 'Sử dụng thanh cuộn để di chuyển | PDF' :
          isWord ? 'Tài liệu DOCX/DOC được hiển thị dưới dạng văn bản' :
          'Nhấn Đóng để thoát'
        )}
        {state === 'loading' && 'Đang tải... nhấn Hủy hoặc Đóng để thoát'}
      </div>
    </div>
  );
}

/** Inner component: mammoth renders DOCX to HTML */
function DocxPreview({ url }: { url: string }) {
  const [html, setHtml] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!url) return;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch document');
        return res.arrayBuffer();
      })
      .then((arrayBuffer) =>
        mammoth.convertToHtml(
          { arrayBuffer },
          {
            styleMap: [
              "p[style-name='Heading 1'] => h1:fresh",
              "p[style-name='Heading 2'] => h2:fresh",
              "p[style-name='Heading 3'] => h3:fresh",
            ],
          }
        )
      )
      .then(({ value, messages }) => {
        setHtml(value);
        if (messages.length > 0) {
          console.warn('Mammoth conversion warnings:', messages);
        }
      })
      .catch((err) => {
        console.error('DOCX render error:', err);
        setError('Không thể hiển thị tài liệu DOCX. Vui lòng tải xuống để xem.');
      })
      .finally(() => {
        setLoading(false);
        URL.revokeObjectURL(url);
      });
  }, [url]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400">Đang chuyển đổi DOCX...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
        <AlertCircle className="w-14 h-14 text-red-500" />
        <p className="text-red-400 text-center">{error}</p>
        <a
          href={url}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
        >
          <Download className="w-4 h-4" />
          Tải xuống để xem
        </a>
      </div>
    );
  }

  if (!html) return null;

  return (
    <div
      className="w-full h-full overflow-auto bg-gray-50 p-8 flex justify-center"
    >
      <div
        className="bg-white shadow-2xl p-10 max-w-4xl w-full"
        style={{
          fontFamily: 'Georgia, "Times New Roman", serif',
          fontSize: '14px',
          lineHeight: '1.8',
          color: '#1a1a1a',
        }}
        dangerouslySetInnerHTML={{ __html: typeof window !== 'undefined' ? DOMPurify.sanitize(html) : '' }}
      />
    </div>
  );
}

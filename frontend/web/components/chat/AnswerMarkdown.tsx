'use client';

import { useMemo } from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CITE_PREFIX, citeNumber, linkCitations } from '@/lib/chat/citations';

// Markdown from the model renders without raw HTML (C8): no rehype-raw, images become links, and
// the only custom scheme is `cite:n`, produced locally by linkCitations.

export function AnswerMarkdown({
  text,
  known,
  labels,
  onCite,
}: {
  text: string;
  known: ReadonlySet<number>;
  /** Optional display label per citation number (e.g. `1 -> "1.1"`, `2 -> "1.2"`). */
  labels?: ReadonlyMap<number, string>;
  onCite: (n: number) => void;
}) {
  const source = useMemo(() => linkCitations(text, known), [text, known]);
  return (
    <div className="chat-markdown prose prose-sm max-w-none text-foreground prose-p:my-2 prose-strong:text-foreground prose-headings:text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (url.startsWith(CITE_PREFIX) ? url : defaultUrlTransform(url))}
        components={{
          a: ({ href, children }) => {
            const n = citeNumber(href);
            if (n !== null) {
              const display = labels?.get(n) ?? String(n);
              return (
                <button
                  type="button"
                  onClick={() => onCite(n)}
                  aria-label={`Source ${display}`}
                  className="ml-0.5 inline-flex min-w-5 -translate-y-0.5 cursor-pointer items-center justify-center rounded-md border border-primary/30 bg-primary-soft px-1.5 py-0.2 align-baseline font-mono text-[11px] font-bold text-primary-strong no-underline transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {display}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
          img: ({ src, alt }) =>
            typeof src === 'string' ? (
              <a href={src} target="_blank" rel="noopener noreferrer">
                {alt || 'Image (open link)'}
              </a>
            ) : null,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}

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
  onCite,
}: {
  text: string;
  known: ReadonlySet<number>;
  onCite: (n: number) => void;
}) {
  const source = useMemo(() => linkCitations(text, known), [text, known]);
  return (
    <div className="prose prose-sm max-w-none text-foreground prose-p:my-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (url.startsWith(CITE_PREFIX) ? url : defaultUrlTransform(url))}
        components={{
          a: ({ href, children }) => {
            const n = citeNumber(href);
            if (n !== null) {
              return (
                <button
                  type="button"
                  onClick={() => onCite(n)}
                  aria-label={`Source ${n}`}
                  className="mx-0.5 inline-block min-w-5 rounded-[5px] bg-primary-soft px-1.5 align-baseline text-xs font-bold text-primary-strong no-underline hover:outline hover:outline-1 hover:outline-primary focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {n}
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

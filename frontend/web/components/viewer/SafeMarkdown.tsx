'use client';

import { useMemo, type ComponentPropsWithoutRef, type ElementType } from 'react';
import ReactMarkdown, { defaultUrlTransform, type Components, type ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { overlaps, type Range16 } from '@/lib/viewer/offsets';

// Canonical Markdown of a document, rendered without raw HTML (C8, S2): no rehype-raw, so a
// `<script>` or `<img onerror>` in the text is shown as text, an image becomes a link (nothing is
// fetched), and unsafe link schemes are dropped by the default URL transform. Blocks that overlap
// the highlight range (UTF-16 offsets into the full Markdown) are marked; `baseOffset` is where
// this slice starts in the full text.

type Block = ComponentPropsWithoutRef<'p'> & ExtraProps;

type BlockTag = 'p' | 'li' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'pre' | 'td' | 'th';

// Colour plus a bar on the left (not colour alone); table cells keep the colour only.
const HIGHLIGHT = 'rounded-sm bg-warning-soft shadow-[inset_3px_0_0_var(--warning)]';
const HIGHLIGHT_CELL = 'bg-warning-soft';

function makeBlock<K extends BlockTag>(tag: K, baseOffset: number, highlight: Range16 | null): NonNullable<Components[K]> {
  const Tag: ElementType = tag;
  function MarkdownBlock({ node, children, ...rest }: Block) {
    const start = node?.position?.start.offset;
    const end = node?.position?.end.offset;
    const hit =
      highlight !== null &&
      start !== undefined &&
      end !== undefined &&
      overlaps(baseOffset + start, baseOffset + end, highlight.start, highlight.end);
    const { className, ...others } = rest;
    return (
      <Tag {...others} className={[className, hit ? (tag === 'td' || tag === 'th' ? HIGHLIGHT_CELL : HIGHLIGHT) : ''].filter(Boolean).join(' ') || undefined} data-highlight={hit ? 'true' : undefined}>
        {children}
      </Tag>
    );
  }
  // react-markdown types each tag's props separately; the block shape is the same for all of them.
  return MarkdownBlock as unknown as NonNullable<Components[K]>;
}

export function SafeMarkdown({
  text,
  baseOffset = 0,
  highlight = null,
}: {
  text: string;
  baseOffset?: number;
  highlight?: Range16 | null;
}) {
  const hlStart = highlight?.start;
  const hlEnd = highlight?.end;
  const components = useMemo<Components>(() => {
    const range = hlStart !== undefined && hlEnd !== undefined ? { start: hlStart, end: hlEnd } : null;
    return {
    // An unsafe scheme is stripped to an empty href: keep the text, drop the link.
    a: ({ href, children }) =>
      href ? (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      ) : (
        <span>{children}</span>
      ),
    img: ({ src, alt }) =>
      typeof src === 'string' ? (
        <a href={src} target="_blank" rel="noopener noreferrer">
          {alt || 'Image (open link)'}
        </a>
      ) : null,
    p: makeBlock('p', baseOffset, range),
    li: makeBlock('li', baseOffset, range),
    h1: makeBlock('h1', baseOffset, range),
    h2: makeBlock('h2', baseOffset, range),
    h3: makeBlock('h3', baseOffset, range),
    h4: makeBlock('h4', baseOffset, range),
    h5: makeBlock('h5', baseOffset, range),
    h6: makeBlock('h6', baseOffset, range),
    pre: makeBlock('pre', baseOffset, range),
    td: makeBlock('td', baseOffset, range),
    th: makeBlock('th', baseOffset, range),
    };
  }, [baseOffset, hlStart, hlEnd]);
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={defaultUrlTransform} components={components}>
      {text}
    </ReactMarkdown>
  );
}

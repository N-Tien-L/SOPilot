import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { SafeMarkdown } from './SafeMarkdown';

// S2 / C8: a hostile document renders as text and links, never as live HTML.
const FIXTURE = [
  '# Title',
  '',
  '<script>alert(1)</script>',
  '',
  '<img src="https://evil.example/x.png" onerror="alert(2)">',
  '',
  '![tracker](https://evil.example/pixel.png)',
  '',
  '[click](javascript:alert(3))',
  '',
  'Plain paragraph with <b onclick="x()">bold</b> html.',
].join('\n');

function render(text: string, highlight: { start: number; end: number } | null = null): string {
  return renderToStaticMarkup(createElement(SafeMarkdown, { text, highlight }));
}

describe('SafeMarkdown', () => {
  const html = render(FIXTURE);

  it('emits no script, image or event-handler elements', () => {
    expect(html).not.toMatch(/<script/i);
    expect(html).not.toMatch(/<img/i);
    expect(html).not.toMatch(/<b[ >]/i);
    expect(html).not.toMatch(/<[^>]*\sonerror=/i);
    expect(html).not.toMatch(/<[^>]*\sonclick=/i);
  });

  it('keeps the hostile source visible as escaped text', () => {
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  it('turns an external image into a link that is not fetched', () => {
    expect(html).toContain('<a href="https://evil.example/pixel.png"');
    expect(html).toContain('>tracker</a>');
  });

  it('drops an unsafe link scheme', () => {
    expect(html).not.toMatch(/href="javascript:/i);
    expect(html).not.toContain('href=""');
    expect(html).toContain('<span>click</span>');
  });

  it('marks only the blocks that overlap the highlight', () => {
    const text = 'first\n\nsecond\n\nthird';
    const marked = render(text, { start: 7, end: 13 });
    expect(marked.match(/data-highlight="true"/g)).toHaveLength(1);
    expect(marked).toMatch(/data-highlight="true"[^>]*>second</);
    expect(render(text)).not.toContain('data-highlight');
  });

  it('applies baseOffset: a slice rendered from the middle of the document', () => {
    // The slice starts at offset 7 of the full text, so "third" is at 15..20 there.
    const full = 'first\n\nsecond\n\nthird';
    const slice = full.slice(7);
    const html2 = renderToStaticMarkup(createElement(SafeMarkdown, { text: slice, baseOffset: 7, highlight: { start: 15, end: 20 } }));
    expect(html2).toMatch(/data-highlight="true"[^>]*>third</);
    expect(html2.match(/data-highlight="true"/g)).toHaveLength(1);
  });
});

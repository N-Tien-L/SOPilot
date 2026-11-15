'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { SafeMarkdown } from '@/components/viewer/SafeMarkdown';
import { thoughtLabel } from '@/lib/chat/labels';

// The model's reasoning as a collapsible block, like the popular chat apps: open and live while
// the model thinks, folded to "Thought for N s" once the answer starts. A click always wins over
// the automatic state. The text is rendered as Markdown without raw HTML (C8).

export function ReasoningBlock({
  text,
  durationMs,
  thinking,
}: {
  text: string;
  durationMs: number | null;
  /** True while the model is still reasoning (no answer text yet, no `reasoning_done`). */
  thinking: boolean;
}) {
  const [manual, setManual] = useState<boolean | null>(null);
  const open = manual ?? thinking;
  const panelId = useId();
  const scroller = useRef<HTMLDivElement>(null);

  // Follow the newest reasoning while it streams.
  useEffect(() => {
    if (thinking && open && scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [text, thinking, open]);

  return (
    <div className="mb-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setManual(!open)}
        className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
      >
        <ChevronRight size={14} aria-hidden className={`transition-transform motion-reduce:transition-none ${open ? 'rotate-90' : ''}`} />
        {thinking ? <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse" /> : null}
        <span>{thoughtLabel(durationMs, thinking)}</span>
      </button>
      {open ? (
        <div
          id={panelId}
          ref={scroller}
          className="prose prose-sm mt-1 max-h-64 max-w-none overflow-y-auto border-l-2 border-border pl-3 text-muted-foreground prose-p:my-1.5 prose-headings:text-muted-foreground"
        >
          {text ? <SafeMarkdown text={text} /> : <p>…</p>}
        </div>
      ) : null}
    </div>
  );
}

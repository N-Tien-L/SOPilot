'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { ShinyText } from '@/components/effects';
import { CollapsiblePanel } from '@/components/motion/Primitives';
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
    <div className="mb-3.5">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setManual(!open)}
        className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border/80 bg-muted/60 px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
      >
        <ChevronRight
          size={13}
          aria-hidden
          className={`transition-transform duration-200 motion-reduce:transition-none ${open ? 'rotate-90' : ''}`}
        />
        {thinking ? (
          <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse" />
        ) : null}
        <ShinyText active={thinking}>{thoughtLabel(durationMs, thinking)}</ShinyText>
      </button>
      <CollapsiblePanel open={open} id={panelId}>
        <div
          ref={scroller}
          className="prose prose-sm mt-2 max-h-64 max-w-none overflow-y-auto rounded-xl border border-border/70 bg-muted/40 px-3.5 py-2.5 text-xs text-muted-foreground prose-p:my-1.5 prose-headings:text-muted-foreground"
        >
          {text ? <SafeMarkdown text={text} /> : <p>…</p>}
        </div>
      </CollapsiblePanel>
    </div>
  );
}

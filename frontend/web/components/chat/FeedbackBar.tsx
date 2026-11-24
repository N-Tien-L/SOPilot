'use client';

import { useRef, useState } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
import { CollapsiblePanel } from '@/components/motion/Primitives';
import { sendFeedback } from '@/lib/api/endpoints';

/** FR-16: thumbs up or down, with an optional comment sent as a second PUT (one vote per user). */
export function FeedbackBar({ messageId }: { messageId: string }) {
  const [vote, setVote] = useState<1 | -1 | null>(null);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // The server upsert replaces the comment with every vote, so a changed vote re-sends the saved one.
  const savedComment = useRef<string | undefined>(undefined);

  async function submit(next: 1 | -1, text?: string) {
    setBusy(true);
    setError(null);
    try {
      const sent = text ?? savedComment.current;
      await sendFeedback(messageId, next, sent);
      savedComment.current = sent;
      setVote(next);
      setSaved(true);
      toast.success(text ? 'Feedback comment saved' : 'Thanks for your feedback');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 space-y-2.5 border-t border-border/70 pt-3 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center gap-1.5">
        <Button
          size="sm"
          variant={vote === 1 ? 'primaryOutline' : 'ghost'}
          aria-pressed={vote === 1}
          disabled={busy}
          icon={<ThumbsUp size={13} aria-hidden />}
          onClick={() => void submit(1)}
        >
          Helpful
        </Button>
        <Button
          size="sm"
          variant={vote === -1 ? 'dangerOutline' : 'ghost'}
          aria-pressed={vote === -1}
          disabled={busy}
          icon={<ThumbsDown size={13} aria-hidden />}
          onClick={() => void submit(-1)}
        >
          Not helpful
        </Button>
        {saved ? (
          <span role="status" className="ml-1 text-xs font-medium text-primary-strong">
            Thanks for the feedback.
          </span>
        ) : null}
      </div>

      <CollapsiblePanel open={vote !== null}>
        <form
          className="flex items-center gap-2 pt-0.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (comment.trim()) void submit(vote!, comment.trim());
          }}
        >
          <input
            aria-label="Feedback comment (optional)"
            placeholder="Add a comment (optional)…"
            maxLength={1000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="h-9 min-w-0 flex-1 rounded-xl border border-input bg-background px-3 text-xs text-foreground placeholder:text-placeholder outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
          />
          <Button size="sm" type="submit" variant="outline" disabled={busy || comment.trim().length === 0}>
            Send
          </Button>
        </form>
      </CollapsiblePanel>

      {error ? <ErrorNote error={error} /> : null}
    </div>
  );
}

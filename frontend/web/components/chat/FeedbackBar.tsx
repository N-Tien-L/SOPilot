'use client';

import { useRef, useState } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { Button } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
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
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 space-y-2 text-sm text-muted-foreground">
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant={vote === 1 ? 'primaryOutline' : 'outline'}
          aria-pressed={vote === 1}
          disabled={busy}
          icon={<ThumbsUp size={14} aria-hidden />}
          onClick={() => void submit(1)}
        >
          Helpful
        </Button>
        <Button
          size="sm"
          variant={vote === -1 ? 'primaryOutline' : 'outline'}
          aria-pressed={vote === -1}
          disabled={busy}
          icon={<ThumbsDown size={14} aria-hidden />}
          onClick={() => void submit(-1)}
        >
          Not helpful
        </Button>
        {saved ? <span role="status">Thanks for the feedback.</span> : null}
      </div>
      {vote !== null ? (
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (comment.trim()) void submit(vote, comment.trim());
          }}
        >
          <input
            aria-label="Feedback comment (optional)"
            placeholder="Add a comment (optional)"
            maxLength={1000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="min-w-0 flex-1 rounded-md border border-input bg-card px-3 py-1.5 text-sm text-foreground"
          />
          <Button size="sm" type="submit" variant="outline" disabled={busy || comment.trim().length === 0}>
            Send
          </Button>
        </form>
      ) : null}
      {error ? <ErrorNote error={error} /> : null}
    </div>
  );
}

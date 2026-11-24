'use client';

import { useQuery } from '@tanstack/react-query';
import { Switch } from '@/components/ui';
import { getRetrievalOptions } from '@/lib/api/endpoints';
import { workspaceKey } from '@/lib/query/client';
import { useSessionStore } from '@/store/session-store';

const TITLE_AVAILABLE =
  'Re-rank retrieved passages with the cross-encoder. Turn off to compare with plain hybrid retrieval.';
const HINT_NOT_CONFIGURED = 'Reranker is not configured on this server';
const HINT_FAILED = 'Rerank unavailable';

export interface RerankOptionsState {
  available: boolean;
  loading: boolean;
  failed: boolean;
}

/** Whether the service has a reranker; a failed request counts as unavailable (no error banner). */
export function useRerankOptions(): RerankOptionsState {
  const wid = useSessionStore((s) => s.workspace?.id ?? 'none');
  const options = useQuery({
    queryKey: workspaceKey(wid, 'retrieval-options'),
    queryFn: ({ signal }) => getRetrievalOptions(signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  return {
    available: options.data?.rerank.available === true,
    loading: options.isPending,
    failed: options.isError,
  };
}

/** Per-question reranker switch beside the composer; disabled with a reason when unavailable. */
export function RerankToggle({
  available,
  loading,
  failed,
  on,
  onChange,
  disabled,
}: RerankOptionsState & {
  on: boolean;
  onChange: (on: boolean) => void;
  disabled?: boolean;
}) {
  const hint = failed ? HINT_FAILED : HINT_NOT_CONFIGURED;
  return (
    <span className="inline-flex flex-wrap items-center gap-2" title={available ? TITLE_AVAILABLE : hint}>
      <Switch
        label="Rerank"
        checked={available && on}
        onCheckedChange={onChange}
        disabled={!available || disabled}
        className="gap-2 [&_label_span]:text-[11px] [&_label_span]:font-normal"
      />
      {!available && !loading ? <span>{hint}</span> : null}
    </span>
  );
}

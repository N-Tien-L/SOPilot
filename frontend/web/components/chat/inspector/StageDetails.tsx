'use client';

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  FileCode2,
  Layers,
  Lock,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { Badge } from '@/components/ui';
import type {
  ContextSourceTrace,
  PipelineTrace,
  PromptMessageTrace,
  RetrievedChunkTrace,
} from '@/lib/api/types';
import { formatMs, type AggregatedStage } from '@/lib/chat/pipeline-trace';
import type { InspectorModalTarget } from './InspectorDetailModal';

function asRec(val: unknown): Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val) ? (val as Record<string, unknown>) : {};
}

function asStr(val: unknown): string | null {
  return typeof val === 'string' && val.length > 0 ? val : null;
}

function asNum(val: unknown): number | null {
  return typeof val === 'number' && Number.isFinite(val) ? val : null;
}

function asArr(val: unknown): unknown[] {
  return Array.isArray(val) ? val : [];
}

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 text-xs">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 text-right font-medium text-foreground">{value}</span>
    </div>
  );
}

function ChipList({ items, variant = 'default' }: { items: string[]; variant?: 'default' | 'warning' | 'danger' | 'info' }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge key={item} variant={variant} className="font-mono text-[10px]">
          {item}
        </Badge>
      ))}
    </div>
  );
}

export function StageDetails({
  stage,
  trace,
  onOpenModal,
}: {
  stage: AggregatedStage;
  trace: PipelineTrace;
  onOpenModal: (target: InspectorModalTarget) => void;
}) {
  if (stage.steps.length === 0) return null;
  if (stage.steps.some((s) => s.detail?.hidden === true)) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-dashed border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        <Lock size={13} aria-hidden className="shrink-0" />
        <span>Hidden because a source document is no longer accessible.</span>
      </div>
    );
  }

  switch (stage.def.id) {
    case 'input_pii': {
      const quota = asRec(stage.byStep.quota?.detail);
      const input = asRec(stage.byStep.input?.detail);
      const pii = asRec(stage.byStep.pii?.detail);
      const piiRules = asArr(pii.ruleIds).map(String);
      const maskedText = asStr(pii.maskedText);
      const charCount = asNum(input.charCount);
      const maxChars = asNum(input.maxChars);
      return (
        <div className="space-y-2.5">
          {charCount !== null && maxChars !== null ? (
            <KVRow label="Length" value={`${charCount} / ${maxChars} chars`} />
          ) : null}
          {quota.enabled === true ? (
            <KVRow
              label="Quota"
              value={
                quota.allowed === false
                  ? `Exceeded (${String(quota.state ?? 'limit')})`
                  : quota.questionsLeft != null
                    ? `${String(quota.questionsLeft)} left today`
                    : 'Reserved'
              }
            />
          ) : stage.byStep.quota ? (
            <KVRow label="Quota" value="Unlimited" />
          ) : null}
          <KVRow
            label="PII Masking"
            value={piiRules.length > 0 ? `${piiRules.length} pattern(s) masked` : 'Clean (none found)'}
          />
          {piiRules.length > 0 ? <ChipList items={piiRules} variant="warning" /> : null}
          {maskedText && piiRules.length > 0 ? (
            <div className="rounded-lg border border-border/80 bg-muted/40 p-2 font-mono text-[11px] leading-relaxed text-foreground">
              {maskedText}
            </div>
          ) : null}
        </div>
      );
    }

    case 'guard_rule': {
      const guard = asRec(stage.byStep.guard?.detail);
      const router = asRec(stage.byStep.router?.detail);
      const mt = asRec(stage.byStep.meaningful_tokens?.detail);
      const flags = [...asArr(guard.flagRules), ...asArr(guard.abuseRules)].map(String);
      const stripped = asArr(router.strippedKinds).map(String);
      const workingText = asStr(router.workingText);
      const meaningful = asNum(mt.meaningfulCount);
      const minReq = asNum(mt.minRequired);

      return (
        <div className="space-y-2.5">
          <KVRow
            label="Input Guard"
            value={
              guard.blocked === true ? (
                <span className="font-mono text-danger-foreground">{String(guard.blockedRule ?? 'BLOCKED')}</span>
              ) : flags.length > 0 ? (
                <span className="text-warning-foreground">Flagged ({flags.length})</span>
              ) : (
                <span className="text-success-foreground">Passed</span>
              )
            }
          />
          {flags.length > 0 ? <ChipList items={flags} variant="warning" /> : null}
          {stripped.length > 0 ? (
            <div className="space-y-1">
              <div className="text-[11px] text-muted-foreground">Stripped tokens</div>
              <ChipList items={stripped} variant="info" />
            </div>
          ) : null}
          {meaningful !== null ? (
            <KVRow
              label="Meaningful tokens"
              value={minReq !== null ? `${meaningful} (min ${minReq})` : String(meaningful)}
            />
          ) : null}
          {asStr(router.templateKey) || asStr(mt.templateKey) ? (
            <KVRow
              label="Rule template"
              value={
                <Badge variant="warning" className="font-mono text-[10px]">
                  {asStr(router.templateKey) ?? asStr(mt.templateKey)}
                </Badge>
              }
            />
          ) : null}
          {workingText && stripped.length > 0 ? (
            <div className="rounded-lg border border-border/80 bg-muted/40 p-2 text-[11px] text-foreground">
              <span className="font-semibold text-muted-foreground">Working query: </span>
              {workingText}
            </div>
          ) : null}
        </div>
      );
    }

    case 'classify_route': {
      const frame = asRec(stage.byStep.frame?.detail);
      const signals = asRec(frame.signals);
      const sem = asRec(stage.byStep.semantic_router?.detail);
      const clf = asRec((stage.byStep.setfit_router ?? stage.byStep.setfit_router_shadow)?.detail);
      const docCodes = asArr(frame.docCodes).map(String);
      const signalTags: string[] = [];
      if (signals.followup === true) signalTags.push('follow-up');
      if (signals.comparison === true) signalTags.push('comparison');
      if (frame.short === true) signalTags.push('short');

      return (
        <div className="space-y-2.5">
          {stage.byStep.frame ? (
            <>
              <KVRow label="Language" value={String(frame.lang ?? trace.lang).toUpperCase()} />
              {asNum(frame.tokenCount) !== null ? (
                <KVRow label="Tokens" value={String(frame.tokenCount)} />
              ) : null}
              {signalTags.length > 0 ? <ChipList items={signalTags} variant="info" /> : null}
              {docCodes.length > 0 ? (
                <div className="space-y-1">
                  <div className="text-[11px] text-muted-foreground">Detected document codes</div>
                  <ChipList items={docCodes} variant="info" />
                </div>
              ) : null}
            </>
          ) : null}

          {sem.enabled === true ? (
            <div className="rounded-lg border border-border/80 bg-muted/35 p-2.5 space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Semantic Router
              </div>
              <KVRow label="Top intent" value={String(sem.topIntent ?? sem.intent ?? 'none')} />
              {asNum(sem.score) !== null ? (
                <KVRow
                  label="Score / Margin"
                  value={`${Number(sem.score).toFixed(3)} / ${Number(sem.margin ?? 0).toFixed(3)}`}
                />
              ) : null}
            </div>
          ) : null}

          {Object.keys(clf).length > 0 ? (
            <div className="rounded-lg border border-border/80 bg-muted/35 p-2.5 space-y-1.5">
              <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                <span>SetFit Classifier</span>
                <Badge variant="default" className="text-[9px]">
                  mode: {String(clf.mode ?? 'on')}
                </Badge>
              </div>
              {clf.error ? (
                <p className="text-xs text-warning-foreground">{String(clf.error)}</p>
              ) : (
                <>
                  <KVRow label="Label" value={<span className="font-mono">{String(clf.label ?? '—')}</span>} />
                  <KVRow label="Action" value={String(clf.action ?? '—')} />
                  {asNum(clf.confidence) !== null ? (
                    <div className="space-y-1">
                      <KVRow label="Confidence" value={`${(Number(clf.confidence) * 100).toFixed(1)}%`} />
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/80">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, Number(clf.confidence) * 100))}%` }}
                        />
                      </div>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : null}
        </div>
      );
    }

    case 'rewrite_translate': {
      const rw = asRec(stage.byStep.rewrite?.detail);
      const tr = asRec(stage.byStep.translate?.detail);
      const orig = asStr(rw.originalQuery);
      const rewritten = asStr(rw.rewrittenQuery);
      const translated = asStr(tr.translatedQuery);

      return (
        <div className="space-y-2.5">
          {stage.byStep.rewrite ? (
            <KVRow
              label="Rewrite"
              value={`${String(rw.status ?? 'NONE')}${asNum(rw.historyTurns) ? ` (${rw.historyTurns} turns)` : ''}`}
            />
          ) : null}
          {rewritten && orig ? (
            <div className="space-y-1.5 rounded-lg border border-border/80 bg-muted/35 p-2.5 text-[11px]">
              <div className="text-muted-foreground line-clamp-2">{orig}</div>
              <div className="flex items-center gap-1 font-semibold text-primary-strong">
                <ArrowRight size={11} aria-hidden />
                <span>Standalone query</span>
              </div>
              <div className="font-medium text-foreground">{rewritten}</div>
            </div>
          ) : null}
          {stage.byStep.translate ? (
            <KVRow
              label="Cross-lingual"
              value={
                tr.skipped === true
                  ? 'Not needed'
                  : `${String(tr.sourceLang ?? '').toUpperCase()} → ${String(tr.targetLang ?? '').toUpperCase()} (${String(tr.status ?? '')})`
              }
            />
          ) : null}
          {translated ? (
            <div className="rounded-lg border border-primary/25 bg-primary-soft/35 p-2 text-[11px] text-foreground">
              <span className="font-semibold text-primary-strong">Alt query: </span>
              {translated}
            </div>
          ) : null}
        </div>
      );
    }

    case 'retrieve_dense': {
      const d = asRec(stage.byStep.retrieve_dense?.detail);
      if (d.skipped === true) {
        return <p className="text-xs text-muted-foreground">Dense search disabled by retrieval mode.</p>;
      }
      const denseCount = asNum(d.denseCount) ?? 0;
      const altDense = asNum(d.altDenseCount) ?? 0;
      const topScore = asNum(d.topScore);
      const denseChunks = trace.chunks
        .filter((c) => c.denseScore !== null)
        .sort((a, b) => (b.denseScore ?? -Infinity) - (a.denseScore ?? -Infinity));
      return (
        <div className="space-y-2.5">
          {asStr(d.model) ? (
            <KVRow label="Embedding model" value={<span className="font-mono">{asStr(d.model)}</span>} />
          ) : null}
          <KVRow
            label="Candidates"
            value={altDense > 0 ? `${denseCount} (+${altDense} alt lang)` : String(denseCount)}
          />
          {topScore !== null ? (
            <KVRow label="Top cosine" value={<span className="font-mono">{topScore.toFixed(4)}</span>} />
          ) : null}
          {d.reusedVector === true ? (
            <Badge variant="info" className="text-[10px]">
              Reused router vector
            </Badge>
          ) : null}
          {denseChunks.length > 0 ? (
            <div className="flex items-center justify-between gap-2 rounded-xl border border-border/85 bg-muted/35 px-3 py-2">
              <span className="text-xs font-semibold text-foreground">
                {denseChunks.length} dense chunk{denseChunks.length === 1 ? '' : 's'}
              </span>
              <button
                type="button"
                onClick={() =>
                  onOpenModal({
                    kind: 'chunks',
                    chunks: denseChunks,
                    title: `Dense Vector Chunks (${denseChunks.length})`,
                    description: 'Sorted by pgvector dense cosine similarity (highest first).',
                    primaryMetric: 'dense',
                  })
                }
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-primary/35 bg-primary-soft/65 px-2.5 py-1 text-xs font-semibold text-primary-strong transition-colors hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-ring"
              >
                <Layers size={12} aria-hidden />
                <span>Inspect Chunks</span>
              </button>
            </div>
          ) : null}
        </div>
      );
    }

    case 'retrieve_sparse': {
      const s = asRec(stage.byStep.retrieve_sparse?.detail);
      if (s.skipped === true) {
        return <p className="text-xs text-muted-foreground">Sparse BM25 search disabled by retrieval mode.</p>;
      }
      const bm25Count = asNum(s.bm25Count) ?? 0;
      const altBm25 = asNum(s.altBm25Count) ?? 0;
      const topScore = asNum(s.topScore);
      const terms = asArr(s.terms).map(String);
      const bm25Chunks = trace.chunks
        .filter((c) => c.bm25Score !== null)
        .sort((a, b) => (b.bm25Score ?? -Infinity) - (a.bm25Score ?? -Infinity));
      return (
        <div className="space-y-2.5">
          <KVRow
            label="BM25 candidates"
            value={altBm25 > 0 ? `${bm25Count} (+${altBm25} alt lang)` : String(bm25Count)}
          />
          {topScore !== null ? (
            <KVRow label="Top BM25 score" value={<span className="font-mono">{topScore.toFixed(2)}</span>} />
          ) : null}
          {terms.length > 0 ? (
            <div className="space-y-1">
              <div className="text-[11px] text-muted-foreground">Query terms ({asNum(s.termCount) ?? terms.length})</div>
              <ChipList items={terms.slice(0, 12)} variant="default" />
            </div>
          ) : null}
          {bm25Chunks.length > 0 ? (
            <div className="flex items-center justify-between gap-2 rounded-xl border border-border/85 bg-muted/35 px-3 py-2">
              <span className="text-xs font-semibold text-foreground">
                {bm25Chunks.length} BM25 chunk{bm25Chunks.length === 1 ? '' : 's'}
              </span>
              <button
                type="button"
                onClick={() =>
                  onOpenModal({
                    kind: 'chunks',
                    chunks: bm25Chunks,
                    title: `Sparse BM25 Chunks (${bm25Chunks.length})`,
                    description: 'Sorted by BM25 lexical term-frequency score (highest first).',
                    primaryMetric: 'bm25',
                  })
                }
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-primary/35 bg-primary-soft/65 px-2.5 py-1 text-xs font-semibold text-primary-strong transition-colors hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-ring"
              >
                <Layers size={12} aria-hidden />
                <span>Inspect Chunks</span>
              </button>
            </div>
          ) : null}
        </div>
      );
    }

    case 'retrieve_rrf': {
      const rrf = asRec(stage.byStep.retrieve_rrf?.detail);
      if (rrf.skipped === true) {
        return <p className="text-xs text-muted-foreground">RRF fusion skipped (single-branch retrieval mode).</p>;
      }
      const docCodes = asArr(rrf.docCodes).map(String);
      const rrfChunks = trace.chunks
        .filter((c) => c.fusionScore !== null)
        .sort((a, b) => (b.fusionScore ?? -Infinity) - (a.fusionScore ?? -Infinity));
      return (
        <div className="space-y-2.5">
          <div className="grid grid-cols-4 gap-1.5 text-center">
            {[
              { label: 'Dense', val: asNum(rrf.denseCount) },
              { label: 'BM25', val: asNum(rrf.bm25Count) },
              { label: 'Fused', val: asNum(rrf.fusedCount) },
              { label: 'Pool', val: asNum(rrf.poolCount) },
            ].map((cell) => (
              <div key={cell.label} className="rounded-lg border border-border/80 bg-muted/40 px-1.5 py-1.5">
                <div className="text-[9px] font-semibold uppercase text-muted-foreground">{cell.label}</div>
                <div className="font-mono text-xs font-bold text-foreground">{cell.val ?? 0}</div>
              </div>
            ))}
          </div>
          <KVRow
            label="RRF parameters"
            value={`k=${asNum(rrf.rrfK) ?? 60} · weights [${asArr(rrf.rrfWeights).join(', ')}]`}
          />
          {asNum(rrf.docCodeMatches) ? (
            <KVRow label="Doc-code boost" value={`${rrf.docCodeMatches} chunk(s) boosted`} />
          ) : null}
          {docCodes.length > 0 ? <ChipList items={docCodes} variant="info" /> : null}
          {rrfChunks.length > 0 ? (
            <div className="flex items-center justify-between gap-2 rounded-xl border border-border/85 bg-muted/35 px-3 py-2">
              <span className="text-xs font-semibold text-foreground">
                {rrfChunks.length} fused chunk{rrfChunks.length === 1 ? '' : 's'}
              </span>
              <button
                type="button"
                onClick={() =>
                  onOpenModal({
                    kind: 'chunks',
                    chunks: rrfChunks,
                    title: `RRF Fused Pool Chunks (${rrfChunks.length})`,
                    description: 'Sorted by Reciprocal Rank Fusion + doc-code boost score before cross-encoder reranking.',
                    primaryMetric: 'fusion',
                  })
                }
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-primary/35 bg-primary-soft/65 px-2.5 py-1 text-xs font-semibold text-primary-strong transition-colors hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-ring"
              >
                <Layers size={12} aria-hidden />
                <span>Inspect Chunks</span>
              </button>
            </div>
          ) : null}
        </div>
      );
    }

    case 'retrieve_rerank': {
      const ret = asRec(stage.byStep.retrieve_and_gate?.detail);
      const scope = asRec(ret.accessScope);
      const gateScore = asNum(ret.gateScore);
      const threshold = asNum(ret.threshold);
      const passed = ret.passed === true;
      const chunks: RetrievedChunkTrace[] =
        trace.chunks.length > 0 ? trace.chunks : (asArr(ret.chunks) as RetrievedChunkTrace[]);
      const inContextCount = chunks.filter((c) => c.inContext).length;

      return (
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="info" className="font-mono text-[10px]">
              {String(ret.mode ?? trace.mode)}
            </Badge>
            <Badge variant="success" icon={<ShieldCheck size={10} aria-hidden />} className="text-[10px]">
              {scope.departmentScoped ? 'Workspace + Dept RLS' : 'Workspace RLS'}
            </Badge>
            {asStr(ret.rerankModel) ? (
              <Badge variant="default" className="font-mono text-[10px]">
                {asStr(ret.rerankModel)}
              </Badge>
            ) : null}
            {asStr(ret.refusal) ? (
              <Badge variant="danger" className="font-mono text-[10px]">
                {asStr(ret.refusal)}
              </Badge>
            ) : null}
          </div>

          {gateScore !== null ? (
            <div className="rounded-lg border border-border/80 bg-muted/35 p-2.5 space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Relevance Gate</span>
                <span className={`font-mono font-semibold ${passed ? 'text-success-foreground' : 'text-danger-foreground'}`}>
                  {gateScore.toFixed(3)} {passed ? '≥' : '<'} {threshold !== null ? threshold.toFixed(3) : '—'}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/80">
                <div
                  className={`h-full rounded-full ${passed ? 'bg-success' : 'bg-danger'}`}
                  style={{ width: `${Math.min(100, Math.max(4, gateScore * 100))}%` }}
                />
              </div>
            </div>
          ) : null}

          <div className="flex items-center justify-between gap-2 rounded-xl border border-border/85 bg-muted/35 px-3 py-2">
            <div className="text-xs">
              <span className="font-semibold text-foreground">{chunks.length} chunk{chunks.length === 1 ? '' : 's'}</span>
              <span className="text-muted-foreground"> · {inContextCount} in context</span>
            </div>
            {chunks.length > 0 ? (
              <button
                type="button"
                onClick={() => onOpenModal({ kind: 'chunks', chunks })}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-primary/35 bg-primary-soft/65 px-2.5 py-1 text-xs font-semibold text-primary-strong transition-colors hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-ring"
              >
                <Layers size={12} aria-hidden />
                <span>Inspect Chunks</span>
              </button>
            ) : null}
          </div>
        </div>
      );
    }

    case 'context_prompt': {
      const bc = asRec(stage.byStep.build_context?.detail);
      const bp = asRec(stage.byStep.build_prompt?.detail);
      const sources = asArr(bc.sources) as ContextSourceTrace[];
      const tokensUsed = asNum(bc.tokensUsed);
      const tokenBudget = asNum(bc.tokenBudget);
      const promptMessages: PromptMessageTrace[] | null =
        trace.promptMessages ?? (Array.isArray(bp.messages) ? (bp.messages as PromptMessageTrace[]) : null);
      const llmDetail = asRec(trace.steps.find((s) => s.step === 'generate_and_stream')?.detail);

      return (
        <div className="space-y-2.5">
          {tokensUsed !== null ? (
            <KVRow
              label="Context budget"
              value={
                tokenBudget !== null
                  ? `${tokensUsed.toLocaleString()} / ${tokenBudget.toLocaleString()} tok`
                  : `${tokensUsed.toLocaleString()} tok`
              }
            />
          ) : null}
          {stage.byStep.build_context ? (
            <KVRow label="Section expand" value={bc.expand === false ? 'Off' : 'On'} />
          ) : null}
          {sources.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {sources.map((s) => (
                <span
                  key={s.n}
                  className="inline-flex max-w-full items-center gap-1 rounded-lg border border-border bg-muted/45 px-2 py-0.5 text-[11px] text-foreground"
                >
                  <span className="font-mono font-bold text-primary-strong">[{s.n}]</span>
                  <span className="truncate max-w-[160px]">{s.title ?? 'Document'}</span>
                  {s.tokens != null ? <span className="text-[10px] text-muted-foreground">{s.tokens}t</span> : null}
                  {s.reduced ? <span className="text-[9px] text-warning-foreground">reduced</span> : null}
                </span>
              ))}
            </div>
          ) : null}

          {asStr(bp.systemPreview) || promptMessages ? (
            <div className="rounded-xl border border-border bg-muted/35 p-2.5 space-y-2">
              <div className="flex items-center justify-between gap-2 text-[11px]">
                <span className="font-semibold text-foreground">Final Fusion Prompt</span>
                <Badge variant="success" className="text-[9px]">
                  Canary redacted
                </Badge>
              </div>
              {asStr(bp.userMessage) ? (
                <p className="line-clamp-2 font-mono text-[11px] text-foreground">{asStr(bp.userMessage)}</p>
              ) : null}
              {asStr(bp.systemPreview) ? (
                <p className="line-clamp-2 font-mono text-[10px] text-muted-foreground">{asStr(bp.systemPreview)}</p>
              ) : null}
              {promptMessages ? (
                <button
                  type="button"
                  onClick={() =>
                    onOpenModal({
                      kind: 'prompt',
                      messages: promptMessages,
                      promptVersion: asStr(bp.promptVersion) ?? undefined,
                      model: asStr(llmDetail.model),
                      promptTokens: asNum(bp.promptTokensEst),
                    })
                  }
                  className="inline-flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-primary/35 bg-primary-soft/60 px-3 py-1.5 text-xs font-semibold text-primary-strong transition-colors hover:bg-primary-soft"
                >
                  <FileCode2 size={13} aria-hidden />
                  <span>View Full Fusion Prompt</span>
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      );
    }

    case 'llm_generate': {
      const gen = asRec(stage.byStep.generate_and_stream?.detail);
      const model = asStr(gen.model);
      const provider = asStr(gen.provider) ?? 'modal';
      const promptTok = asNum(gen.promptTokens);
      const outTok = asNum(gen.outputTokens);
      const usageSrc = asStr(gen.usageSource) ?? 'estimated';
      const guardVerdict = asStr(gen.outputGuard);

      return (
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="info" icon={<Cpu size={11} aria-hidden />} className="font-mono text-[10px]">
              {provider} · {model ?? 'connecting…'}
            </Badge>
            {gen.streamingPhase ? (
              <Badge variant="default" className="text-[10px]">
                {gen.streamingPhase === 'thinking' ? 'Thinking…' : 'Streaming…'}
              </Badge>
            ) : null}
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className="rounded-lg border border-border/80 bg-muted/40 px-1.5 py-1.5">
              <div className="text-[9px] font-semibold uppercase text-muted-foreground">Reasoning</div>
              <div className="font-mono text-xs font-semibold text-foreground">
                {asNum(gen.reasoningMs) !== null ? formatMs(asNum(gen.reasoningMs)) : '—'}
              </div>
            </div>
            <div className="rounded-lg border border-border/80 bg-muted/40 px-1.5 py-1.5">
              <div className="text-[9px] font-semibold uppercase text-muted-foreground">First Delta</div>
              <div className="font-mono text-xs font-semibold text-foreground">
                {asNum(gen.firstDeltaMs) !== null ? formatMs(asNum(gen.firstDeltaMs)) : '—'}
              </div>
            </div>
            <div className="rounded-lg border border-border/80 bg-muted/40 px-1.5 py-1.5">
              <div className="text-[9px] font-semibold uppercase text-muted-foreground">Total</div>
              <div className="font-mono text-xs font-semibold text-foreground">
                {asNum(gen.generateMs) !== null ? formatMs(asNum(gen.generateMs)) : '—'}
              </div>
            </div>
          </div>
          {promptTok !== null || outTok !== null ? (
            <KVRow
              label={`Tokens (${usageSrc === 'provider' ? 'exact' : 'est.'})`}
              value={`${(promptTok ?? 0).toLocaleString()} in · ${(outTok ?? 0).toLocaleString()} out`}
            />
          ) : null}
          {gen.reasoningWithheld === true ? (
            <p className="text-[11px] text-warning-foreground">
              Reasoning was withheld by OutputGuard.
            </p>
          ) : null}
          {guardVerdict && guardVerdict !== 'passed' ? (
            <Badge variant="danger" icon={<ShieldAlert size={11} aria-hidden />} className="font-mono text-[10px]">
              OutputGuard: {guardVerdict}
            </Badge>
          ) : null}
        </div>
      );
    }

    case 'post_checks': {
      const gen = asRec(trace.steps.find((s) => s.step === 'generate_and_stream')?.detail);
      const cite = asRec(stage.byStep.postprocess_citations?.detail);
      const sr = asRec(stage.byStep.detect_self_refusal?.detail);
      const nc = asRec(stage.byStep.check_numbers?.detail);
      const warnings = asArr(nc.warnings).map((w) => asRec(w));
      const outputGuard = asStr(gen.outputGuard) ?? 'passed';

      return (
        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">OutputGuard</span>
            {outputGuard === 'passed' ? (
              <span className="inline-flex items-center gap-1 font-medium text-success-foreground">
                <CheckCircle2 size={12} aria-hidden /> Passed
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 font-mono font-medium text-danger-foreground">
                <ShieldAlert size={12} aria-hidden /> {outputGuard}
              </span>
            )}
          </div>
          {stage.byStep.postprocess_citations ? (
            <KVRow
              label="Verified citations"
              value={`${asNum(cite.citationCount) ?? 0}${
                asNum(cite.invalidMarkersRemoved) ? ` (${cite.invalidMarkersRemoved} invalid removed)` : ''
              }`}
            />
          ) : null}
          {stage.byStep.detect_self_refusal ? (
            <KVRow
              label="Self-refusal check"
              value={
                sr.detected === true ? (
                  <span className="text-warning-foreground">GENERATOR_NOT_FOUND</span>
                ) : (
                  <span className="text-success-foreground">Passed</span>
                )
              }
            />
          ) : null}
          {stage.byStep.check_numbers ? (
            <KVRow
              label="Number grounding"
              value={
                nc.warned === true ? (
                  <span className="inline-flex items-center gap-1 text-warning-foreground">
                    <AlertTriangle size={12} aria-hidden /> Flagged
                  </span>
                ) : (
                  <span className="text-success-foreground">Grounded</span>
                )
              }
            />
          ) : null}
          {warnings.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {warnings.flatMap((w) => asArr(w.values).map(String)).map((v, i) => (
                <Badge key={`${v}-${i}`} variant="warning" className="font-mono text-[10px]">
                  {v}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      );
    }
  }
}

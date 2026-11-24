'use client';

import { motion, useReducedMotion } from 'motion/react';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui';
import type {
  ContextSourceTrace,
  PipelineTrace,
  PromptMessageTrace,
  RetrievedChunkTrace,
} from '@/lib/api/types';
import { formatMs, type AggregatedStage } from '@/lib/chat/pipeline-trace';
import { cn } from '@/lib/utils';
import type { InspectorModalTarget } from './InspectorDetailModal';

type Tone = 'success' | 'warning' | 'danger';

type Detail =
  | { kind: 'kv'; label: string; value: string; mono?: boolean; tone?: Tone }
  | { kind: 'bar'; label: string; value: number; text: string }
  | { kind: 'gate'; score: number; threshold: number; passed: boolean }
  | { kind: 'chips'; label: string; items: string[]; mono?: boolean }
  | { kind: 'quote'; label: string; text: string };

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

function DetailRow({ d, reduced }: { d: Detail; reduced: boolean }) {
  const toneCls = (tone?: Tone) =>
    tone === 'success'
      ? 'text-success-foreground'
      : tone === 'warning'
        ? 'text-warning-foreground'
        : tone === 'danger'
          ? 'text-danger-foreground'
          : 'text-foreground';

  switch (d.kind) {
    case 'kv':
      return (
        <div className="flex items-start justify-between gap-4 text-[13px]">
          <dt className="shrink-0 text-muted-foreground">{d.label}</dt>
          <dd
            className={cn(
              'min-w-0 text-right [overflow-wrap:anywhere]',
              d.mono && 'font-mono text-xs leading-5 tabular-nums',
              toneCls(d.tone),
            )}
          >
            {d.value}
          </dd>
        </div>
      );

    case 'bar': {
      const pct = Math.min(1, Math.max(0, d.value));
      return (
        <div className="text-[13px]">
          <div className="flex items-center justify-between gap-4">
            <dt className="text-muted-foreground">{d.label}</dt>
            <dd className="font-mono text-xs tabular-nums text-foreground">{d.text}</dd>
          </div>
          <div aria-hidden className="mt-1.5 h-1 overflow-hidden rounded-full bg-border">
            <motion.div
              initial={reduced ? false : { scaleX: 0 }}
              animate={{ scaleX: pct }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="h-full w-full origin-left rounded-full bg-primary"
            />
          </div>
        </div>
      );
    }

    case 'gate': {
      const scorePct = Math.min(1, Math.max(0, d.score));
      const thresholdPct = Math.min(100, Math.max(0, Math.round(d.threshold * 100)));
      return (
        <div className="text-[13px]">
          <div className="flex items-center justify-between gap-4">
            <dt className="text-muted-foreground">Relevance gate</dt>
            <dd className={cn('font-mono text-xs tabular-nums', d.passed ? 'text-success-foreground' : 'text-warning-foreground')}>
              {d.score.toFixed(3)} {d.passed ? '≥' : '<'} {d.threshold.toFixed(3)} · {d.passed ? 'passed' : 'not passed'}
            </dd>
          </div>
          <div aria-hidden className="relative mt-1.5 h-1 rounded-full bg-border">
            <motion.div
              initial={reduced ? false : { scaleX: 0 }}
              animate={{ scaleX: scorePct }}
              transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
              className={cn('h-full w-full origin-left rounded-full', d.passed ? 'bg-success' : 'bg-warning')}
            />
            <div className="absolute -top-1 h-3 w-px bg-foreground" style={{ left: `${thresholdPct}%` }} />
          </div>
        </div>
      );
    }

    case 'chips':
      return (
        <div className="text-[13px]">
          <dt className="text-muted-foreground">{d.label}</dt>
          <dd className="mt-1.5 flex flex-wrap gap-1.5">
            {d.items.map((item, idx) => (
              <span
                key={`${item}-${idx}`}
                className={cn(
                  'inline-flex max-w-full items-center rounded-[5px] bg-card px-1.5 py-0.5 text-foreground shadow-2xs ring-1 ring-border/70',
                  d.mono ? 'font-mono text-xs' : 'text-[13px]',
                )}
              >
                <span className="truncate">{item}</span>
              </span>
            ))}
          </dd>
        </div>
      );

    case 'quote':
      return (
        <div className="text-[13px]">
          <dt className="text-muted-foreground">{d.label}</dt>
          <dd className="mt-1 border-l-2 border-border-strong pl-2.5 text-foreground [overflow-wrap:anywhere]">
            {d.text}
          </dd>
        </div>
      );
  }
}

function buildStageDetails(
  stage: AggregatedStage,
  trace: PipelineTrace,
): { details: Detail[]; modalTarget: InspectorModalTarget | null } {
  const details: Detail[] = [];
  let modalTarget: InspectorModalTarget | null = null;

  switch (stage.def.id) {
    case 'input_pii': {
      const quota = asRec(stage.byStep.quota?.detail);
      const input = asRec(stage.byStep.input?.detail);
      const pii = asRec(stage.byStep.pii?.detail);
      const piiRules = asArr(pii.ruleIds).map(String);
      const maskedText = asStr(pii.maskedText);
      const charCount = asNum(input.charCount);
      const maxChars = asNum(input.maxChars);

      if (charCount !== null && maxChars !== null) {
        details.push({ kind: 'kv', label: 'Length', value: `${charCount.toLocaleString()} / ${maxChars.toLocaleString()} characters` });
      }
      if (quota.enabled === true) {
        details.push({
          kind: 'kv',
          label: 'Question quota',
          value:
            quota.allowed === false
              ? `Exceeded (${String(quota.state ?? 'limit')})`
              : quota.questionsLeft != null
                ? `${String(quota.questionsLeft)} left today`
                : 'Reserved',
          tone: quota.allowed === false ? 'danger' : undefined,
        });
      } else if (stage.byStep.quota) {
        details.push({ kind: 'kv', label: 'Question quota', value: 'Unlimited' });
      }
      details.push({
        kind: 'kv',
        label: 'Personal data',
        value: piiRules.length > 0 ? `${piiRules.length} pattern(s) masked` : 'None found',
        tone: piiRules.length > 0 ? 'warning' : 'success',
      });
      if (piiRules.length > 0) {
        details.push({ kind: 'chips', label: 'Masked rules', items: piiRules, mono: true });
      }
      if (maskedText && piiRules.length > 0) {
        details.push({ kind: 'quote', label: 'Masked question', text: maskedText });
      }
      break;
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
      const templateKey = asStr(router.templateKey) ?? asStr(mt.templateKey);

      details.push({
        kind: 'kv',
        label: 'Input guard',
        value:
          guard.blocked === true
            ? String(guard.blockedRule ?? 'Blocked')
            : flags.length > 0
              ? `Flagged (${flags.length})`
              : 'Passed',
        mono: guard.blocked === true,
        tone: guard.blocked === true ? 'danger' : flags.length > 0 ? 'warning' : 'success',
      });
      if (flags.length > 0) {
        details.push({ kind: 'chips', label: 'Flagged rules', items: flags, mono: true });
      }
      if (stripped.length > 0) {
        details.push({ kind: 'chips', label: 'Stripped tokens', items: stripped, mono: true });
      }
      if (meaningful !== null) {
        details.push({
          kind: 'kv',
          label: 'Meaningful words',
          value: minReq !== null ? `${meaningful} (min ${minReq})` : String(meaningful),
        });
      }
      details.push({
        kind: 'kv',
        label: 'Rule template',
        value: templateKey ?? 'None',
        mono: Boolean(templateKey),
        tone: templateKey ? 'warning' : undefined,
      });
      if (workingText && stripped.length > 0) {
        details.push({ kind: 'quote', label: 'Working query', text: workingText });
      }
      break;
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

      if (stage.byStep.frame) {
        details.push({ kind: 'kv', label: 'Language', value: String(frame.lang ?? trace.lang).toUpperCase(), mono: true });
        if (asNum(frame.tokenCount) !== null) {
          details.push({ kind: 'kv', label: 'Words', value: String(frame.tokenCount), mono: true });
        }
        if (signalTags.length > 0) {
          details.push({ kind: 'chips', label: 'Signals', items: signalTags, mono: true });
        }
        if (docCodes.length > 0) {
          details.push({ kind: 'chips', label: 'Document codes', items: docCodes, mono: true });
        }
      }
      if (sem.enabled === true) {
        details.push({ kind: 'kv', label: 'Semantic intent', value: String(sem.topIntent ?? sem.intent ?? 'none'), mono: true });
        if (asNum(sem.score) !== null) {
          details.push({
            kind: 'kv',
            label: 'Semantic score / margin',
            value: `${Number(sem.score).toFixed(3)} / ${Number(sem.margin ?? 0).toFixed(3)}`,
            mono: true,
          });
        }
      }
      if (Object.keys(clf).length > 0) {
        if (clf.error) {
          details.push({ kind: 'kv', label: 'Classifier', value: String(clf.error), tone: 'warning' });
        } else {
          if (clf.label) {
            details.push({ kind: 'kv', label: 'Classifier label', value: String(clf.label), mono: true });
          }
          const conf = asNum(clf.confidence);
          if (conf !== null) {
            details.push({
              kind: 'bar',
              label: 'Classifier confidence',
              value: conf,
              text: `${(conf * 100).toFixed(1)}%`,
            });
          }
          if (clf.action) {
            details.push({ kind: 'kv', label: 'Action', value: String(clf.action) });
          }
        }
      }
      break;
    }

    case 'rewrite_translate': {
      const rw = asRec(stage.byStep.rewrite?.detail);
      const tr = asRec(stage.byStep.translate?.detail);
      const rewritten = asStr(rw.rewrittenQuery);
      const translated = asStr(tr.translatedQuery);

      if (stage.byStep.rewrite) {
        const turns = asNum(rw.historyTurns);
        details.push({
          kind: 'kv',
          label: 'Rewrite',
          value: rewritten
            ? turns
              ? `Rewritten with ${turns} earlier ${turns === 1 ? 'turn' : 'turns'}`
              : 'Rewritten'
            : String(rw.status ?? 'Not needed'),
        });
      }
      if (rewritten) {
        details.push({ kind: 'quote', label: 'Standalone question', text: rewritten });
      }
      if (stage.byStep.translate) {
        details.push({
          kind: 'kv',
          label: 'Cross-lingual',
          value:
            tr.skipped === true
              ? 'Not needed'
              : `${String(tr.sourceLang ?? '').toUpperCase()} → ${String(tr.targetLang ?? '').toUpperCase()}`,
        });
      }
      if (translated) {
        details.push({ kind: 'quote', label: 'Second-language query', text: translated });
      }
      break;
    }

    case 'retrieve_dense': {
      const d = asRec(stage.byStep.retrieve_dense?.detail);
      if (d.skipped === true) {
        details.push({ kind: 'kv', label: 'Reason', value: 'Dense search disabled by retrieval mode.' });
        break;
      }
      const denseCount = asNum(d.denseCount) ?? 0;
      const altDense = asNum(d.altDenseCount) ?? 0;
      const topScore = asNum(d.topScore);

      if (asStr(d.model)) {
        details.push({ kind: 'kv', label: 'Embedding model', value: asStr(d.model)!, mono: true });
      }
      details.push({
        kind: 'kv',
        label: 'Candidates',
        value: altDense > 0 ? `${denseCount} (+${altDense} in the second language)` : String(denseCount),
      });
      if (topScore !== null) {
        details.push({ kind: 'bar', label: 'Top cosine', value: topScore, text: topScore.toFixed(4) });
      }
      if (d.reusedVector === true) {
        details.push({ kind: 'kv', label: 'Embedding vector', value: 'Reused from router', tone: 'success' });
      }
      const denseChunks = trace.chunks.filter((c) => c.denseScore !== null);
      if (denseChunks.length > 0) {
        modalTarget = { kind: 'chunks-dense', chunks: denseChunks };
      }
      break;
    }

    case 'retrieve_sparse': {
      const s = asRec(stage.byStep.retrieve_sparse?.detail);
      if (s.skipped === true) {
        details.push({ kind: 'kv', label: 'Reason', value: 'Keyword search disabled by retrieval mode.' });
        break;
      }
      const bm25Count = asNum(s.bm25Count) ?? 0;
      const altBm25 = asNum(s.altBm25Count) ?? 0;
      const topScore = asNum(s.topScore);
      const terms = asArr(s.terms).map(String);

      details.push({
        kind: 'kv',
        label: 'Candidates',
        value: altBm25 > 0 ? `${bm25Count} (+${altBm25} in the second language)` : String(bm25Count),
      });
      if (topScore !== null) {
        details.push({ kind: 'kv', label: 'Top BM25 score', value: topScore.toFixed(2), mono: true });
      }
      if (terms.length > 0) {
        details.push({
          kind: 'chips',
          label: `Query terms (${asNum(s.termCount) ?? terms.length})`,
          items: terms.slice(0, 12),
          mono: true,
        });
      }
      const bm25Chunks = trace.chunks.filter((c) => c.bm25Score !== null);
      if (bm25Chunks.length > 0) {
        modalTarget = { kind: 'chunks-bm25', chunks: bm25Chunks };
      }
      break;
    }

    case 'retrieve_rrf': {
      const rrf = asRec(stage.byStep.retrieve_rrf?.detail);
      if (rrf.skipped === true) {
        details.push({ kind: 'kv', label: 'Reason', value: 'Skipped (single-branch retrieval mode).' });
        break;
      }
      const denseCount = asNum(rrf.denseCount) ?? 0;
      const bm25Count = asNum(rrf.bm25Count) ?? 0;
      const fusedCount = asNum(rrf.fusedCount) ?? 0;
      const poolCount = asNum(rrf.poolCount) ?? 0;
      const weights = asArr(rrf.rrfWeights);
      const docCodeMatches = asNum(rrf.docCodeMatches) ?? 0;
      const docCodes = asArr(rrf.docCodes).map(String);

      details.push({
        kind: 'kv',
        label: 'Dense · BM25 · merged · pool',
        value: `${denseCount} · ${bm25Count} · ${fusedCount} · ${poolCount}`,
        mono: true,
      });
      details.push({
        kind: 'kv',
        label: 'Parameters',
        value: `k = ${asNum(rrf.rrfK) ?? 60}${weights.length > 0 ? ` · weights ${weights.join(', ')}` : ''}`,
        mono: true,
      });
      details.push({
        kind: 'kv',
        label: 'Document-code boost',
        value: docCodeMatches > 0 ? `${docCodeMatches} passage(s) boosted` : 'None',
      });
      if (docCodes.length > 0) {
        details.push({ kind: 'chips', label: 'Matched codes', items: docCodes, mono: true });
      }
      const rrfChunks = trace.chunks.filter((c) => c.fusionScore !== null);
      if (rrfChunks.length > 0) {
        modalTarget = { kind: 'chunks-rrf', chunks: rrfChunks };
      }
      break;
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

      if (gateScore !== null && threshold !== null) {
        details.push({ kind: 'gate', score: gateScore, threshold, passed });
      } else if (gateScore !== null) {
        details.push({ kind: 'bar', label: 'Relevance score', value: gateScore, text: gateScore.toFixed(3) });
      }
      if (asStr(ret.rerankModel)) {
        details.push({ kind: 'kv', label: 'Reranker', value: asStr(ret.rerankModel)!, mono: true });
      }
      details.push({
        kind: 'kv',
        label: 'Access filter',
        value: scope.departmentScoped ? 'Workspace and department rules applied' : 'Workspace rules applied',
        tone: 'success',
      });
      details.push({
        kind: 'kv',
        label: 'Passages',
        value:
          inContextCount > 0
            ? `${chunks.length} scored · ${inContextCount} in context`
            : `${chunks.length} scored · none in context`,
      });
      if (asStr(ret.refusal)) {
        details.push({ kind: 'kv', label: 'Refusal', value: asStr(ret.refusal)!, mono: true, tone: 'danger' });
      }
      if (chunks.length > 0) {
        modalTarget = { kind: 'chunks-rerank', chunks };
      }
      break;
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

      if (tokensUsed !== null) {
        details.push({
          kind: 'kv',
          label: 'Context budget',
          value:
            tokenBudget !== null
              ? `${tokensUsed.toLocaleString()} / ${tokenBudget.toLocaleString()} tokens`
              : `${tokensUsed.toLocaleString()} tokens`,
          mono: true,
        });
      }
      if (stage.byStep.build_context) {
        details.push({ kind: 'kv', label: 'Section expansion', value: bc.expand === false ? 'Off' : 'On' });
      }
      if (sources.length > 0) {
        details.push({
          kind: 'chips',
          label: 'Sources in the prompt',
          items: sources.map((s) => `[${s.n}] ${s.title ?? 'Document'}${s.tokens != null ? ` (${s.tokens}t)` : ''}`),
        });
      }
      if (promptMessages && promptMessages.length > 0) {
        modalTarget = {
          kind: 'prompt',
          messages: promptMessages,
          promptVersion: asStr(bp.promptVersion) ?? undefined,
          model: asStr(llmDetail.model),
          promptTokens: asNum(bp.promptTokensEst),
        };
      }
      break;
    }

    case 'llm_generate': {
      const gen = asRec(stage.byStep.generate_and_stream?.detail);
      const model = asStr(gen.model);
      const provider = asStr(gen.provider) ?? 'Modal (self-hosted)';
      const promptTok = asNum(gen.promptTokens);
      const outTok = asNum(gen.outputTokens);
      const usageSrc = asStr(gen.usageSource) ?? 'estimated';
      const guardVerdict = asStr(gen.outputGuard);

      details.push({ kind: 'kv', label: 'Provider', value: provider });
      if (model) {
        details.push({ kind: 'kv', label: 'Model', value: model, mono: true });
      }
      if (asNum(gen.reasoningMs) !== null) {
        details.push({ kind: 'kv', label: 'Reasoning', value: formatMs(asNum(gen.reasoningMs)), mono: true });
      }
      if (asNum(gen.firstDeltaMs) !== null) {
        details.push({ kind: 'kv', label: 'First answer token', value: formatMs(asNum(gen.firstDeltaMs)), mono: true });
      }
      if (asNum(gen.generateMs) !== null) {
        details.push({ kind: 'kv', label: 'Generation time', value: formatMs(asNum(gen.generateMs)), mono: true });
      }
      if (promptTok !== null || outTok !== null) {
        details.push({
          kind: 'kv',
          label: `Tokens (${usageSrc === 'provider' ? 'exact' : 'estimated'})`,
          value: `${(promptTok ?? 0).toLocaleString()} in · ${(outTok ?? 0).toLocaleString()} out`,
          mono: true,
        });
      }
      if (gen.reasoningWithheld === true) {
        details.push({ kind: 'kv', label: 'Reasoning', value: 'Withheld by output guard', tone: 'warning' });
      }
      if (guardVerdict && guardVerdict !== 'passed') {
        details.push({ kind: 'kv', label: 'Output guard', value: guardVerdict, mono: true, tone: 'danger' });
      }
      break;
    }

    case 'post_checks': {
      const gen = asRec(trace.steps.find((s) => s.step === 'generate_and_stream')?.detail);
      const cite = asRec(stage.byStep.postprocess_citations?.detail);
      const sr = asRec(stage.byStep.detect_self_refusal?.detail);
      const nc = asRec(stage.byStep.check_numbers?.detail);
      const warnings = asArr(nc.warnings).map((w) => asRec(w));
      const outputGuard = asStr(gen.outputGuard) ?? 'passed';

      details.push({
        kind: 'kv',
        label: 'Output guard',
        value: outputGuard === 'passed' ? 'Passed' : outputGuard,
        mono: outputGuard !== 'passed',
        tone: outputGuard === 'passed' ? 'success' : 'danger',
      });
      if (stage.byStep.postprocess_citations) {
        const removed = asNum(cite.invalidMarkersRemoved);
        details.push({
          kind: 'kv',
          label: 'Verified citations',
          value: `${asNum(cite.citationCount) ?? 0}${removed ? ` (${removed} invalid removed)` : ''}`,
          mono: true,
        });
      }
      if (stage.byStep.detect_self_refusal) {
        details.push({
          kind: 'kv',
          label: 'Self-refusal check',
          value: sr.detected === true ? 'GENERATOR_NOT_FOUND' : 'Passed',
          mono: sr.detected === true,
          tone: sr.detected === true ? 'warning' : 'success',
        });
      }
      if (stage.byStep.check_numbers) {
        details.push({
          kind: 'kv',
          label: 'Number grounding',
          value: nc.warned === true ? 'Flagged' : 'Grounded',
          tone: nc.warned === true ? 'warning' : 'success',
        });
      }
      const flaggedValues = warnings.flatMap((w) => asArr(w.values).map(String));
      if (flaggedValues.length > 0) {
        details.push({ kind: 'chips', label: 'Unverified figures', items: flaggedValues, mono: true });
      }
      break;
    }
  }

  return { details, modalTarget };
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
  const reduced = useReducedMotion() ?? false;

  if (stage.steps.length === 0) return null;
  if (stage.steps.some((s) => s.detail?.hidden === true)) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Lock size={13} aria-hidden className="shrink-0" />
        <span>Hidden because a source document is no longer accessible.</span>
      </div>
    );
  }

  const { details, modalTarget } = buildStageDetails(stage, trace);
  if (details.length === 0 && !modalTarget) return null;

  return (
    <div>
      {details.length > 0 ? (
        <dl className="space-y-2">
          {details.map((d, i) => (
            <DetailRow key={i} d={d} reduced={reduced} />
          ))}
        </dl>
      ) : null}
      {modalTarget ? (
        <Button size="sm" variant="outline" className="mt-3" onClick={() => onOpenModal(modalTarget)}>
          Details
        </Button>
      ) : null}
    </div>
  );
}

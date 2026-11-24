'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { FileCode2, FileText, Lock, ShieldCheck, Sparkles } from 'lucide-react';
import { BrandMark } from '@/components/motion/Primitives';

const DOCS = [
  { code: 'HR-POL-2026', type: 'PDF', tag: 'VN', icon: FileText },
  { code: 'ISO-SOP-014', type: 'PDF', tag: 'EN', icon: FileText },
  { code: 'ENG-RUNBOOK', type: 'MD', tag: 'EN', icon: FileCode2 },
] as const;

const STAGES = [
  { id: 0, label: '1. Tenant Vault' },
  { id: 1, label: '2. Hybrid RAG' },
  { id: 2, label: '3. Cited Answer' },
] as const;

/**
 * Interactive animated system overview diagram for the /login hero rail:
 * communicates SOPilot's multi-tenant ingestion -> Hybrid RAG -> verified citation flow visually
 * with minimal text. Automatically pauses cycling under prefers-reduced-motion.
 */
export function SopFlowVisual() {
  const [stage, setStage] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced || paused) return;
    const id = window.setInterval(() => {
      setStage((s) => (s + 1) % 3);
    }, 2600);
    return () => window.clearInterval(id);
  }, [paused]);

  return (
    <div className="@container w-full">
      <div
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        className="relative w-full rounded-2xl border border-white/12 bg-white/[0.035] p-4 shadow-[0_24px_64px_rgba(2,12,20,0.45)] backdrop-blur-md sm:p-5 @lg:p-7 @2xl:p-8"
      >
      {/* Top interactive stage pills */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-2.5 @lg:mb-7 @2xl:mb-8">
        <div className="flex flex-wrap items-center gap-1.5 @lg:gap-2">
          {STAGES.map((item) => {
            const active = stage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setStage(item.id)}
                className={`relative cursor-pointer rounded-full px-2.5 py-1 text-xs font-semibold transition-colors @lg:px-3.5 @lg:py-1.5 @lg:text-[13px] @2xl:text-sm ${
                  active ? 'text-teal-200' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {active ? (
                  <motion.span
                    layoutId="login-flow-pill"
                    className="absolute inset-0 rounded-full border border-teal-400/40 bg-teal-400/15"
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                  />
                ) : null}
                <span className="relative z-10">{item.label}</span>
              </button>
            );
          })}
        </div>
        <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-teal-300/90 @lg:text-[13px]">
          <Lock size={13} aria-hidden /> RLS Isolated
        </span>
      </div>

      {/* 3-Column Visual Architecture Diagram (container-responsive) */}
      <div className="relative grid grid-cols-1 items-center gap-4 @md:grid-cols-[minmax(0,1fr)_minmax(88px,0.55fr)_minmax(0,1.15fr)] @md:gap-2.5 @lg:gap-4 @xl:gap-5 @2xl:gap-6">
        {/* Animated SVG Data Flow Connectors (horizontal layout) */}
        <svg
          aria-hidden
          viewBox="0 0 420 220"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 hidden h-full w-full @md:block"
        >
          <defs>
            <linearGradient id="flow-grad-a" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(45,212,191,0.12)" />
              <stop offset="50%" stopColor="rgba(94,234,212,0.85)" />
              <stop offset="100%" stopColor="rgba(45,212,191,0.15)" />
            </linearGradient>
          </defs>
          {/* Docs -> Hub */}
          <path d="M 148 37 C 176 37, 174 106, 198 106" fill="none" stroke="rgba(148,163,184,0.2)" strokeWidth="1.5" />
          <path d="M 148 110 L 198 106" fill="none" stroke="rgba(148,163,184,0.2)" strokeWidth="1.5" />
          <path d="M 148 183 C 176 183, 174 106, 198 106" fill="none" stroke="rgba(148,163,184,0.2)" strokeWidth="1.5" />
          {/* Hub -> Answer */}
          <path d="M 218 106 L 252 106" fill="none" stroke="rgba(148,163,184,0.24)" strokeWidth="1.5" />

          {/* Active animated light pulses */}
          <motion.path
            d="M 148 37 C 176 37, 174 106, 198 106"
            fill="none"
            stroke="url(#flow-grad-a)"
            strokeWidth="2.2"
            strokeDasharray="20 120"
            animate={{ strokeDashoffset: [140, 0] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
            opacity={stage === 0 || stage === 1 ? 0.95 : 0.3}
          />
          <motion.path
            d="M 148 110 L 198 106"
            fill="none"
            stroke="url(#flow-grad-a)"
            strokeWidth="2.2"
            strokeDasharray="16 90"
            animate={{ strokeDashoffset: [106, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'linear', delay: 0.35 }}
            opacity={stage === 0 || stage === 1 ? 0.95 : 0.3}
          />
          <motion.path
            d="M 148 183 C 176 183, 174 106, 198 106"
            fill="none"
            stroke="url(#flow-grad-a)"
            strokeWidth="2.2"
            strokeDasharray="20 120"
            animate={{ strokeDashoffset: [140, 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'linear', delay: 0.7 }}
            opacity={stage === 0 || stage === 1 ? 0.85 : 0.25}
          />
          <motion.path
            d="M 218 106 L 252 106"
            fill="none"
            stroke="url(#flow-grad-a)"
            strokeWidth="2.4"
            strokeDasharray="14 60"
            animate={{ strokeDashoffset: [74, 0] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'linear' }}
            opacity={stage === 1 || stage === 2 ? 1 : 0.35}
          />
        </svg>

        {/* Column 1: Workspace SOP Vault */}
        <div className="relative z-10 space-y-2.5 @xl:space-y-3.5 @2xl:space-y-4">
          {DOCS.map((doc, idx) => {
            const Icon = doc.icon;
            const lit = stage === 0 || (stage === 2 && idx === 0);
            return (
              <motion.div
                key={doc.code}
                animate={{
                  borderColor: lit ? 'rgba(94, 234, 212, 0.45)' : 'rgba(255, 255, 255, 0.1)',
                  backgroundColor: lit ? 'rgba(20, 184, 166, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                }}
                transition={{ duration: 0.35 }}
                className="flex items-center justify-between gap-2 rounded-xl border px-3 py-2.5 @xl:px-4 @xl:py-3.5 @2xl:px-4 @2xl:py-4"
              >
                <div className="flex min-w-0 items-center gap-2.5 @xl:gap-3">
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition-colors @xl:h-8 @xl:w-8 @2xl:h-9 @2xl:w-9 ${
                      lit
                        ? 'border-teal-400/35 bg-teal-400/12 text-teal-300'
                        : 'border-white/8 bg-white/[0.04] text-slate-400'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5 @xl:h-4 @xl:w-4" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <span className="block truncate font-mono text-xs font-semibold text-slate-100 @xl:text-[13px] @2xl:text-sm">
                      {doc.code}
                    </span>
                    <span className="hidden text-[10px] text-slate-400 @2xl:block">
                      {doc.type} · Indexed
                    </span>
                  </div>
                </div>
                <span className="shrink-0 rounded-md bg-white/8 px-2 py-0.5 font-mono text-[10px] font-medium text-slate-300 @xl:text-[11px]">
                  {doc.tag}
                </span>
              </motion.div>
            );
          })}
        </div>

        {/* Mobile vertical flow connector (Vault -> Hub) */}
        <div aria-hidden className="flex justify-center @md:hidden">
          <div className="h-5 w-px bg-gradient-to-b from-teal-400/25 via-teal-300/75 to-teal-400/25" />
        </div>

        {/* Column 2: SOPilot Hybrid RAG Hub */}
        <div className="relative z-10 flex flex-col items-center justify-center">
          <motion.div
            animate={{
              scale: stage === 1 ? [1, 1.06, 1] : 1,
              boxShadow:
                stage === 1
                  ? '0 0 36px rgba(20, 184, 166, 0.5)'
                  : '0 0 16px rgba(20, 184, 166, 0.2)',
            }}
            transition={{ duration: 1.1, repeat: stage === 1 ? Infinity : 0 }}
            className="flex h-14 w-14 items-center justify-center rounded-2xl border border-teal-400/45 bg-[#0a1d26] p-1.5 @lg:h-16 @lg:w-16 @lg:p-2 @xl:h-20 @xl:w-20 @xl:p-2.5 @2xl:h-24 @2xl:w-24 @2xl:rounded-3xl @2xl:p-3"
          >
            <BrandMark className="h-full w-full rounded-xl @2xl:rounded-2xl" />
          </motion.div>
          <span className="mt-2 inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-white/10 bg-white/[0.06] px-2 py-0.5 font-mono text-[10px] font-medium text-teal-200 @lg:mt-2.5 @lg:gap-1.5 @lg:px-2.5 @lg:py-1 @lg:text-[11px] @xl:mt-3 @xl:px-3 @xl:text-xs">
            <Sparkles className="h-3 w-3 shrink-0" aria-hidden /> Hybrid RAG
          </span>
        </div>

        {/* Mobile vertical flow connector (Hub -> Answer) */}
        <div aria-hidden className="flex justify-center @md:hidden">
          <div className="h-5 w-px bg-gradient-to-b from-teal-400/25 via-teal-300/75 to-teal-400/25" />
        </div>

        {/* Column 3: Cited Answer + Exact Source Highlight */}
        <motion.div
          animate={{
            borderColor: stage === 2 ? 'rgba(94, 234, 212, 0.5)' : 'rgba(255, 255, 255, 0.1)',
            backgroundColor: stage === 2 ? 'rgba(20, 184, 166, 0.08)' : 'rgba(255, 255, 255, 0.04)',
          }}
          transition={{ duration: 0.35 }}
          className="relative z-10 rounded-xl border p-3.5 @lg:p-4 @xl:p-5 @2xl:p-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-1.5 text-[11px] text-slate-400 @lg:text-xs @xl:text-[13px] @2xl:text-sm">
            <span className="whitespace-nowrap font-semibold text-slate-100">Verified Answer</span>
            <span className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap text-teal-300">
              <ShieldCheck className="h-3.5 w-3.5 @xl:h-4 @xl:w-4" aria-hidden /> Grounded
            </span>
          </div>

          {/* Minimal schematic answer lines with inline citation chips */}
          <div className="mt-3.5 space-y-2.5 @xl:mt-4 @xl:space-y-3">
            <div className="flex items-center gap-2">
              <span className="h-2 flex-1 rounded-full bg-slate-200/75 @xl:h-2.5" />
              <span className="rounded bg-teal-400/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-teal-200 ring-1 ring-teal-400/40 @xl:text-[11px]">
                1
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-4/5 rounded-full bg-slate-300/45 @xl:h-2.5" />
              <span className="rounded bg-teal-400/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-teal-200 ring-1 ring-teal-400/40 @xl:text-[11px]">
                2
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-3/5 rounded-full bg-slate-300/30 @xl:h-2.5" />
            </div>
          </div>

          {/* Highlighted Source Passage Callout */}
          <motion.div
            animate={{ opacity: stage === 2 ? 1 : 0.72, y: stage === 2 ? 0 : 2 }}
            className="mt-4 rounded-lg border-l-2 border-amber-400 bg-amber-400/12 px-3 py-2 @xl:mt-5 @xl:px-3.5 @xl:py-2.5"
          >
            <div className="flex flex-wrap items-center justify-between gap-1 font-mono text-[11px] text-amber-200 @xl:text-xs">
              <span>HR-POL-2026</span>
              <span>p.3 · Highlight</span>
            </div>
          </motion.div>
        </motion.div>
      </div>
      </div>
    </div>
  );
}

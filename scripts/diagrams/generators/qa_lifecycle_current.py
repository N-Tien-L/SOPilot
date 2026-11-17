"""Generator for docs/architecture/diagrams/qa-lifecycle-current.excalidraw (as-built QA lifecycle,
RESEARCH-decision-layer-context-2026-11-16). Run: python scripts/diagrams/generators/qa_lifecycle_current.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/architecture/diagrams"
sys.path.insert(0, str(REPO / "scripts/diagrams"))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

b = ExcalidrawBuilder()
b.add_text("title", 0, 0, "SOPilot QA request lifecycle, as built (ai-service, 2026-11-16)", font_size=28)
b.add_text("sub", 0, 42, "POST /ai/v1/conversations/{id}/messages -> QAService.answer -> run_steps; "
           "first non-continue Decision ends the chain", 16, MUTED)

W, H, GAP = 175, 92, 42
LANE_PAD, LANE_H, LANE_GAP, TOP = 24, 170, 46, 100
lanes = [
    ("Decision layer: deterministic, no LLM (qa/steps.py, qa/router.py)", [
        ("quota", "1 Quota\nreserve (off by\ndefault)", "gray", "solid"),
        ("input", "2 Input\nempty / >1000 chars", "blue", "solid"),
        ("pii", "3 PII mask\nregex", "blue", "solid"),
        ("frame", "4 QueryFrame\nlang, codes,\nfollow-up markers", "blue", "solid"),
        ("guard", "5 Guard\nYAML regex\nblock / flag / abuse", "red", "solid"),
        ("rule", "6 Rule router\nstrip greeting,\nthanks, profanity", "blue", "solid"),
        ("mean", "7 Meaningful\ntokens\n(chunk_terms)", "blue", "solid"),
        ("sem", "8 Semantic router\nbge-m3 exemplars\nflag OFF by default", "yellow", "dashed"),
    ]),
    ("Context + retrieval (conversations/steps.py, retrieval/)", [
        ("hist", "History loader\n(_run, before step 1)\n3 ANSWERED pairs", "teal", "solid"),
        ("rw", "9 Rewrite (LLM)\nalways when history,\nthinking off", "green", "solid"),
        ("ret", "10 Hybrid retrieve\ndense+BM25, RRF,\nrerank, gate", "green", "solid"),
        ("ctx", "11 Build context\nsection expand,\n<=16K tokens", "green", "solid"),
        ("prm", "12 Prompt\nsources + question\n+ original, no history", "green", "solid"),
    ]),
    ("Generation, checks, persistence", [
        ("gen", "13 Generate\nQwen3.5-9B on Modal\nthinking: global flag", "orange", "solid"),
        ("og", "Output guard\ncanary + prompt\necho", "red", "solid"),
        ("cit", "14 Citations\ndrop invalid [n]", "green", "solid"),
        ("selfref", "15 Self-refusal\nfixed opening\nsentence", "green", "solid"),
        ("num", "16 Number check\nflags only", "green", "solid"),
        ("save", "save_turn\none tenant_tx:\nmessages, citations", "teal", "solid"),
    ]),
]

first_ids, last_ids = [], []
for li, (label, boxes) in enumerate(lanes):
    y = TOP + li * (LANE_H + LANE_GAP)
    lane_w = len(lanes[0][1]) * (W + GAP) - GAP + 2 * LANE_PAD
    b.add_box(f"lane{li}", -LANE_PAD, y, lane_w, LANE_H, "", **C["gray"], fill_style="hachure",
              stroke_style="dashed")
    b.add_text(f"lane{li}_t", W + GAP / 2, y + 8, label, 16, MUTED)
    by = y + 52
    for i, (bid, title, color, stroke) in enumerate(boxes):
        b.add_box(bid, i * (W + GAP), by, W, H, title, **C[color], stroke_style=stroke, font_size=14)
    for (a, *_), (z, *_) in zip(boxes, boxes[1:]):
        b.connect(f"{a}_{z}", a, z)
    first_ids.append((boxes[0][0], by))
    last_ids.append((boxes[-1][0], by, len(boxes)))

# Row-to-row links (snake back to the left).
for li in range(len(lanes) - 1):
    last, ly, n = last_ids[li]
    first, fy = first_ids[li + 1]
    x_last = (n - 1) * (W + GAP) + W / 2
    mid_y = ly + H + (LANE_H - 52 - H) + LANE_GAP / 2 + 4
    b.connect(f"row{li}", last, first, via=[(x_last, mid_y), (W / 2, mid_y)])

# Early exits.
y_exit = TOP + 3 * (LANE_H + LANE_GAP) + 10
b.add_box("exit", 0, y_exit, 2 * W + GAP, 70,
          "Early exit: TEMPLATE / REFUSED_GUARD /\nREFUSED_NO_EVIDENCE (no generator call)",
          **C["red"], font_size=14)
b.add_box("db", 3 * (W + GAP), y_exit, W + 60, 70, "Postgres rag schema\nmessages.route / checks\n"
          "standalone_query", **C["teal"], font_size=14)
b.add_box("modal", 4 * (W + GAP) + 80, y_exit, W + 40, 70, "Modal L40S\nvLLM + reranker\n64K context",
          **C["orange"], font_size=14)
b.connect("save_db", "save", "db", stroke_style="dashed")

# Gaps found (yellow notes).
notes_x = 6 * (W + GAP) - 60
b.add_box("gaps", notes_x, y_exit - 10, 2 * W + GAP + 60, 150,
          "Gaps found\n- Decision.CLARIFY declared, never emitted\n- rewrite runs on every turn with history\n"
          "- follow-up signal used only on rewrite fail\n- thinking on/off is process-wide\n"
          "- no multi-turn eval set", **C["yellow"], font_size=14, text_align="left")

b.export(OUT, "qa-lifecycle-current", theme="light")

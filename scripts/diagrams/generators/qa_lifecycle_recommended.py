"""Generator for docs/architecture/diagrams/qa-lifecycle-recommended.excalidraw (recommended QA request
flow, RESEARCH-decision-layer-context-2026-11-16 §7). Run:
python scripts/diagrams/generators/qa_lifecycle_recommended.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/diagrams"))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

b = ExcalidrawBuilder()
b.add_text("title", -560, -150, "Recommended QA request flow (proposal, not implemented)", font_size=28)
b.add_text("sub", -560, -108, "Deterministic first; LLM rewrite only on follow-ups; thinking chosen once, "
           "after retrieval; generator never sees history", 16, MUTED)

W, H, DW, DH, VG = 280, 80, 280, 130, 60
RED = C["red"]["stroke_color"]

# Centre column, top to bottom: (id, kind, title, colour, stroke, height)
spine = [
    ("msg", "box", "User message", "gray", "solid", H),
    ("det", "box", "Deterministic steps\ninput, PII, frame, guard,\nrule router, meaningful tokens", "blue", "solid", 100),
    ("sem", "box", "Semantic router (bge-m3)\ndefault on/off: owner decides", "yellow", "dashed", H),
    ("fu", "diamond", "Follow-up signal?\n(markers, short,\nelliptic opening)", "yellow", "solid", DH),
    ("rw", "box", "Rewrite (LLM, thinking off)\nmay return CANNOT_RESOLVE", "orange", "solid", H),
    ("grw", "box", "Guard block rules\non the rewritten query", "red", "solid", H),
    ("ret", "box", "Hybrid retrieve, rerank, gate\nthrough the access filter", "green", "solid", H),
    ("ctx", "box", "Context builder\nsections, <= 16K tokens", "green", "solid", H),
    ("think", "diamond", "Thinking mode?\nquery + evidence\nsignals", "yellow", "solid", DH),
    ("gen", "box", "Generate (same model)\nconfig key: fast | deliberate", "orange", "solid", H),
    ("post", "box", "Output guard, citations,\nself-refusal, number check,\nfinish_reason", "green", "solid", 100),
    ("save", "box", "save_turn: one tenant_tx\ncontent + standalone_query\n+ route decision trace", "teal", "solid", 100),
]
y = 0
cy = {}
for sid, kind, title, color, stroke, h in spine:
    cy[sid] = y + h / 2
    if kind == "box":
        b.add_box(sid, -W / 2, y, W, h, title, **C[color], stroke_style=stroke, font_size=15)
    else:
        b.add_diamond(sid, 0, y + h / 2, DW, h, title, **C[color], stroke_style=stroke, font_size=14)
    y += h + VG

labels = {("fu", "rw"): "follow-up", ("grw", "ret"): "pass  (hit: use original)",
          ("think", "gen"): "pick config key", ("ret", "ctx"): "above gate"}
for (a, *_), (z, *_) in zip(spine, spine[1:]):
    if (a, z) == ("post", "save"):
        b.connect(f"{a}_{z}", a, z)
        continue
    b.connect(f"{a}_{z}", a, z, label=labels.get((a, z)))

# Right column: early exits, all stored by save_turn.
XR, EW, EH = 300, 260, 76
exits = [
    ("x_tpl", (cy["det"] + cy["sem"]) / 2, "TEMPLATE / REFUSED_GUARD\nno LLM, no retrieval", ["det", "sem"]),
    ("x_clar", (cy["fu"] + cy["rw"]) / 2, "Clarify template\nask for the full question", ["fu", "rw"]),
    ("x_noev", cy["ret"], "REFUSED_NO_EVIDENCE\nnearest documents", ["ret"]),
]
exit_labels = {("fu", "x_clar"): "no usable history", ("rw", "x_clar"): "unresolved",
               ("ret", "x_noev"): "below gate", ("sem", "x_tpl"): "template intent"}
BUS = XR + EW + 50
for eid, ecy, title, sources in exits:
    b.add_box(eid, XR, ecy - EH / 2, EW, EH, title, **C["red"], font_size=14)
    for s in sources:
        b.connect(f"{s}_{eid}", s, eid, label=exit_labels.get((s, eid)), stroke_color=RED,
                  stroke_style="dashed")
    if eid == "x_tpl":  # one arrow down the bus; the other exits join it with plain stubs
        b.connect(f"{eid}_save", eid, "save", via=[(BUS, ecy), (BUS, cy["save"])], stroke_color=RED,
                  stroke_style="dashed")
    else:
        b.add_arrow(f"{eid}_bus", [(XR + EW, ecy), (BUS, ecy)], RED, end_head=None,
                    stroke_style="dashed")

# Left: history loader feeds the follow-up check; standalone path skips the rewrite.
XL = -560
b.add_box("hist", XL, cy["sem"] - 45, 260, 90, "History loader\n3 ANSWERED pairs, revoked hidden\n"
          "loaded only at this point", **C["teal"], font_size=14)
b.connect("hist_fu", "hist", "fu")
SX = -DW / 2 - 60
b.connect("fu_ret", "fu", "ret", label="standalone", via=[(SX, cy["fu"]), (SX, cy["ret"])])

# Notes.
b.add_box("note_rw", XL, cy["rw"] - 20, 260, 130,
          "Rewrite rules\n- only on a follow-up signal\n- history: questions + cited titles\n  "
          "(A/B vs answer text)\n- original query always kept", **C["yellow"], font_size=13,
          text_align="left")
b.add_box("note_think", XR, cy["ctx"] - 10, EW + 40, 150,
          "Thinking selector (deterministic)\n- query: comparison, scenario,\n  dates or amounts\n"
          "- evidence: >= 2 documents/versions,\n  exception wording\n- unsure -> deliberate",
          **C["yellow"], font_size=13, text_align="left")

b.add_text("legend", -560, y + 10, "Legend: blue deterministic | orange LLM on Modal | yellow decision or note | "
           "red guard or early exit (dashed) | green retrieval and checks | teal storage", 14, MUTED)

b.export(REPO / "docs/architecture/diagrams", "qa-lifecycle-recommended", theme="light")

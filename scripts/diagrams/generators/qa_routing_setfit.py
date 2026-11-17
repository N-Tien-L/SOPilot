"""Generator for docs/architecture/diagrams/qa-routing-setfit.excalidraw (QA request flow with the SetFit
routing classifier, ADR-012 / V2-44, proposal). Run: python scripts/diagrams/generators/qa_routing_setfit.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/diagrams"))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

b = ExcalidrawBuilder()
b.add_text("title", -700, -150, "QA request flow with the SetFit router (proposal, ADR-012)", font_size=28)
b.add_text("sub", -700, -108, "The classifier replaces the embedding comparison of the semantic router; rules "
           "stay first; five corpus-dependent labels are left to retrieval", 16, MUTED)

W, H, DW, DH, VG = 300, 80, 300, 140, 56
RED = C["red"]["stroke_color"]

# Centre column, top to bottom: (id, kind, title, colour, stroke, height)
spine = [
    ("msg", "box", "User question\n+ previous turn, if any", "gray", "solid", H),
    ("det", "box", "Deterministic rules (unchanged)\ninput, PII, guard, profanity,\nrule router, meaningful tokens",
     "blue", "solid", 100),
    ("svm", "box", "SetFit router (new, local CPU)\nfine-tuned bge-m3 + logistic head\n"
     "predicts 1 of 14 labels", "green", "solid", 100),
    ("dec", "diamond", "Label routed\nbefore retrieval?", "yellow", "solid", DH),
    ("rw", "box", "Rewrite (LLM) only on a\nfollow-up signal", "orange", "solid", H),
    ("ret", "box", "Hybrid retrieve, rerank, gate\nthrough the access filter", "green", "solid", H),
    ("gen", "box", "Context builder + generate\n(Modal LLM, thinking chosen once)", "orange", "solid", H),
    ("post", "box", "Output guard, citations, number check\n+ disclaimer for some labels", "green", "solid", 100),
    ("save", "box", "save_turn: one tenant_tx\nanswer + route trace (label, confidence)",
     "teal", "solid", 90),
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

labels = {("dec", "rw"): "no: SOP, follow-up\nor deferred label"}
for (a, *_), (z, *_) in zip(spine, spine[1:]):
    b.connect(f"{a}_{z}", a, z, label=labels.get((a, z)))

# Right column: early exits, all stored by save_turn.
XR, EW, EH = 340, 290, 86
exits = [
    ("x_det", cy["det"], "TEMPLATE / REFUSED_GUARD\nrules decide, no LLM, no retrieval", ["det"]),
    ("x_tpl", cy["dec"], "Fixed template, no LLM\ngreeting, thanks, about_bot,\nabuse_only, feedback_in_chat",
     ["dec"]),
    ("x_noev", cy["ret"], "REFUSED_NO_EVIDENCE\nOUT_OF_SCOPE when label = off_topic", ["ret"]),
]
exit_labels = {("dec", "x_tpl"): "yes", ("ret", "x_noev"): "below gate"}
BUS = XR + EW + 50
for eid, ecy, title, sources in exits:
    b.add_box(eid, XR, ecy - EH / 2, EW, EH, title, **C["red"], font_size=14)
    for s in sources:
        b.connect(f"{s}_{eid}", s, eid, label=exit_labels.get((s, eid)), stroke_color=RED,
                  stroke_style="dashed")
    if eid == "x_det":  # one arrow down the bus; the other exits join it with plain stubs
        b.connect(f"{eid}_save", eid, "save", via=[(BUS, ecy), (BUS, cy["save"])], stroke_color=RED,
                  stroke_style="dashed")
    else:
        b.add_arrow(f"{eid}_bus", [(XR + EW, ecy), (BUS, ecy)], RED, end_head=None, stroke_style="dashed")

# Right notes.
b.add_box("note_mode", XR, cy["svm"] - 55, EW + 20, 110,
          "Rollout flag (default off)\nSOPILOT_ROUTER_CLASSIFIER_MODE\noff | shadow | on\n"
          "shadow: label is only recorded\nin messages.route", **C["yellow"], font_size=13, text_align="left")
b.add_box("note_defer", XR, cy["gen"] - 70, EW + 20, 225,
          "Deferred labels travel with the question\n- off_topic: OUT_OF_SCOPE only if\n  the gate refuses\n"
          "- legal_medical, personal_data,\n  action_request: disclaimer after\n  generation\n"
          "- abuse_with_question, about_source:\n  answered as ordinary questions\n"
          "- harmful: rules decide, the\n  classifier alone never blocks",
          **C["yellow"], font_size=13, text_align="left")

# Left: offline training lane feeding the router.
XL, LW = -700, 290
b.add_box("tr_data", XL, cy["msg"] - 40, LW, 90, "train-pool.jsonl 447 rows\n+ 60 router exemplars\n"
          "(test.jsonl never used)", **C["gray"], font_size=14)
b.add_box("tr_modal", XL, cy["det"] - 10, LW, 100, "Modal A100-40GB\n5 folds + final model in parallel\n"
          "about 6 min, modal_setfit_app.py", **C["orange"], font_size=14)
b.add_box("tr_art", XL, cy["svm"] - 20, LW, 130, "Artifact (not in git)\nbody/ 2.3 GB + head.npz\npath in config/models.yaml\n"
          "loaded once: ~2.9 GB RAM\n~100 ms p50 per question (CPU)", **C["green"], font_size=14)
b.connect("tr_data_modal", "tr_data", "tr_modal")
b.connect("tr_modal_art", "tr_modal", "tr_art", label="download")
b.connect("tr_art_svm", "tr_art", "svm", label="load")
b.add_text("tr_lane", XL, cy["msg"] - 80, "Offline training", 16, MUTED)

b.add_text("legend", -700, y + 10, "Legend: blue rules | green local model or retrieval | orange LLM or GPU job | "
           "yellow decision or note | red early exit (dashed) | teal storage", 14, MUTED)

b.export(REPO / "docs/architecture/diagrams", "qa-routing-setfit", theme="light")

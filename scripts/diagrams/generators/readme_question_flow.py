"""Generator for docs/architecture/diagrams/readme-question-flow.excalidraw (one question -> cited answer, for
the root README). Simplified from TECH-V2-ai-service §7.1 (steps 1-12) and system-overview.md §3 flow 4;
the detailed as-built view is qa-lifecycle-current.excalidraw.
Run: python scripts/diagrams/generators/readme_question_flow.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/architecture/diagrams"
sys.path.insert(0, str(REPO / "scripts/diagrams"))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

b = ExcalidrawBuilder()
b.add_text("title", 0, 0, "Question -> cited answer (ai-service)", font_size=30)
b.add_text("sub", 0, 44, "POST /ai/v1/conversations/{id}/messages, answer streamed back over SSE", 18, MUTED)

W, H, GAP = 200, 110, 50
LANE_PAD, LANE_H, LANE_GAP, TOP = 24, 190, 60, 250
lanes = [
    ("Check and prepare the question", [
        ("ask", "1 Question\nfrom the chat UI", "violet"),
        ("inp", "2 Input check\n+ mask personal\ndata (PII)", "green"),
        ("guard", "3 Guard\nprompt injection,\nabuse", "red"),
        ("route", "4 Router\ngreeting, thanks,\nsmall talk", "green"),
        ("rw", "5 Rewrite (LLM)\nfollow-ups only:\nstandalone question", "green"),
    ]),
    ("Find evidence, answer, verify", [
        ("ret", "6 Hybrid retrieval\ndense + BM25, RRF,\noptional rerank", "green"),
        ("gate", "7 Enough\nevidence?", "yellow"),
        ("gen", "8 Generate\nQwen3.5-9B on Modal\nstreamed", "orange"),
        ("cit", "9 Verify\ncitations [n],\nnumbers, dates", "green"),
        ("save", "10 Save turn\nanswer + citations", "teal"),
    ]),
]

lane_w = len(lanes[0][1]) * (W + GAP) - GAP + 2 * LANE_PAD
rows = []
for li, (label, boxes) in enumerate(lanes):
    y = TOP + li * (LANE_H + LANE_GAP)
    b.add_box(f"lane{li}", -LANE_PAD, y, lane_w, LANE_H, "", **C["gray"], fill_style="hachure",
              stroke_style="dashed")
    b.add_text(f"lane{li}_t", 0, y + 10, label, 17, MUTED)
    by = y + 56
    for i, (bid, title, color) in enumerate(boxes):
        x = i * (W + GAP)
        if bid == "gate":
            b.add_diamond(bid, x + W / 2, by + H / 2, W, H + 20, title, **C[color], font_size=17)
        else:
            b.add_box(bid, x, by, W, H, title, **C[color], font_size=17)
    for (a, *_), (z, *_) in zip(boxes, boxes[1:]):
        b.connect(f"{a}_{z}", a, z, label="yes" if a == "gate" else None)
    rows.append(by)

x_last = 4 * (W + GAP) + W / 2
mid_y = rows[0] + H + (LANE_H - 56 - H) + LANE_GAP / 2
b.connect("rw_ret", "rw", "ret", via=[(x_last, mid_y), (W / 2, mid_y)])

# Access filter callout on retrieval.
y_end = TOP + 2 * (LANE_H + LANE_GAP) + 10
b.add_box("acl", -10, y_end, 295, 120, "Only chunks the asker may read:\nsame workspace (RLS + filter)\n"
          "+ department access,\napplied before ranking", **C["blue"], font_size=16, text_align="left")
b.connect("acl_ret", "acl", "ret", stroke_style="dashed")

# Early exits.
gx, rx = 2 * (W + GAP) + W / 2, 3 * (W + GAP) + W / 2      # guard and router centres
b.add_box("tmpl", gx + 30, 95, rx - gx - 60, 100, "Fixed reply\nguard refusal or\ntemplate, no LLM",
          **C["red"], font_size=16)
b.connect("guard_tmpl", "guard", "tmpl", stroke_style="dashed", via=[(gx, 145)])
b.connect("route_tmpl", "route", "tmpl", stroke_style="dashed", via=[(rx, 145)])
gate_x = 1 * (W + GAP) + W / 2
b.add_box("refuse", 2 * (W + GAP) - 20, y_end, 2 * W + GAP + 40, 110,
          "\"Not in your documents\" + closest documents\n-> listed as a knowledge gap for admins",
          **C["red"], font_size=16)
b.connect("gate_refuse", "gate", "refuse", label="no", via=[(gate_x, y_end + 55)])

b.export(OUT, "readme-question-flow", theme="light")

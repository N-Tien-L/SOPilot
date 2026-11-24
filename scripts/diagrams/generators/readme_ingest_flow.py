"""Generator for docs/architecture/diagrams/readme-ingest-flow.excalidraw (upload -> searchable chunks, for
the root README). Source of truth: docs/architecture/system-overview.md §3 (flows 2-3),
docs/architecture/data/document-access-sync.md and TECH-V2-ai-service.
Run: python scripts/diagrams/generators/readme_ingest_flow.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/architecture/diagrams"
sys.path.insert(0, str(REPO / "scripts/diagrams"))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

b = ExcalidrawBuilder()
b.add_text("title", 0, 0, "Upload -> searchable document", font_size=30)
b.add_text("sub", 0, 44, "The upload request returns at step 4; everything after it runs in the background",
           18, MUTED)

W, H, GAP = 200, 110, 50
LANE_PAD, LANE_H, LANE_GAP, TOP = 24, 190, 60, 110
lanes = [
    ("core-api (synchronous, inside the upload request)", [
        ("up", "1 Upload\nadmin or dept.\npublisher", "violet"),
        ("val", "2 Validate\ntype, size,\nSHA-256, quota", "blue"),
        ("s3", "3 Store file\nin MinIO", "teal"),
        ("tx", "4 One DB transaction\nversion row +\nINGEST_REQUESTED", "blue"),
        ("out", "5 Outbox dispatcher\nafter commit,\nretries", "blue"),
    ]),
    ("ai-service + ai-worker (asynchronous)", [
        ("claim", "6 Claim job\nlease + retry", "green"),
        ("ext", "7 Extract\nPDF: Docling\nMarkdown: parser", "green"),
        ("chunk", "8 Clean, Markdown,\nchunk by section", "green"),
        ("emb", "9 Embed\nbge-m3 (local)", "green"),
        ("act", "10 Activate version\none transaction\n(old chunks out)", "teal"),
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
        b.add_box(bid, i * (W + GAP), by, W, H, title, **C[color], font_size=17)
    for (a, *_), (z, *_) in zip(boxes, boxes[1:]):
        b.connect(f"{a}_{z}", a, z)
    rows.append(by)

# Row 1 -> row 2: dispatcher calls ai-service, snake back to the left.
x_last = 4 * (W + GAP) + W / 2
mid_y = rows[0] + H + (LANE_H - 56 - H) + LANE_GAP / 2
b.connect("out_claim", "out", "claim", label="POST /internal/ingestions", via=[(x_last, mid_y), (W / 2, mid_y)])

# Outcome boxes below.
y_end = TOP + 2 * (LANE_H + LANE_GAP) + 10
b.add_box("ready", 3 * (W + GAP), y_end, W + 70, 100, "11 Callback to core-api\nstatus READY or FAILED\n"
          "(shown in the UI)", **C["blue"], font_size=17)
b.add_box("sugg", 4 * (W + GAP) + 110, y_end, W + 40, 100, "12 Metadata suggestions\nrules + Groq\n(optional)",
          **C["orange"], font_size=17, stroke_style="dashed")
b.connect("act_ready", "act", "ready", via=[(4 * (W + GAP) + 40, y_end + 50)])
b.connect("act_sugg", "act", "sugg", stroke_style="dashed")
b.add_box("note", 0, y_end, 2 * (W + GAP) + 80, 100, "New answers search only the ACTIVE version.\n"
          "Re-uploading keeps the old version searchable\nuntil the new one is READY.",
          **C["yellow"], font_size=16, text_align="left")

b.export(OUT, "readme-ingest-flow", theme="light")

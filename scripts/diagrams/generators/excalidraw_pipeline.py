"""Generator for docs/architecture/diagrams/excalidraw-pipeline.excalidraw (sample for the
excalidraw-visualize skill). Run: python scripts/diagrams/generators/excalidraw_pipeline.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

b = ExcalidrawBuilder()
b.add_text("title", 0, 0, "Diagram pipeline: script to docs", font_size=28)
b.add_text("sub", 0, 42, "The agent writes a short generator; it never emits raw scene JSON", 16, MUTED)

W, H, GAP, Y = 210, 90, 70, 110
steps = [
    ("gen", "Generator script\n(~50 lines Python)", "violet"),
    ("scene", "<name>.excalidraw\n+ viewer .html", "blue"),
    ("cap", "capture_diagram.py\nheadless Chromium", "orange"),
    ("img", "assets/<name>.svg\nvector, cropped", "green"),
]
for i, (sid, title, color) in enumerate(steps):
    b.add_box(sid, i * (W + GAP), Y, W, H, title, **C[color])
for (a, _, _), (z, _, _) in zip(steps, steps[1:]):
    b.connect(f"{a}_{z}", a, z)

b.add_box("doc", 2 * (W + GAP) + W / 2 + GAP / 2, Y + 170, W + 60, H, "docs/**/*.md\n![alt](../diagrams/assets/...)",
          **C["gray"])
b.connect("img_doc", "img", "doc", label="embed")
b.add_diamond("check", W / 2 + 60, Y + 215, 190, 110, "check-docs\npasses?", **C["yellow"])
b.connect("doc_check", "doc", "check", label="verify")
b.add_text("ok", W / 2 + 60, Y + 300, "yes: commit .py, .excalidraw, .svg", 14, C["green"]["stroke_color"],
           align="center")
b.connect("check_gen", "check", "gen", label="no: fix", stroke_color=C["red"]["stroke_color"],
          stroke_style="dashed")

b.export(REPO / "docs/architecture/diagrams", "excalidraw-pipeline", theme="light")

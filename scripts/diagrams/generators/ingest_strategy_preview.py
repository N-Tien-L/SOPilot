"""Generator for docs/architecture/diagrams/ingest-strategy-preview.excalidraw: wireframe of the proposed
"Processing report" (detected document type -> chunking strategy -> sample page with chunk regions).
Run: python scripts/diagrams/generators/ingest_strategy_preview.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

b = ExcalidrawBuilder(style="clean")
b.add_text("title", 0, 0, "Processing report: what the user would see after upload", font_size=28)
b.add_text("sub", 0, 42, "Detected type, then the chunking strategy it selects, then a sample page with the chunks outlined",
           16, MUTED)

TOP, CH = 100, 580
CARDS = [("card1", 0, 440), ("card2", 500, 440), ("card3", 1000, 640)]
for cid, x, w in CARDS:
    b.add_box(cid, x, TOP, w, CH, "", **C["gray"], fill_style="solid", rounded=True)
b.add_text("h1", 20, TOP + 14, "1  Detected type", 22)
b.add_text("h2", 520, TOP + 14, "2  Chunking strategy", 22)
b.add_text("h3", 1020, TOP + 14, "3  Sample page, chunks outlined", 22)
b.connect("a12", "card1", "card2")
b.connect("a23", "card2", "card3")

# ---- card 1: the four families, the detected one highlighted --------------------------------
families = [
    ("LEGAL_ARTICLES", "3 or more \"Dieu N\" headings (decrees, circulars)", False),
    ("ISO_PROCEDURE", "2 or more SOP sections (purpose, scope, procedure)\nor a step table", True),
    ("MARKDOWN", "has headings, no special pattern", False),
    ("PROSE", "no headings at all", False),
]
y = TOP + 64
for name, rule, hit in families:
    color = C["green"] if hit else C["gray"]
    b.add_box(f"fam_{name}", 20, y, 400, 72, f"{name}\n{rule}", **color, fill_style="solid",
              stroke_style="solid" if hit else "dashed", font_size=15)
    y += 88
b.add_text("detected", 20, y + 8, "Detected: ISO_PROCEDURE", 18, C["green"]["stroke_color"])
b.add_text("signals", 20, y + 38,
           "Signals shown to the user:\n- section words found: Muc dich, Pham vi, Noi dung\n"
           "- 1 step table (3 rows)\n- language: vi    document code: QT-07", 14, MUTED)

# ---- card 2: the strategy (rules) ------------------------------------------------------------
rules = [
    ("r1", "Cut by heading tree", "one section = one candidate chunk", "blue"),
    ("r2", "Merge short sections", "under 64 tokens joins its next sibling", "blue"),
    ("r3", "Step table: one row = one chunk", "kept whole, never merged", "green"),
    ("r4", "Pack text up to 384 tokens", "hard cap 512, split at a sentence", "blue"),
    ("r5", "Prefix every chunk", "title [code] > section path (what is embedded)", "violet"),
]
y = TOP + 64
for rid, head, sub, color in rules:
    b.add_box(rid, 520, y, 400, 62, f"{head}\n{sub}", **C[color], fill_style="solid", font_size=15)
    y += 74
b.add_text("others_h", 520, y + 6, "Other families, for comparison", 16)
b.add_text("others", 520, y + 32,
           "LEGAL_ARTICLES: one chunk per \"Dieu\", never merged\n"
           "MARKDOWN: heading sections, merge short ones\n"
           "PROSE: paragraphs packed to the token target", 14, MUTED)

# ---- card 3: sample page with chunk regions --------------------------------------------------
PX, PY, PW, PH = 1020, TOP + 60, 600, 380
b.add_box("page", PX, PY, PW, PH, "", bg_color="#ffffff", stroke_color="#868e96", fill_style="solid", rounded=False)

BAR_BG = "#dee2e6"


def bars(prefix, x, y0, w, n, gap=11):
    for i in range(n):
        ww = w if i < n - 1 else w * 0.6
        b.add_box(f"{prefix}{i}", x, y0 + i * gap, ww, 5, "", bg_color=BAR_BG, stroke_color=BAR_BG,
                  fill_style="solid", rounded=True)


RX, RW = PX + 12, 410     # region x and width
LBL = RX + RW + 10        # label column


def region(rid, y0, h, color, label, heading=None, bar_count=0):
    c = C[color]
    b.add_box(rid, RX, y0, RW, h, "", bg_color="#ffffff", stroke_color=c["stroke_color"],
              fill_style="solid", stroke_style="dashed", rounded=False)
    if heading:
        b.add_text(f"{rid}_h", RX + 8, y0 + 6, heading, 13)
    if bar_count:
        bars(f"{rid}_b", RX + 8, y0 + 28, RW - 16, bar_count)
    b.add_text(f"{rid}_l", LBL, y0 + 2, label, 13, c["stroke_color"])


region("c1", PY + 12, 88, "blue", "#1  SECTION\n118 tok\n2 short sections\nmerged", "1. Muc dich    2. Pham vi", 4)
region("c2", PY + 110, 100, "blue", "#2  SECTION\n301 tok\n3. Noi dung", "3. Noi dung", 5)
b.add_text("tbl_h", RX + 8, PY + 218, "4. Quy trinh thuc hien", 13)
b.add_box("tbl_head", RX, PY + 240, RW, 22, "Step      Action      Owner", bg_color="#e9ecef",
          stroke_color="#adb5bd", fill_style="solid", rounded=False, font_size=12, text_align="left")
for i in range(3):
    region(f"s{i}", PY + 266 + i * 36, 32, "green",
           f"#{3 + i}  STEP {i + 1}\n{40 + i * 7} tok", None, 0)
    b.add_text(f"s{i}_t", RX + 8, PY + 273 + i * 36, f"{i + 1}    action text of step {i + 1}...    role", 12, MUTED)

b.add_text("pagenav", PX + 200, PY + PH + 10, "<  page 1 of 4  >", 14, MUTED)

# legend and stats
LY = PY + PH + 44
for i, (color, name) in enumerate([("blue", "SECTION / PROSE"), ("green", "PROCEDURE_STEP"), ("orange", "TABLE (not on this page)")]):
    c = C[color]
    b.add_box(f"lg{i}", PX + i * 200, LY, 22, 14, "", bg_color="#ffffff", stroke_color=c["stroke_color"],
              fill_style="solid", stroke_style="dashed", rounded=False)
    b.add_text(f"lg{i}_t", PX + i * 200 + 30, LY - 2, name, 13, MUTED)
b.add_text("stats", PX, LY + 34, "Whole document: 14 chunks, average 188 tokens, largest 301 of 512", 15)
b.add_text("hint", PX, LY + 62, "Click a chunk: see its section path and the exact text that was embedded", 14, MUTED)

# ---- what it needs ---------------------------------------------------------------------------
NY = TOP + CH + 30
b.add_box("need", 0, NY, 1640, 118,
          "Backend needed (ai-service, read-only, same 404 rule as the content view, FR-25):  "
          "GET .../versions/{id}/chunks\n"
          "returns family + signals, the rules applied, and per chunk: kind, sectionPath, charStart/charEnd, page, tokenCount.\n"
          "The page preview is the canonical Markdown slice from page_index, not a PDF bitmap: chunks carry character offsets, no bounding boxes.",
          **C["yellow"], fill_style="solid", font_size=15, text_align="left")

b.export(REPO / "docs/architecture/diagrams", "ingest-strategy-preview", theme="light")

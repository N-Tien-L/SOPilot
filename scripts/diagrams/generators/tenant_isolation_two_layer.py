"""Generator for docs/architecture/diagrams/tenant-isolation-two-layer.excalidraw (thesis slide,
Vietnamese labels, angular style, full SQL). Run: python scripts/diagrams/generators/tenant_isolation_two_layer.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from excalidraw_builder import ExcalidrawBuilder  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

BLUE = dict(stroke_color="#1D4ED8", bg_color="#EFF6FF")
TEAL = dict(stroke_color="#0F766E", bg_color="#F0FDFA")
AMBER = dict(stroke_color="#B45309", bg_color="#FFFBEB")
RED = dict(stroke_color="#BE123C", bg_color="#FFF1F2")
GRAY = dict(stroke_color="#475569", bg_color="#F8FAFC")
INK = "#475569"

b = ExcalidrawBuilder(style="clean")
NL = "\n"
SQL_IDS = set()


def box(id_, x, y, w, h, text, col, size=14, align="center", sql=False, dashed=False):
    b.add_box(id_, x, y, w, h, text, font_size=size, text_align=align, rounded=False,
              stroke_style="dashed" if dashed else "solid", **col)
    if sql:
        SQL_IDS.add(id_)


# ---- geometry: four rows, pipeline column on the left, detail on the right
PX, PW, PH = 0, 230, 76          # pipeline boxes
DX = 290                         # detail column start
G = 22
R1, R2, R3, R4 = (0, 150), (172, 90), (284, 192), (498, 142)   # (y, h)
mids = [y + h / 2 for y, h in (R1, R2, R3, R4)]

# ---- pipeline (compact, angular)
pipe = [
    ("p1", ["01 · JWT RS256", "wid = 'A' · wdept = 'FINANCE'"], GRAY),
    ("p2", ["02 · TenantTx", "set_config('app.workspace_id')"], GRAY),
    ("p3", ["03 · Lớp 1 · Ứng dụng", "workspace + phòng ban", "lọc trước LIMIT"], BLUE),
    ("p4", ["04 · Lớp 2 · PostgreSQL RLS", "ép workspace_id ngầm", "trong DB (hàng rào cứng)"], TEAL),
]
for (pid, lines, col), m in zip(pipe, mids):
    box(pid, PX, m - PH / 2, PW, PH, NL.join(lines), col, size=14)
for i in range(3):
    b.connect(f"pd{i}", pipe[i][0], pipe[i + 1][0], stroke_color=INK)
for i, ((pid, _, col), m) in enumerate(zip(pipe, mids)):
    b.add_arrow(f"pa{i}", [(PW, m), (DX - 4, m)], stroke_color=col["stroke_color"], end_head="arrow")

# ---- R1: scenario table
b.add_text("h1", DX, 0, "Tình huống: nhân viên Công ty A · Phòng FINANCE hỏi  (4 chunk nằm chung bảng chunks)", 16, INK)
rows = [
    ("chunk 1 · workspace A", "Công khai (PUBLIC)", "✓ Được thấy · cùng công ty, tài liệu công khai", TEAL),
    ("chunk 2 · workspace A", "Riêng phòng FINANCE", "✓ Được thấy · cùng công ty, cùng phòng", TEAL),
    ("chunk 3 · workspace A", "Riêng phòng HR", "✕ Không · khác phòng ban", AMBER),
    ("chunk 4 · workspace B", "Công khai (PUBLIC)", "✕ Không · khác công ty", RED),
]
RH = 30
for i, (c1, c2, c3, col) in enumerate(rows):
    y = 30 + i * (RH + 4)
    box(f"t{i}a", DX, y, 200, RH, c1, GRAY, size=13)
    box(f"t{i}b", DX + 200, y, 220, RH, c2, GRAY, size=13)
    box(f"t{i}c", DX + 420, y, 486, RH, c3, col, size=13, dashed=(i == 3))

# ---- R2: TenantTx
y, h = R2
box("q2", DX, y, 906, h, NL.join([
    "-- 02 · TenantTx: gắn nhãn 'Công ty A' cho giao dịch này",
    "BEGIN;",
    "SELECT set_config('app.workspace_id', 'A', true);",
    "COMMIT;   -- cuối request: nhãn tự xóa (cờ true), không rò qua connection pool",
]), GRAY, size=13, align="left", sql=True)

# ---- R3: Layer 1 SQL + result
y, h = R3
box("q3", DX, y, 580, h, NL.join([
    "-- 03 · Lớp 1: lọc công ty + phòng ban TRƯỚC LIMIT",
    "WITH allowed_chunks AS (",
    "  SELECT c.id, c.content, c.embedding",
    "  FROM chunks c JOIN documents d ON d.id = c.document_id",
    "  WHERE c.workspace_id = 'A'         -- chặn chunk 4 (Công ty B)",
    "    AND ( d.visibility = 'PUBLIC'    -- cho qua chunk 1",
    "       OR d.department = 'FINANCE' ) -- cho qua chunk 2, chặn chunk 3 (HR)",
    ")",
    "SELECT id, content FROM allowed_chunks",
    "ORDER BY embedding <=> :query_vector",
    "LIMIT 10;   -- top-10 chỉ lấy trong các chunk ĐÃ HỢP LỆ",
]), BLUE, size=13, align="left", sql=True)
RX = DX + 580 + 40
b.add_arrow("q3r", [(DX + 580, y + h / 2), (RX - 4, y + h / 2)], stroke_color=BLUE["stroke_color"])
b.add_text("r3t", RX, y, "Kết quả sau Lớp 1", 14, BLUE["stroke_color"])
res = [
    ("✓ chunk 1 · PUBLIC · qua", TEAL, False),
    ("✓ chunk 2 · FINANCE · qua", TEAL, False),
    ("✕ chunk 3 · HR · bị loại", AMBER, False),
    ("✕ chunk 4 · Công ty B · bị loại", RED, True),
]
for i, (t, col, dashed) in enumerate(res):
    box(f"r3{i}", RX, y + 26 + i * 34, 286, 30, t, col, size=13, dashed=dashed)
b.add_text("r3f", RX, y + 26 + 4 * 34 + 4, "→ chỉ chunk 1, 2 vào reranker / LLM", 13, INK)

# ---- R4: Layer 2
y, h = R4
box("q4", DX, y, 410, h, NL.join([
    "-- 04 · Lớp 2: RLS (FORCE RLS, NOBYPASSRLS)",
    "CREATE POLICY tenant_isolation ON chunks",
    "  USING ( workspace_id =",
    "    current_setting('app.workspace_id', true) );",
]), TEAL, size=13, align="left", sql=True)
BX = DX + 410 + 80
b.add_arrow("q4b", [(DX + 410, y + h / 2), (BX - 4, y + h / 2)], stroke_color=RED["stroke_color"],
            stroke_style="dashed")
b.add_text("q4l", DX + 410 + 8, y + h / 2 - 22, "Lớp 1 bug", 12, RED["stroke_color"])
box("q5", BX, y, 906 - 410 - 80, h, NL.join([
    "-- Bug: code app quên WHERE workspace_id",
    "SELECT id, content FROM chunks;",
    "-- PostgreSQL tự chạy thành:",
    "SELECT id, content FROM chunks",
    "WHERE workspace_id = 'A';   -- chunk 4 vẫn bị ẩn",
    "-- Quên cả set_config → NULL → 0 dòng (fail-closed)",
]), RED, size=13, align="left", sql=True)

for e in b.elements:
    if e["id"].endswith("__label") and e["id"][:-7] in SQL_IDS:
        e["fontFamily"] = 8

b.export(REPO / "docs/architecture/diagrams", "tenant-isolation-two-layer", theme="light")

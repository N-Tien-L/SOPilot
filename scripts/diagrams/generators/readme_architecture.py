"""Generator for docs/architecture/diagrams/readme-architecture.excalidraw (V2 components for the root
README). Source of truth: docs/architecture/system-overview.md §1-§2 and docker-compose.yml.
Run: python scripts/diagrams/generators/readme_architecture.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/architecture/diagrams"
sys.path.insert(0, str(REPO / "scripts/diagrams"))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

b = ExcalidrawBuilder()
b.add_text("title", 0, 0, "SOPilot V2 - components", font_size=30)
b.add_text("sub", 0, 44, "Everything inside the dashed frame runs in docker compose (project sopilot-v2)",
           18, MUTED)

TOP = 110
BW, BH = 230, 110          # service box
X_USER, X_WEB, X_SVC, X_DATA = -40, 300, 700, 1080

# Compose frame.
b.add_box("frame", X_WEB - 40, TOP - 20, X_DATA + 300 - (X_WEB - 40), 640, "",
          **C["gray"], fill_style="hachure", stroke_style="dashed")
b.add_text("frame_t", X_WEB - 20, TOP - 8, "docker compose", 16, MUTED)

b.add_box("user", X_USER, TOP + 230, 190, BH, "Browser\nemployee / admin", **C["plain"], font_size=18)
b.add_box("web", X_WEB, TOP + 230, BW, BH, "web  :3000\nNext.js\nsame-origin proxy", **C["violet"],
          font_size=18)

b.add_box("core", X_SVC, TOP + 30, BW, BH, "core-api  :8080\nSpring Boot\nusers, docs, access",
          **C["blue"], font_size=18)
b.add_box("ai", X_SVC, TOP + 230, BW, BH, "ai-service  :8000\nFastAPI\nretrieval, answers",
          **C["green"], font_size=18)
b.add_box("worker", X_SVC, TOP + 430, BW, BH, "ai-worker\nextract, chunk,\nembed (bge-m3)",
          **C["green"], font_size=18)

b.add_box("minio", X_DATA, TOP + 30, 230, BH, "MinIO (S3)\ndocument files", **C["teal"], font_size=18)
b.add_box("pg", X_DATA, TOP + 230, 230, 310, "Postgres 16\n+ pgvector\n\nschema core\nschema rag\n\n"
          "row-level security\nper workspace", **C["teal"], font_size=18)

# External providers, below the frame.
EXT_Y = TOP + 700
b.add_box("modal", X_WEB - 20, EXT_Y, 270, 100, "Modal (GPU, external)\nanswer LLM Qwen3.5-9B\n+ reranker",
          **C["orange"], font_size=17)
b.add_box("groq", X_SVC, EXT_Y, BW, 100, "Groq (optional)\nmetadata suggestions", **C["orange"],
          font_size=17, stroke_style="dashed")

b.connect("u_w", "user", "web", label="HTTPS")
b.connect("w_c", "web", "core", label="/api/v1", via=[(X_WEB + BW / 2, TOP + 85)])
b.connect("w_a", "web", "ai", label="/ai/v1 (SSE)")
b.connect("c_a", "core", "ai", via=[(X_SVC + 70, TOP + 185)])
b.connect("a_c", "ai", "core", via=[(X_SVC + 160, TOP + 185)])
b.add_text("c_a_t", X_SVC - 120, TOP + 170, "outbox events", 15, MUTED)
b.add_text("a_c_t", X_SVC + 172, TOP + 170, "callbacks", 15, MUTED)
b.connect("c_s3", "core", "minio", label="write")
b.connect("c_pg", "core", "pg", label="core", via=[(X_DATA - 45, TOP + 110), (X_DATA - 45, TOP + 260)])
b.connect("a_pg", "ai", "pg", label="rag")
b.connect("wk_pg", "worker", "pg", label="rag")
b.connect("wk_s3", "worker", "minio", label="read", via=[(X_SVC + 180, TOP + 600), (X_DATA + 270, TOP + 600),
                                                          (X_DATA + 270, TOP + 85)])
b.connect("a_modal", "ai", "modal", via=[(X_SVC - 50, TOP + 320),
                                                                      (X_SVC - 50, EXT_Y + 50)])
b.add_text("a_modal_t", X_SVC - 262, TOP + 662, "answers (+ optional rerank)", 15, MUTED)
b.connect("wk_groq", "worker", "groq", stroke_style="dashed", via=[(X_SVC + 60, TOP + 600)])

b.export(OUT, "readme-architecture", theme="light")

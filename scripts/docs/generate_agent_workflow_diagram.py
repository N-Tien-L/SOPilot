"""Generate Excalidraw and standalone HTML diagram for Agent Spec-Driven Workflow.
Demonstrates token-efficient Excalidraw generation via Python script.
"""

from __future__ import annotations

import json
from pathlib import Path


class ExcalidrawBuilder:
    def __init__(self):
        self.elements = []
        self._seed = 1000

    def next_seed(self) -> int:
        self._seed += 7
        return self._seed

    def add_text(
        self,
        elem_id: str,
        x: float,
        y: float,
        text: str,
        font_size: int = 18,
        color: str = "#1e1e1e",
        text_align: str = "left",
        vertical_align: str = "top",
        width: float = 300,
        height: float = 30,
        container_id: str | None = None,
    ) -> dict:
        elem = {
            "id": elem_id,
            "type": "text",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "angle": 0,
            "strokeColor": color,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 2,
            "strokeStyle": "solid",
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "roundness": None,
            "seed": self.next_seed(),
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
            "boundElements": [],
            "updated": 1,
            "link": None,
            "locked": False,
            "text": text,
            "originalText": text,
            "fontSize": font_size,
            "fontFamily": 5,
            "textAlign": text_align,
            "verticalAlign": vertical_align,
            "containerId": container_id,
            "lineHeight": 1.25,
            "autoResize": container_id is None,
        }
        self.elements.append(elem)
        return elem

    def add_box(
        self,
        box_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        stroke_color: str = "#1e1e1e",
        bg_color: str = "transparent",
        stroke_style: str = "solid",
        stroke_width: int = 2,
        title: str | None = None,
        font_size: int = 16,
        text_color: str = "#1e1e1e",
        text_align: str = "center",
    ) -> dict:
        bound_elements = []
        text_elem_id = f"{box_id}_text" if title else None
        if text_elem_id:
            bound_elements.append({"type": "text", "id": text_elem_id})

        box = {
            "id": box_id,
            "type": "rectangle",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "angle": 0,
            "strokeColor": stroke_color,
            "backgroundColor": bg_color,
            "fillStyle": "solid",
            "strokeWidth": stroke_width,
            "strokeStyle": stroke_style,
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "roundness": {"type": 3},
            "seed": self.next_seed(),
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
            "boundElements": bound_elements,
            "updated": 1,
            "link": None,
            "locked": False,
        }
        self.elements.append(box)

        if title:
            # Center text inside container
            self.add_text(
                elem_id=text_elem_id,
                x=x + 10,
                y=y + 10,
                text=title,
                font_size=font_size,
                color=text_color,
                text_align=text_align,
                vertical_align="middle",
                width=width - 20,
                height=height - 20,
                container_id=box_id,
            )
        return box

    def add_arrow(
        self,
        arrow_id: str,
        points: list[list[float]],
        start_x: float,
        start_y: float,
        stroke_color: str = "#1e1e1e",
        stroke_style: str = "solid",
        label: str | None = None,
        label_offset_y: float = -20,
    ) -> dict:
        width = abs(points[-1][0] - points[0][0])
        height = abs(points[-1][1] - points[0][1])
        arrow = {
            "id": arrow_id,
            "type": "arrow",
            "x": start_x,
            "y": start_y,
            "width": width,
            "height": height,
            "angle": 0,
            "strokeColor": stroke_color,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 2,
            "strokeStyle": stroke_style,
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "roundness": {"type": 2},
            "seed": self.next_seed(),
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
            "boundElements": [],
            "updated": 1,
            "link": None,
            "locked": False,
            "points": points,
            "lastCommittedPoint": None,
            "startBinding": None,
            "endBinding": None,
            "startArrowhead": None,
            "endArrowhead": "arrow",
            "elbowed": len(points) > 2,
        }
        self.elements.append(arrow)

        if label:
            mid_x = start_x + (points[-1][0] + points[0][0]) / 2 - 40
            mid_y = start_y + (points[-1][1] + points[0][1]) / 2 + label_offset_y
            self.add_text(
                elem_id=f"{arrow_id}_label",
                x=mid_x,
                y=mid_y,
                text=label,
                font_size=14,
                color=stroke_color,
            )
        return arrow

    def build_scene(self) -> dict:
        return {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": self.elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }


def generate_diagram(dest_dir: Path):
    b = ExcalidrawBuilder()

    # 1. Header
    b.add_text(
        "header_title",
        x=40,
        y=30,
        text="SOPilot: Spec-Driven Agent Execution Architecture",
        font_size=32,
        color="#1e1e1e",
        width=900,
        height=40,
    )
    b.add_text(
        "header_subtitle",
        x=40,
        y=80,
        text="How agents discover ground truth, plan changes, enforce constraints, implement across boundaries, and verify quality gates",
        font_size=18,
        color="#495057",
        width=1200,
        height=25,
    )

    # 2. Stage Columns: 4 Main Swimlanes
    col_w = 300
    gap = 40
    start_x = 40
    stage_y = 130
    stage_h = 710

    # Column 1: Context & Discovery
    c1_x = start_x
    b.add_box("lane1", c1_x, stage_y, col_w, stage_h, stroke_color="#1971c2", bg_color="#f8f9fa", stroke_style="dashed")
    b.add_box("lane1_h", c1_x + 10, stage_y + 10, col_w - 20, 50, stroke_color="#1971c2", bg_color="#d0ebff",
              title="1. Context & Discovery\n(Ground Truth)", font_size=16, text_color="#1864ab")

    b.add_box("c1_b1", c1_x + 15, stage_y + 80, col_w - 30, 110, stroke_color="#1971c2", bg_color="#ffffff",
              title="Global Entry & Rules\n• CLAUDE.md\n• .claude/rules/docs.md\n• English only, author: Owner", font_size=14, text_align="left")

    b.add_box("c1_b2", c1_x + 15, stage_y + 210, col_w - 30, 130, stroke_color="#e03131", bg_color="#fff5f5",
              title="Precedence Hierarchy\n1. Running code & migrations\n2. docs/ specs\n3. Service READMEs\n(Code wins; never guess)", font_size=14, text_align="left")

    b.add_box("c1_b3", c1_x + 15, stage_y + 360, col_w - 30, 140, stroke_color="#1971c2", bg_color="#ffffff",
              title="Authoritative Specs\n• product/ (PRD-V2, FR-xx)\n• architecture/decisions (ADR)\n• architecture/components\n  (TECH-V2-core-api / ai-service)", font_size=14, text_align="left")

    b.add_box("c1_b4", c1_x + 15, stage_y + 520, col_w - 30, 130, stroke_color="#1971c2", bg_color="#ffffff",
              title="Discovery Tools\n• Search ID before words\n• rg 'TECH-V2-* §5'\n• Check Flyway migrations\n• config/models.yaml", font_size=14, text_align="left")

    # Column 2: Spec-First Planning
    c2_x = c1_x + col_w + gap
    b.add_box("lane2", c2_x, stage_y, col_w, stage_h, stroke_color="#6741d9", bg_color="#f8f9fa", stroke_style="dashed")
    b.add_box("lane2_h", c2_x + 10, stage_y + 10, col_w - 20, 50, stroke_color="#6741d9", bg_color="#eebefa",
              title="2. Spec-First Planning\n(Decide Before Code)", font_size=16, text_color="#5f3dc4")

    b.add_box("c2_b1", c2_x + 15, stage_y + 80, col_w - 30, 110, stroke_color="#6741d9", bg_color="#ffffff",
              title="Choose Artifact Type\n• Small fix: No doc / code\n• Hard decision: Draft ADR\n• Multi-ticket: Initiative\n(docs/README.md guide)", font_size=14, text_align="left")

    b.add_box("c2_b2", c2_x + 15, stage_y + 210, col_w - 30, 130, stroke_color="#6741d9", bg_color="#ffffff",
              title="Stable ID & Section Rule\n• Id = highest existing + 1\n• Append new sections\n• NEVER renumber TECH/ADR\n(Code citations permanent)", font_size=14, text_align="left")

    b.add_box("c2_b3", c2_x + 15, stage_y + 360, col_w - 30, 140, stroke_color="#6741d9", bg_color="#ffffff",
              title="Initiative & Tickets\n• execution/initiatives/*/PLAN.md\n• tickets/V2-NN-*.md\n• Total/completed counters\n• Frontmatter metadata", font_size=14, text_align="left")

    b.add_box("c2_b4", c2_x + 15, stage_y + 520, col_w - 30, 130, stroke_color="#ae3ec9", bg_color="#f8f0fc",
              title="Mermaid DAG Integrity\n• Flowchart LR in PLAN.md\n• Must match depends_on 1:1\n• Reverse blocks validated\n• CI blocks any mismatch", font_size=14, text_align="left")

    # Column 3: Implementation & Guardrails
    c3_x = c2_x + col_w + gap
    b.add_box("lane3", c3_x, stage_y, col_w, stage_h, stroke_color="#2f9e44", bg_color="#f8f9fa", stroke_style="dashed")
    b.add_box("lane3_h", c3_x + 10, stage_y + 10, col_w - 20, 50, stroke_color="#2f9e44", bg_color="#b2f2bb",
              title="3. Implementation\n(Boundaries & Safety)", font_size=16, text_color="#2b8a3e")

    b.add_box("c3_b1", c3_x + 15, stage_y + 80, col_w - 30, 110, stroke_color="#2f9e44", bg_color="#ffffff",
              title="Strict Execution Order\n1. DB migration (Flyway)\n2. core-api (Spring Boot)\n3. ai-service (FastAPI)\n4. frontend -> 5. docs", font_size=14, text_align="left")

    b.add_box("c3_b2", c3_x + 15, stage_y + 210, col_w - 30, 130, stroke_color="#e03131", bg_color="#fff5f5",
              title="Mandatory Multi-Tenancy\n• Postgres RLS on current_workspace\n• Explicit workspace_id in SQL\n• TenantTx / tenant_tx bound\n• Dept read check (FR-29)", font_size=14, text_align="left")

    b.add_box("c3_b3", c3_x + 15, stage_y + 360, col_w - 30, 140, stroke_color="#2f9e44", bg_color="#ffffff",
              title="Single Source of Truth\n• Link to existing specs\n• Do NOT copy schemas/code\n• Mark planned as 'planned'\n• Separate planned vs done", font_size=14, text_align="left")

    b.add_box("c3_b4", c3_x + 15, stage_y + 520, col_w - 30, 130, stroke_color="#2f9e44", bg_color="#ffffff",
              title="Service Isolation\n• core: users, workspaces, S3 write\n• rag: chunks, search, S3 read\n• Async outbox sync\n• No cross-schema SQL", font_size=14, text_align="left")

    # Column 4: Verification & Handover
    c4_x = c3_x + col_w + gap
    b.add_box("lane4", c4_x, stage_y, col_w, stage_h, stroke_color="#e8590c", bg_color="#f8f9fa", stroke_style="dashed")
    b.add_box("lane4_h", c4_x + 10, stage_y + 10, col_w - 20, 50, stroke_color="#e8590c", bg_color="#ffe8cc",
              title="4. Verification & Gates\n(Evidence-Based)", font_size=16, text_color="#d9480f")

    b.add_box("c4_b1", c4_x + 15, stage_y + 80, col_w - 30, 110, stroke_color="#e8590c", bg_color="#ffffff",
              title="Docs Validator\n• ./scripts/docs/check-docs.ps1\n• Strict: frontmatter, kinds, IDs\n• Case-sensitive link checks\n• Exit 1 on broken link", font_size=14, text_align="left")

    b.add_box("c4_b2", c4_x + 15, stage_y + 210, col_w - 30, 130, stroke_color="#e8590c", bg_color="#ffffff",
              title="Plan & Ticket Validator\n• plan_check.py (pytest)\n• Ticket counters sync\n• Acyclic DAG verification\n• Handover closure check", font_size=14, text_align="left")

    b.add_box("c4_b3", c4_x + 15, stage_y + 360, col_w - 30, 140, stroke_color="#e8590c", bg_color="#ffffff",
              title="Test Evidence Gate\n• Ticket 'done' requires proof\n• Unit & tenant-isolation suites\n• Quality test reports\n• 'approved/done' = Owner call", font_size=14, text_align="left")

    b.add_box("c4_b4", c4_x + 15, stage_y + 520, col_w - 30, 130, stroke_color="#e8590c", bg_color="#fff9db",
              title="Handoff Protocol\n• If stopping mid-task:\n  docs/handoffs/handoff-*.md\n• Commit SHA, uncommitted state\n• Next steps & owner decisions", font_size=14, text_align="left")

    # Arrows between lanes
    arrow_y1 = stage_y + 135
    arrow_y2 = stage_y + 275
    arrow_y3 = stage_y + 430
    arrow_y4 = stage_y + 585

    b.add_arrow("a_c1_c2", [[0, 0], [gap, 0]], c1_x + col_w, arrow_y1, stroke_color="#6741d9")
    b.add_arrow("a_c2_c3", [[0, 0], [gap, 0]], c2_x + col_w, arrow_y1, stroke_color="#2f9e44")
    b.add_arrow("a_c3_c4", [[0, 0], [gap, 0]], c3_x + col_w, arrow_y1, stroke_color="#e8590c")

    b.add_arrow("a_c1_c2_2", [[0, 0], [gap, 0]], c1_x + col_w, arrow_y3, stroke_color="#6741d9")
    b.add_arrow("a_c2_c3_2", [[0, 0], [gap, 0]], c2_x + col_w, arrow_y3, stroke_color="#2f9e44")
    b.add_arrow("a_c3_c4_2", [[0, 0], [gap, 0]], c3_x + col_w, arrow_y3, stroke_color="#e8590c")

    # Loop back arrow if verification fails
    b.add_arrow(
        "a_loopback",
        [[0, 0], [0, 80], [-(col_w * 2 + gap * 2), 80], [-(col_w * 2 + gap * 2), 10]],
        c4_x + 150,
        stage_y + 650,
        stroke_color="#e03131",
        stroke_style="dashed",
        label="Validation fails -> Fix & Re-verify",
        label_offset_y=60,
    )

    # 3. Bottom Summary Box: Non-Negotiable Agent Rules
    bot_y = stage_y + stage_h + 30
    bot_w = col_w * 4 + gap * 3
    bot_h = 135
    b.add_box("rules_box", start_x, bot_y, bot_w, bot_h, stroke_color="#f59f00", bg_color="#fff9db")
    b.add_box("rules_title", start_x + 15, bot_y + 12, 280, 32, stroke_color="#f59f00", bg_color="#ffe066",
              title="Non-Negotiable Guardrails", font_size=15, text_color="#d9480f")

    summary_text = (
        "1. Author is ALWAYS 'Owner': Never attribute docs or designs to an AI name or tool.\n"
        "2. Code Wins Over Docs: When code and docs disagree, report the mismatch; never silently align either side.\n"
        "3. Immutability of Sections: Never renumber TECH or ADR section numbers (existing migrations and code cite them).\n"
        "4. Strict Evidence: A ticket is never marked 'done' without passing tests and owner approval.\n"
        "5. Pre-Finishing Gate: ./scripts/docs/check-docs.ps1 must output 'docs check passed' before any session completion."
    )
    b.add_text("rules_content", start_x + 25, bot_y + 48, summary_text, font_size=14, color="#1e1e1e", width=bot_w - 50, height=80)

    # Export
    scene = b.build_scene()
    dest_dir.mkdir(parents=True, exist_ok=True)
    excalidraw_path = dest_dir / "agent-spec-driven-workflow.excalidraw"
    html_path = dest_dir / "agent-spec-driven-workflow.html"

    excalidraw_path.write_text(json.dumps(scene, indent=1, ensure_ascii=False), encoding="utf-8")

    html_content = f"""<!doctype html><html><head><meta charset="utf-8"><title>SOPilot Agent Spec-Driven Workflow</title><style>html,body,#root{{margin:0;height:100%}}</style>
<link rel="stylesheet" href="https://esm.sh/@excalidraw/excalidraw@0.18.0/dist/prod/index.css"></head><body><div id="root"></div>
<script>window.EXCALIDRAW_ASSET_PATH="https://esm.sh/@excalidraw/excalidraw@0.18.0/dist/prod/";window.SCENE={json.dumps(scene, ensure_ascii=False)};</script>
<script type="module">
import React from "https://esm.sh/react@19.1.0";
import {{"createRoot"}} from "https://esm.sh/react-dom@19.1.0/client";
import {{"Excalidraw"}} from "https://esm.sh/@excalidraw/excalidraw@0.18.0?deps=react@19.1.0,react-dom@19.1.0";
createRoot(document.getElementById("root")).render(React.createElement(Excalidraw,{{initialData:{{elements:SCENE.elements,appState:{{viewBackgroundColor:"#ffffff"}},scrollToContent:true}},excalidrawAPI:a=>window.api=a}}));
</script></body></html>"""

    html_path.write_text(html_content, encoding="utf-8")
    print(f"SUCCESS: Generated {excalidraw_path} ({len(scene['elements'])} elements, {len(json.dumps(scene))} bytes)")
    print(f"SUCCESS: Generated {html_path}")


if __name__ == "__main__":
    out_dir = Path("docs/architecture/diagrams")
    generate_diagram(out_dir)

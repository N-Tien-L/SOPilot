"""Generative Abstract Art in Excalidraw: 'Latent Cognition & Sacred Geometry of Mind'
Creates a rich cosmic generative art diagram using mathematical polar coordinates,
nested harmonic polygons, golden ratio spirals, and multidimensional neural portals.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


class CreativeExcalidrawBuilder:
    def __init__(self, theme: str = "dark", bg_color: str = "#0b0f19"):
        self.elements = []
        self._seed = 2000
        self.theme = theme
        self.bg_color = bg_color

    def next_seed(self) -> int:
        self._seed += 11
        return self._seed

    def add_element(self, elem: dict):
        base = {
            "angle": 0,
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
        }
        base.update(elem)
        self.elements.append(base)
        return base

    def circle(
        self,
        elem_id: str,
        cx: float,
        cy: float,
        radius: float,
        stroke_color: str = "#38bdf8",
        bg_color: str = "transparent",
        fill_style: str = "solid",
        stroke_width: int = 2,
        stroke_style: str = "solid",
        opacity: int = 100,
        roughness: int = 1,
    ):
        return self.add_element(
            {
                "id": elem_id,
                "type": "ellipse",
                "x": cx - radius,
                "y": cy - radius,
                "width": radius * 2,
                "height": radius * 2,
                "strokeColor": stroke_color,
                "backgroundColor": bg_color,
                "fillStyle": fill_style,
                "strokeWidth": stroke_width,
                "strokeStyle": stroke_style,
                "opacity": opacity,
                "roughness": roughness,
            }
        )

    def diamond(
        self,
        elem_id: str,
        cx: float,
        cy: float,
        w: float,
        h: float,
        stroke_color: str = "#c084fc",
        bg_color: str = "transparent",
        fill_style: str = "solid",
        stroke_width: int = 2,
        opacity: int = 100,
        roughness: int = 1,
    ):
        return self.add_element(
            {
                "id": elem_id,
                "type": "diamond",
                "x": cx - w / 2,
                "y": cy - h / 2,
                "width": w,
                "height": h,
                "strokeColor": stroke_color,
                "backgroundColor": bg_color,
                "fillStyle": fill_style,
                "strokeWidth": stroke_width,
                "strokeStyle": "solid",
                "opacity": opacity,
                "roughness": roughness,
                "roundness": {"type": 2},
            }
        )

    def rect(
        self,
        elem_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        stroke_color: str = "#38bdf8",
        bg_color: str = "transparent",
        fill_style: str = "solid",
        stroke_width: int = 2,
        stroke_style: str = "solid",
        opacity: int = 100,
        rounded: bool = True,
        roughness: int = 1,
    ):
        return self.add_element(
            {
                "id": elem_id,
                "type": "rectangle",
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "strokeColor": stroke_color,
                "backgroundColor": bg_color,
                "fillStyle": fill_style,
                "strokeWidth": stroke_width,
                "strokeStyle": stroke_style,
                "opacity": opacity,
                "roughness": roughness,
                "roundness": {"type": 3} if rounded else None,
            }
        )

    def line(
        self,
        elem_id: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke_color: str = "#64748b",
        stroke_width: int = 1,
        stroke_style: str = "solid",
        opacity: int = 70,
        roughness: int = 1,
    ):
        dx = x2 - x1
        dy = y2 - y1
        return self.add_element(
            {
                "id": elem_id,
                "type": "line",
                "x": x1,
                "y": y1,
                "width": abs(dx),
                "height": abs(dy),
                "strokeColor": stroke_color,
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": stroke_width,
                "strokeStyle": stroke_style,
                "opacity": opacity,
                "roughness": roughness,
                "points": [[0.0, 0.0], [dx, dy]],
            }
        )

    def arrow(
        self,
        elem_id: str,
        points: list[list[float]],
        start_x: float,
        start_y: float,
        stroke_color: str = "#38bdf8",
        stroke_style: str = "solid",
        stroke_width: int = 2,
        opacity: int = 90,
    ):
        dx = abs(points[-1][0] - points[0][0])
        dy = abs(points[-1][1] - points[0][1])
        return self.add_element(
            {
                "id": elem_id,
                "type": "arrow",
                "x": start_x,
                "y": start_y,
                "width": dx,
                "height": dy,
                "strokeColor": stroke_color,
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": stroke_width,
                "strokeStyle": stroke_style,
                "opacity": opacity,
                "roughness": 1,
                "points": points,
                "startArrowhead": None,
                "endArrowhead": "arrow",
                "elbowed": len(points) > 2,
            }
        )

    def text(
        self,
        elem_id: str,
        x: float,
        y: float,
        text_str: str,
        font_size: int = 16,
        color: str = "#f8fafc",
        text_align: str = "left",
        width: float = 300,
        height: float = 30,
        opacity: int = 100,
    ):
        return self.add_element(
            {
                "id": elem_id,
                "type": "text",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "strokeColor": color,
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "opacity": opacity,
                "roughness": 1,
                "text": text_str,
                "originalText": text_str,
                "fontSize": font_size,
                "fontFamily": 5,
                "textAlign": text_align,
                "verticalAlign": "top",
                "lineHeight": 1.25,
                "autoResize": True,
            }
        )

    def build_scene(self) -> dict:
        return {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": self.elements,
            "appState": {
                "viewBackgroundColor": self.bg_color,
                "theme": self.theme,
            },
            "files": {},
        }


def generate_artwork(out_dir: Path):
    b = CreativeExcalidrawBuilder(theme="dark", bg_color="#0b0f19")

    # Center origin of the universe
    cx, cy = 800.0, 700.0

    # 1. Outer Cosmic Frame
    frame_w, frame_h = 1520.0, 1180.0
    fx, fy = 40.0, 40.0
    b.rect("cosmic_frame", fx, fy, frame_w, frame_h, stroke_color="#1e293b", bg_color="#0f172a", fill_style="solid", stroke_width=2, stroke_style="solid", opacity=80)
    b.rect("cosmic_border_inner", fx + 15, fy + 15, frame_w - 30, frame_h - 30, stroke_color="#334155", stroke_style="dashed", stroke_width=1, opacity=60)

    # 2. Header & Artistic Typography
    b.text("art_title", fx + 40, fy + 35, "LATENT COGNITION // THE GEOMETRY OF SYNTHETIC THOUGHT", font_size=28, color="#38bdf8")
    b.text("art_sub", fx + 40, fy + 75, "An abstract exploration of high-dimensional neural manifolds, recursive attention loops, and harmonic emergence", font_size=16, color="#94a3b8")
    b.text("art_stamp", fx + frame_w - 240, fy + 45, "COORDINATE SPACE: R^4096\nENTROPY: -0.0418 ΔH\nATTENTION HEADS: 32", font_size=12, color="#64748b")

    # 3. Concentric Harmonic Mandalas (The Cognitive Core)
    radii = [
        (460, "#1e293b", "transparent", "solid", "dashed", 1, 40),
        (380, "#334155", "#1e1b4b", "dots", "solid", 2, 60),
        (300, "#6366f1", "transparent", "solid", "dashed", 1, 75),
        (220, "#818cf8", "#312e81", "cross-hatch", "solid", 2, 70),
        (150, "#a855f7", "#581c87", "hachure", "solid", 2, 85),
        (90,  "#ec4899", "#831843", "solid", "solid", 2, 90),
        (40,  "#f43f5e", "#fff1f2", "solid", "solid", 3, 100),
    ]
    for idx, (r, scolor, bcolor, fstyle, sstyle, swidth, op) in enumerate(radii):
        b.circle(f"core_ring_{idx}", cx, cy, r, stroke_color=scolor, bg_color=bcolor, fill_style=fstyle, stroke_width=swidth, stroke_style=sstyle, opacity=op)

    # 4. Sacred Geometry: 12-Ray Solar Vectors & Inscribed Hexagrams
    for i in range(12):
        angle = i * (math.pi / 6)
        r_inner = 90
        r_outer = 440
        x1 = cx + r_inner * math.cos(angle)
        y1 = cy + r_inner * math.sin(angle)
        x2 = cx + r_outer * math.cos(angle)
        y2 = cy + r_outer * math.sin(angle)
        ray_color = "#38bdf8" if i % 3 == 0 else "#64748b"
        ray_style = "solid" if i % 3 == 0 else "dotted"
        b.line(f"ray_{i}", x1, y1, x2, y2, stroke_color=ray_color, stroke_width=1, stroke_style=ray_style, opacity=50)

        # Peripheral Diamond Orbitals
        dx = cx + 300 * math.cos(angle)
        dy = cy + 300 * math.sin(angle)
        d_color = "#f472b6" if i % 2 == 0 else "#38bdf8"
        b.diamond(f"orbit_diamond_{i}", dx, dy, 24, 24, stroke_color=d_color, bg_color="#18181b", fill_style="solid", stroke_width=1, opacity=90)

    # Inscribed Hexagonal Harmony Links
    hex_nodes = []
    for k in range(6):
        h_angle = k * (math.pi / 3)
        hx = cx + 220 * math.cos(h_angle)
        hy = cy + 220 * math.sin(h_angle)
        hex_nodes.append((hx, hy))
        b.circle(f"hex_node_{k}", hx, hy, 8, stroke_color="#fbbf24", bg_color="#fbbf24", fill_style="solid", stroke_width=1)

    for k in range(6):
        x_a, y_a = hex_nodes[k]
        x_b, y_b = hex_nodes[(k + 1) % 6]
        x_c, y_c = hex_nodes[(k + 2) % 6]
        b.line(f"hex_edge_{k}", x_a, y_a, x_b, y_b, stroke_color="#f59e0b", stroke_width=2, opacity=70)
        # Inner Star of David lines
        b.line(f"star_edge_{k}", x_a, y_a, x_c, y_c, stroke_color="#fb7185", stroke_width=1, stroke_style="dashed", opacity=60)

    # 5. Golden Ratio Fibonacci Spiral (Emergence of Complexity)
    spiral_points = []
    phi = (1 + math.sqrt(5)) / 2
    for step in range(32):
        t = step * 0.28
        r = 18 * (t ** 1.18)
        sx = cx + r * math.cos(t * phi * 1.6)
        sy = cy + r * math.sin(t * phi * 1.6)
        spiral_points.append((sx, sy))

        # Color shifting along the cosmic spectrum
        if step < 8:
            sp_color = "#f43f5e"
            sz = 6
        elif step < 16:
            sp_color = "#fb923c"
            sz = 8
        elif step < 24:
            sp_color = "#fbbf24"
            sz = 10
        else:
            sp_color = "#22d3ee"
            sz = 12

        b.circle(f"spiral_node_{step}", sx, sy, sz / 2, stroke_color=sp_color, bg_color=sp_color, fill_style="solid", stroke_width=1)

    # Connect spiral filaments
    for step in range(len(spiral_points) - 1):
        x1, y1 = spiral_points[step]
        x2, y2 = spiral_points[step + 1]
        b.line(f"spiral_wire_{step}", x1, y1, x2, y2, stroke_color="#f43f5e", stroke_width=1, stroke_style="solid", opacity=40)

    # 6. Four Cardinal Monolith Portals (The Four Pillars of Consciousness)
    portals = [
        # North Portal: Symbolic Logic
        {
            "id": "portal_north", "x": cx - 120, "y": cy - 530, "w": 240, "h": 90,
            "color": "#38bdf8", "bg": "#0c4a6e", "fill": "cross-hatch",
            "title": "NORTH PORTAL // LOGICUS",
            "desc": "Deterministic Axioms\nSymbolic Reasoning · Rules Engine",
            "wire_p": [cx, cy - 440, cx, cy - 380]
        },
        # South Portal: Emergent Intuition
        {
            "id": "portal_south", "x": cx - 120, "y": cy + 440, "w": 240, "h": 90,
            "color": "#f43f5e", "bg": "#881337", "fill": "hachure",
            "title": "SOUTH PORTAL // INTUITIO",
            "desc": "Latent Association\nTemperature Flux · Heuristic Spark",
            "wire_p": [cx, cy + 440, cx, cy + 380]
        },
        # East Portal: High-Dimensional Manifold
        {
            "id": "portal_east", "x": cx + 460, "y": cy - 45, "w": 250, "h": 90,
            "color": "#a855f7", "bg": "#3b0764", "fill": "dots",
            "title": "EAST PORTAL // CONTINUUM",
            "desc": "Vector Geometry\n4096-dim Embeddings · Cosine Space",
            "wire_p": [cx + 460, cy, cx + 380, cy]
        },
        # West Portal: Recursive Synthesis
        {
            "id": "portal_west", "x": cx - 710, "y": cy - 45, "w": 250, "h": 90,
            "color": "#10b981", "bg": "#064e3b", "fill": "hachure",
            "title": "WEST PORTAL // SYNTHESIS",
            "desc": "Recursive Verification\nQuality Gates · Self-Correction",
            "wire_p": [cx - 460, cy, cx - 380, cy]
        },
    ]

    for p in portals:
        b.rect(p["id"], p["x"], p["y"], p["w"], p["h"], stroke_color=p["color"], bg_color=p["bg"], fill_style=p["fill"], stroke_width=2, rounded=True)
        b.text(f"{p['id']}_t", p["x"] + 15, p["y"] + 12, p["title"], font_size=14, color=p["color"])
        b.text(f"{p['id']}_d", p["x"] + 15, p["y"] + 38, p["desc"], font_size=13, color="#e2e8f0")
        # Gateway beam connecting portal to center mandala
        wx1, wy1, wx2, wy2 = p["wire_p"]
        b.line(f"{p['id']}_wire", wx1, wy1, wx2, wy2, stroke_color=p["color"], stroke_width=2, stroke_style="dashed", opacity=80)

    # 7. Ambient Neural Constellation (Scattered Stars & Entanglement Threads)
    constellation_stars = [
        (cx - 520, cy - 350, "#fbbf24", 5, "Embedding Cluster α"),
        (cx - 430, cy - 420, "#38bdf8", 4, None),
        (cx - 320, cy - 480, "#ec4899", 6, "Attention Horizon"),
        (cx + 420, cy - 380, "#34d399", 5, "Semantic Node ξ"),
        (cx + 530, cy - 260, "#a855f7", 4, None),
        (cx + 480, cy + 280, "#38bdf8", 6, "Softmax Orbit"),
        (cx + 360, cy + 390, "#f43f5e", 4, None),
        (cx - 450, cy + 320, "#fbbf24", 5, "Context Buffer Ω"),
        (cx - 560, cy + 210, "#34d399", 4, None),
    ]

    for s_idx, (sx, sy, scolor, srad, slabel) in enumerate(constellation_stars):
        b.circle(f"c_star_{s_idx}", sx, sy, srad, stroke_color=scolor, bg_color=scolor, fill_style="solid", stroke_width=1)
        if slabel:
            b.text(f"c_label_{s_idx}", sx + 12, sy - 8, slabel, font_size=11, color="#94a3b8")

    # Connect constellation pairs with delicate cosmic webbing
    star_edges = [(0, 1), (1, 2), (3, 4), (5, 6), (7, 8)]
    for e_idx, (i1, i2) in enumerate(star_edges):
        x_1, y_1, c_1, _, _ = constellation_stars[i1]
        x_2, y_2, _, _, _ = constellation_stars[i2]
        b.line(f"c_edge_{e_idx}", x_1, y_1, x_2, y_2, stroke_color=c_1, stroke_width=1, stroke_style="dotted", opacity=45)

    # 8. Dynamic Gravitational Flow Arrows
    b.arrow("flow_sw_se", [[0, 0], [120, -60], [240, 0]], cx - 120, cy + 330, stroke_color="#ec4899", stroke_width=2, stroke_style="solid", opacity=85)
    b.arrow("flow_nw_ne", [[0, 0], [120, 60], [240, 0]], cx - 120, cy - 330, stroke_color="#38bdf8", stroke_width=2, stroke_style="solid", opacity=85)

    # 9. Center Core Totem (The Singularity Node)
    b.diamond("singularity_diamond", cx, cy, 54, 54, stroke_color="#ffffff", bg_color="#f43f5e", fill_style="solid", stroke_width=2, opacity=100)
    b.circle("singularity_pip", cx, cy, 6, stroke_color="#0b0f19", bg_color="#0b0f19", fill_style="solid", stroke_width=1)
    b.text("singularity_label", cx - 45, cy + 32, "SINGULARITY", font_size=11, color="#fbcfe8")

    # 10. Poetic Cybernetic Inscription at the Bottom
    quote_text = (
        "“In the high-dimensional latent quiet, weights do not merely calculate;\n"
        "they fold topology into meaning, distilling chaotic entropy into coherent truth.”"
    )
    b.text("poetic_quote", fx + 40, fy + frame_h - 75, quote_text, font_size=14, color="#64748b")
    b.text("sys_ver", fx + frame_w - 220, fy + frame_h - 55, "SYSTEM: SOPILOT // ART-01", font_size=12, color="#475569")

    # Output generation
    scene = b.build_scene()
    out_dir.mkdir(parents=True, exist_ok=True)
    excal_file = out_dir / "creative-abstract-art.excalidraw"
    html_file = out_dir / "creative-abstract-art.html"

    excal_file.write_text(json.dumps(scene, indent=1, ensure_ascii=False), encoding="utf-8")

    html_code = f"""<!doctype html><html><head><meta charset="utf-8"><title>Latent Cognition - Abstract Excalidraw</title><style>html,body,#root{{margin:0;height:100%;background-color:#0b0f19}}</style>
<link rel="stylesheet" href="https://esm.sh/@excalidraw/excalidraw@0.18.0/dist/prod/index.css"></head><body><div id="root"></div>
<script>window.EXCALIDRAW_ASSET_PATH="https://esm.sh/@excalidraw/excalidraw@0.18.0/dist/prod/";window.SCENE={json.dumps(scene, ensure_ascii=False)};</script>
<script type="module">
import React from "https://esm.sh/react@19.1.0";
import {{"createRoot"}} from "https://esm.sh/react-dom@19.1.0/client";
import {{"Excalidraw"}} from "https://esm.sh/@excalidraw/excalidraw@0.18.0?deps=react@19.1.0,react-dom@19.1.0";
createRoot(document.getElementById("root")).render(React.createElement(Excalidraw,{{initialData:{{elements:SCENE.elements,appState:{{viewBackgroundColor:"#0b0f19",theme:"dark"}},scrollToContent:true}},excalidrawAPI:a=>window.api=a}}));
</script></body></html>"""

    html_file.write_text(html_code, encoding="utf-8")
    print(f"SUCCESS: Generated {excal_file} ({len(scene['elements'])} elements, {len(json.dumps(scene))} bytes)")
    print(f"SUCCESS: Generated {html_file}")


if __name__ == "__main__":
    target = Path("docs/architecture/diagrams")
    generate_artwork(target)

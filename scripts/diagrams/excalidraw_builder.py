"""Token-cheap Excalidraw scene builder for SOPilot docs diagrams.

An agent writes a short generator script that calls this builder, instead of emitting raw
`.excalidraw` JSON. `export()` writes `<name>.excalidraw` (the editable source) and
`<name>.html` (a standalone viewer that `capture_diagram.py` also uses to render PNG/SVG).

Standard library only. Usage from a generator script:

    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # scripts/diagrams
    from excalidraw_builder import ExcalidrawBuilder, C

    b = ExcalidrawBuilder()
    b.add_box("api", 0, 0, 200, 80, "core-api", **C["blue"])
    b.add_box("db", 320, 0, 200, 80, "Postgres", **C["green"])
    b.connect("a1", "api", "db", label="SQL")
    b.export("docs/architecture/diagrams", "example", theme="light")

CLI (inspect a scene without reading its JSON into context):

    python scripts/diagrams/excalidraw_builder.py summary docs/architecture/diagrams/example.excalidraw
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

EXCALIDRAW_VERSION = "0.18.0"
REACT_VERSION = "19.1.0"

# Semantic colours (Excalidraw's open-color palette). Author every diagram with these: the
# dark theme is produced by Excalidraw's own dark-mode filter, so one palette serves both.
C: dict[str, dict[str, str]] = {
    "blue": {"stroke_color": "#1971c2", "bg_color": "#d0ebff"},
    "green": {"stroke_color": "#2f9e44", "bg_color": "#d3f9d8"},
    "violet": {"stroke_color": "#6741d9", "bg_color": "#e5dbff"},
    "orange": {"stroke_color": "#e8590c", "bg_color": "#ffe8cc"},
    "red": {"stroke_color": "#e03131", "bg_color": "#ffe3e3"},
    "yellow": {"stroke_color": "#f08c00", "bg_color": "#fff3bf"},
    "teal": {"stroke_color": "#0c8599", "bg_color": "#c5f6fa"},
    "gray": {"stroke_color": "#495057", "bg_color": "#f1f3f5"},
    "plain": {"stroke_color": "#1e1e1e", "bg_color": "#ffffff"},
    "ghost": {"stroke_color": "#868e96", "bg_color": "transparent"},
}
TEXT = "#1e1e1e"
MUTED = "#495057"

FONTS = {"hand": 5, "clean": 6, "code": 8}  # Excalifont, Nunito, Comic Shanns
FILL_STYLES = {"solid", "hachure", "cross-hatch", "dots"}  # "dots" maps to "zigzag" (closest native style)
LINE_HEIGHT = 1.25


class ExcalidrawBuilder:
    """Collects Excalidraw elements. Coordinates are absolute scene pixels (y grows downward)."""

    def __init__(self, style: str = "hand", roughness: int | None = None, background: str = "#ffffff"):
        if style not in ("hand", "clean"):
            raise ValueError("style must be 'hand' or 'clean'")
        self.font_family = FONTS[style]
        self.roughness = (1 if style == "hand" else 0) if roughness is None else roughness
        self.background = background
        self.elements: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self._seed = 1

    # ------------------------------------------------------------------ internals
    def _base(self, elem_id: str, kind: str, x: float, y: float, w: float, h: float, **kw) -> dict:
        if elem_id in self._by_id:
            raise ValueError(f"duplicate element id: {elem_id}")
        self._seed += 1
        fill = kw.get("fill_style", "solid")
        if fill not in FILL_STYLES:
            raise ValueError(f"fill_style must be one of {sorted(FILL_STYLES)}")
        elem = {
            "id": elem_id, "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
            "strokeColor": kw.get("stroke_color", TEXT),
            "backgroundColor": kw.get("bg_color", "transparent"),
            "fillStyle": "zigzag" if fill == "dots" else fill,
            "strokeWidth": kw.get("stroke_width", 2),
            "strokeStyle": kw.get("stroke_style", "solid"),
            "roughness": kw.get("roughness", self.roughness),
            "opacity": kw.get("opacity", 100),
            "groupIds": [], "frameId": None, "roundness": kw.get("roundness"),
            "seed": self._seed * 7919, "version": 1, "versionNonce": self._seed * 104729,
            "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False,
        }
        self.elements.append(elem)
        self._by_id[elem_id] = elem
        return elem

    @staticmethod
    def _text_size(text: str, font_size: int) -> tuple[float, float]:
        lines = text.split("\n")
        # Estimate only: Excalidraw re-measures text once its fonts load.
        return max(len(line) for line in lines) * font_size * 0.6, len(lines) * font_size * LINE_HEIGHT

    def _text(self, elem_id, x, y, w, h, text, font_size, color, align, valign, container_id=None) -> dict:
        t = self._base(elem_id, "text", x, y, w, h, stroke_color=color)
        t.update({
            "text": text, "originalText": text, "fontSize": font_size, "fontFamily": self.font_family,
            "textAlign": align, "verticalAlign": valign, "containerId": container_id,
            "lineHeight": LINE_HEIGHT, "autoResize": True,
        })
        return t

    def _label(self, shape: dict, title: str | None, font_size: int, color: str, align: str) -> None:
        if not title:
            return
        _, th = self._text_size(title, font_size)
        pad = 8
        x, y, w, h = shape["x"], shape["y"], shape["width"], shape["height"]
        if shape["type"] in ("ellipse", "diamond"):  # usable inner area is smaller
            x, y, w, h = x + w * 0.15, y + h * 0.15, w * 0.7, h * 0.7
        tid = f"{shape['id']}__label"
        self._text(tid, x + pad, y + (h - th) / 2, w - 2 * pad, th, title, font_size, color, align, "middle",
                   container_id=shape["id"])
        shape["boundElements"].append({"type": "text", "id": tid})

    # ------------------------------------------------------------------ shapes
    def add_box(self, id: str, x: float, y: float, w: float, h: float, title: str | None = None,
                bg_color: str = "transparent", stroke_color: str = TEXT, fill_style: str = "solid",
                stroke_style: str = "solid", stroke_width: int = 2, rounded: bool = True,
                font_size: int = 16, text_color: str = TEXT, text_align: str = "center", **kw) -> dict:
        """Rectangle with an optional centred label (use '\\n' for line breaks)."""
        box = self._base(id, "rectangle", x, y, w, h, bg_color=bg_color, stroke_color=stroke_color,
                         fill_style=fill_style, stroke_style=stroke_style, stroke_width=stroke_width,
                         roundness={"type": 3} if rounded else None, **kw)
        self._label(box, title, font_size, text_color, text_align)
        return box

    def add_circle(self, id: str, cx: float, cy: float, r: float, title: str | None = None,
                   bg_color: str = "transparent", stroke_color: str = TEXT, fill_style: str = "solid",
                   font_size: int = 16, text_color: str = TEXT, **kw) -> dict:
        """Circle centred on (cx, cy). For an ellipse pass rx/ry via add_ellipse."""
        return self.add_ellipse(id, cx, cy, r, r, title, bg_color, stroke_color, fill_style, font_size, text_color, **kw)

    def add_ellipse(self, id: str, cx: float, cy: float, rx: float, ry: float, title: str | None = None,
                    bg_color: str = "transparent", stroke_color: str = TEXT, fill_style: str = "solid",
                    font_size: int = 16, text_color: str = TEXT, **kw) -> dict:
        e = self._base(id, "ellipse", cx - rx, cy - ry, 2 * rx, 2 * ry, bg_color=bg_color,
                       stroke_color=stroke_color, fill_style=fill_style, roundness={"type": 2}, **kw)
        self._label(e, title, font_size, text_color, "center")
        return e

    def add_diamond(self, id: str, cx: float, cy: float, w: float, h: float, title: str | None = None,
                    bg_color: str = "transparent", stroke_color: str = TEXT, fill_style: str = "solid",
                    font_size: int = 14, text_color: str = TEXT, **kw) -> dict:
        """Decision diamond centred on (cx, cy)."""
        d = self._base(id, "diamond", cx - w / 2, cy - h / 2, w, h, bg_color=bg_color,
                       stroke_color=stroke_color, fill_style=fill_style, roundness={"type": 2}, **kw)
        self._label(d, title, font_size, text_color, "center")
        return d

    def add_text(self, id: str, x: float, y: float, text: str, font_size: int = 16, color: str = TEXT,
                 align: str = "left") -> dict:
        """Free text whose top-left corner is (x, y) (for align='center', x is the centre)."""
        w, h = self._text_size(text, font_size)
        if align == "center":
            x -= w / 2
        elif align == "right":
            x -= w
        t = self._text(id, x, y, w, h, text, font_size, color, align, "top")
        # Fixed width keeps centre/right alignment stable when Excalidraw re-measures the text.
        t["autoResize"] = align == "left"
        return t

    # ------------------------------------------------------------------ connectors
    def add_arrow(self, id: str, points: list[tuple[float, float]], stroke_color: str = TEXT,
                  label: str | None = None, stroke_style: str = "solid", start_id: str | None = None,
                  end_id: str | None = None, start_head: str | None = None, end_head: str | None = "arrow",
                  font_size: int = 14, curved: bool = False, **kw) -> dict:
        """Arrow through absolute points [(x, y), ...]. Pass start_id/end_id to bind it to shapes,
        start_head/end_head among None, 'arrow', 'triangle', 'dot', 'bar'."""
        if len(points) < 2:
            raise ValueError("an arrow needs at least two points")
        x0, y0 = points[0]
        rel = [[px - x0, py - y0] for px, py in points]
        xs, ys = [p[0] for p in rel], [p[1] for p in rel]
        a = self._base(id, "arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys), stroke_color=stroke_color,
                       stroke_style=stroke_style, roundness={"type": 2} if curved else None, **kw)
        a.update({"points": rel, "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
                  "startArrowhead": start_head, "endArrowhead": end_head, "elbowed": False})
        for key, target in (("startBinding", start_id), ("endBinding", end_id)):
            if target:
                a[key] = {"elementId": target, "focus": 0, "gap": 4}
                self._by_id[target]["boundElements"].append({"type": "arrow", "id": id})
        if label:
            mx, my = self._polyline_midpoint(points)
            lw, lh = self._text_size(label, font_size)
            tid = f"{id}__label"
            self._text(tid, mx - lw / 2, my - lh / 2, lw, lh, label, font_size, stroke_color, "center",
                       "middle", container_id=id)
            a["boundElements"].append({"type": "text", "id": tid})
        return a

    def connect(self, id: str, from_id: str, to_id: str, label: str | None = None, stroke_color: str = MUTED,
                via: list[tuple[float, float]] | None = None, **kw) -> dict:
        """Bound arrow between two shapes, clipped to their outlines. `via` adds bend points."""
        src, dst = self._by_id[from_id], self._by_id[to_id]
        inner = list(via or [])
        first_target = inner[0] if inner else self._center(dst)
        last_source = inner[-1] if inner else self._center(src)
        p0 = self._edge_point(src, first_target)
        p1 = self._edge_point(dst, last_source)
        return self.add_arrow(id, [p0, *inner, p1], stroke_color=stroke_color, label=label,
                              start_id=from_id, end_id=to_id, **kw)

    def group(self, group_id: str, ids: list[str]) -> None:
        """Group elements (and their labels) so they move together in the editor."""
        for i in ids:
            for e in (self._by_id[i], self._by_id.get(f"{i}__label")):
                if e is not None:
                    e["groupIds"].append(group_id)

    # ------------------------------------------------------------------ geometry
    @staticmethod
    def _center(e: dict) -> tuple[float, float]:
        return e["x"] + e["width"] / 2, e["y"] + e["height"] / 2

    def _edge_point(self, e: dict, toward: tuple[float, float], gap: float = 6) -> tuple[float, float]:
        cx, cy = self._center(e)
        dx, dy = toward[0] - cx, toward[1] - cy
        if dx == 0 and dy == 0:
            return cx, cy
        hw, hh = e["width"] / 2 + gap, e["height"] / 2 + gap
        if e["type"] == "ellipse":
            t = 1 / math.sqrt((dx / hw) ** 2 + (dy / hh) ** 2)
        elif e["type"] == "diamond":
            t = 1 / (abs(dx) / hw + abs(dy) / hh)
        else:
            t = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
        return cx + dx * t, cy + dy * t

    @staticmethod
    def _polyline_midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
        if len(points) % 2 == 1:
            return points[len(points) // 2]
        a, b = points[len(points) // 2 - 1], points[len(points) // 2]
        return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2

    # ------------------------------------------------------------------ output
    def scene(self, theme: str = "light") -> dict:
        if theme not in ("light", "dark"):
            raise ValueError("theme must be 'light' or 'dark'")
        return {
            "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
            "elements": self.elements,
            "appState": {"viewBackgroundColor": self.background, "theme": theme, "gridSize": 20},
            "files": {},
        }

    def export(self, output_dir: str | Path, name: str, theme: str = "light", html: bool = True) -> Path:
        """Write <output_dir>/<name>.excalidraw and (optionally) <name>.html. Prints one line per file."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        scene = self.scene(theme)
        src = out / f"{name}.excalidraw"
        src.write_text(json.dumps(scene, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {src.as_posix()} ({len(self.elements)} elements)")
        if html:
            page = out / f"{name}.html"
            page.write_text(viewer_html(scene, name), encoding="utf-8")
            print(f"wrote {page.as_posix()}")
        return src


def viewer_html(scene: dict, title: str) -> str:
    """Standalone viewer. Exposes window.excalidrawAPI and window.ExcalidrawLib for capture."""
    data = json.dumps(scene, ensure_ascii=False).replace("</", "<\\/")
    cdn = f"https://esm.sh/@excalidraw/excalidraw@{EXCALIDRAW_VERSION}"
    deps = f"deps=react@{REACT_VERSION},react-dom@{REACT_VERSION}"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>html,body,#root{{margin:0;height:100%}}</style>
<link rel="stylesheet" href="{cdn}/dist/prod/index.css">
<script>window.EXCALIDRAW_ASSET_PATH="{cdn}/dist/prod/";window.SCENE={data};</script>
</head><body><div id="root"></div>
<script type="module">
import React from "https://esm.sh/react@{REACT_VERSION}";
import {{ createRoot }} from "https://esm.sh/react-dom@{REACT_VERSION}/client?{deps}";
import * as Lib from "{cdn}?{deps}";
window.ExcalidrawLib = Lib;
const s = window.SCENE;
createRoot(document.getElementById("root")).render(React.createElement(Lib.Excalidraw, {{
  initialData: {{ elements: s.elements, files: s.files || {{}}, appState: s.appState, scrollToContent: true }},
  theme: (s.appState && s.appState.theme) || "light",
  excalidrawAPI: (api) => {{ window.excalidrawAPI = api; }},
}}));
</script></body></html>
"""


def summary(path: Path) -> str:
    scene = json.loads(path.read_text(encoding="utf-8"))
    els = [e for e in scene.get("elements", []) if not e.get("isDeleted")]
    counts: dict[str, int] = {}
    for e in els:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    if not els:
        return f"{path.as_posix()}: empty scene"
    x0 = min(e["x"] for e in els)
    y0 = min(e["y"] for e in els)
    x1 = max(e["x"] + e["width"] for e in els)
    y1 = max(e["y"] + e["height"] for e in els)
    kinds = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    theme = scene.get("appState", {}).get("theme", "light")
    return f"{path.as_posix()}: {len(els)} elements ({kinds}); bbox {x1 - x0:.0f}x{y1 - y0:.0f}; theme {theme}"


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "summary":
        for p in sys.argv[2:]:
            print(summary(Path(p)))
    else:
        print(__doc__)

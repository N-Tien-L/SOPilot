"""Render an Excalidraw diagram to a cropped SVG (default) or high-resolution PNG.

    python scripts/diagrams/capture_diagram.py docs/architecture/diagrams/<name>.excalidraw
    python scripts/diagrams/capture_diagram.py docs/architecture/diagrams/<name>.html --format png --theme dark

Input: a `.excalidraw` scene (a temporary viewer page is generated) or a viewer `.html` written by
excalidraw_builder.py. Default output: docs/architecture/diagrams/assets/<name>.svg (<name>-dark.<fmt> when
--theme dark overrides the scene). The crop is the elements' bounding box plus --padding; PNG uses --scale
(default 3x). A dark SVG has its colours rewritten so it stays dark in viewers that ignore CSS filters.

Requires Node.js and the local Excalidraw clone with its Playwright install (EXCALIDRAW_TOOLS_DIR or
--tools-dir, default C:/Users/Tien/Workspace/Personal/tools/excalidraw) and network access to esm.sh.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
from excalidraw_builder import viewer_html  # noqa: E402

DEFAULT_TOOLS = Path(os.environ.get("EXCALIDRAW_TOOLS_DIR", r"C:\Users\Tien\Workspace\Personal\tools\excalidraw"))
DEFAULT_ASSETS = REPO / "docs" / "architecture" / "diagrams" / "assets"


_DARK_FILTER_RE = re.compile(r'\s+filter="invert\(93%\) hue-rotate\(180deg\)"')
_HEX_RE = re.compile(r'(?<=["\':\s])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])')


def _dark_color(hex_color: str) -> str:
    """Apply CSS `invert(93%) hue-rotate(180deg)` (Excalidraw's dark theme) to one sRGB colour."""
    h = hex_color if len(hex_color) == 6 else "".join(c * 2 for c in hex_color)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    r, g, b = (0.93 * (1 - c) + 0.07 * c for c in (r, g, b))
    cos, sin = math.cos(math.pi), math.sin(math.pi)
    m = [
        (0.213 + cos * 0.787 - sin * 0.213, 0.715 - cos * 0.715 - sin * 0.715, 0.072 - cos * 0.072 + sin * 0.928),
        (0.213 - cos * 0.213 + sin * 0.143, 0.715 + cos * 0.285 + sin * 0.140, 0.072 - cos * 0.072 - sin * 0.283),
        (0.213 - cos * 0.213 - sin * 0.787, 0.715 - cos * 0.715 + sin * 0.715, 0.072 + cos * 0.928 + sin * 0.072),
    ]
    out = (min(1.0, max(0.0, row[0] * r + row[1] * g + row[2] * b)) for row in m)
    return "#" + "".join(f"{round(c * 255):02x}" for c in out)


def bake_dark_svg(svg: str) -> str:
    """Excalidraw marks a dark SVG with a root `filter="invert(...)"` attribute, which Word, Inkscape and
    several Markdown viewers ignore. Rewrite every colour instead so the file is dark everywhere."""
    if not _DARK_FILTER_RE.search(svg):
        return svg
    svg = _DARK_FILTER_RE.sub("", svg, count=1)
    # <mask> contents are luminance stencils (arrow-label cut-outs), not visible colours: leave them as is.
    parts = re.split(r"(<mask\b.*?</mask>)", svg, flags=re.DOTALL)
    return "".join(p if p.startswith("<mask") else _HEX_RE.sub(lambda m: _dark_color(m.group(1)), p) for p in parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path, help=".excalidraw or viewer .html")
    p.add_argument("--out", type=Path, help="output file (default: docs/architecture/diagrams/assets/<name>.<fmt>)")
    p.add_argument("--format", choices=("svg", "png"), default="svg",
                   help="svg (default): vector, fonts embedded, sharp at any zoom; png for targets without SVG")
    p.add_argument("--theme", choices=("auto", "light", "dark"), default="auto", help="auto = the scene's theme")
    p.add_argument("--scale", type=float, default=3.0, help="pixel ratio for PNG (default 3)")
    p.add_argument("--padding", type=int, default=20, help="padding around the bounding box, scene px")
    p.add_argument("--tools-dir", type=Path, default=DEFAULT_TOOLS)
    p.add_argument("--timeout", type=int, default=90, help="seconds")
    a = p.parse_args()

    src = a.input.resolve()
    if not src.is_file():
        print(f"capture: input not found: {src}", file=sys.stderr)
        return 2
    node = shutil.which("node")
    if not node:
        print("capture: Node.js is not on PATH", file=sys.stderr)
        return 2

    name = src.stem
    out = (a.out or DEFAULT_ASSETS / f"{name}{'-dark' if a.theme == 'dark' else ''}.{a.format}").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="excalidraw-capture-") as tmp:
        if src.suffix.lower() == ".excalidraw":
            page = Path(tmp) / f"{name}.html"
            page.write_text(viewer_html(json.loads(src.read_text(encoding="utf-8")), name), encoding="utf-8")
        elif src.suffix.lower() in (".html", ".htm"):
            page = src
        else:
            print("capture: input must be .excalidraw or .html", file=sys.stderr)
            return 2
        cmd = [node, str(HERE / "capture_diagram.mjs"), "--html", str(page), "--out", str(out),
               "--format", a.format, "--scale", str(a.scale), "--padding", str(a.padding),
               "--theme", a.theme, "--tools-dir", str(a.tools_dir.resolve()),
               "--timeout", str(a.timeout * 1000)]
        try:
            res = subprocess.run(cmd, timeout=a.timeout + 30)
        except subprocess.TimeoutExpired:
            print(f"capture: timed out after {a.timeout + 30}s", file=sys.stderr)
            return 1
    if res.returncode == 0:
        if a.format == "svg":
            out.write_text(bake_dark_svg(out.read_text(encoding="utf-8")), encoding="utf-8")
        try:
            rel = out.relative_to(REPO).as_posix()
        except ValueError:
            rel = out.as_posix()
        print(f"output: {rel}")
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())

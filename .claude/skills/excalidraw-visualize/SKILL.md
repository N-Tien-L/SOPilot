---
name: excalidraw-visualize
description: Draw a hand-drawn style Excalidraw diagram for human readers of SOPilot docs (architecture, sequence, state machine, flow, ERD) with a short Python generator script, export it headless to a cropped vector SVG (or high-res PNG), and embed it in reader-facing docs/**/*.md. Use when asked to visualize, draw or redraw something as Excalidraw ("vẽ sơ đồ", "thay Mermaid bằng Excalidraw", "xuất ảnh sơ đồ"). Not for tickets, PLAN.md or other agent-facing files (those keep Mermaid/text), and not for previewing an existing file in the Excalidraw app (skill excalidraw-preview).
---

# Visualize with Excalidraw

Pipeline: generator script → `.excalidraw` + viewer `.html` → headless export → `assets/<name>.svg` → Markdown embed → `check-docs`. Example output: [excalidraw-pipeline.svg](../../../docs/architecture/diagrams/assets/excalidraw-pipeline.svg) (do not open it to follow this skill).

| Piece | Path |
|---|---|
| Builder library (stdlib only) | `scripts/diagrams/excalidraw_builder.py` |
| Export CLI | `scripts/diagrams/capture_diagram.py` (drives `capture_diagram.mjs`) |
| Generator scripts, one per diagram | `scripts/diagrams/generators/<name_snake>.py` |
| Example generator | `scripts/diagrams/generators/excalidraw_pipeline.py` |
| Editable sources | `docs/architecture/diagrams/<name>.excalidraw` (+ `<name>.html` viewer) |
| Exported images | `docs/architecture/diagrams/assets/<name>.svg` (or `.png`) |

## 0. Who reads it decides the form

| Audience | Files | Diagram form |
|---|---|---|
| Agents | tickets, `PLAN.md`, handoffs, `.claude/**`, `CLAUDE.md` | **Mermaid or text only** (lists, tables, ids, `depends_on`). No images: an agent cannot grep or diff a picture, and reading one costs tokens without giving exact names. `check-docs.ps1` also parses the `PLAN.md` Mermaid DAG against the tickets. |
| Humans only | `docs/portfolio/`, research write-ups, README overviews | Excalidraw image alone. |
| Both | `docs/architecture/**` designs and ADRs, `docs/product/`, `docs/operations/` (agents use them as specs) | Excalidraw image for readers, and keep the Mermaid (or a short text list of the same edges) right under it inside `<details><summary>Diagram source (text)</summary> … </details>`, so agents still get exact names. |

When unsure, treat the file as "Both".

## Hard rules (token budget)

- **Never write, print, paste or `Read` raw `.excalidraw` JSON or the exported SVG.** Create and change diagrams only by editing and re-running the generator. Inspect a scene with `python scripts/diagrams/excalidraw_builder.py summary <file>.excalidraw` (counts and bounding box).
- To look at the result, export a PNG preview to the session scratchpad (`--format png --out <scratchpad>/preview.png`) and `Read` that.
- Labels in English (repo rule); keep each box to 1–3 short lines.

## 1. Decide what to show

- Read the source of truth first (code, design section, migration). The diagram illustrates a fact that lives elsewhere: link that source next to the image (one source of truth).
- Pick the form: **architecture** (tiers, left→right request flow), **sequence** (actor boxes on top, dashed lifelines via `add_arrow(..., end_head=None, stroke_style="dashed")`, numbered horizontal arrows top→bottom), **state** (ellipses + labelled transitions), **flow** (boxes + diamonds for decisions), **ERD** (boxes titled `table\n─────\ncol type`, `style="clean"`).
- Colour by meaning, consistently: `C["blue"]` core-api, `C["green"]` ai-service, `C["violet"]` frontend, `C["teal"]` Postgres/MinIO, `C["orange"]` external providers, `C["red"]` failures/denials, `C["gray"]` lanes and containers, `C["yellow"]` decisions/notes.
- **Theme: your call, per diagram.** Always author with the light palette `C`; the theme is set in `export(theme=...)` and Excalidraw derives the dark colours. Choose:
  - `light` for anything that may be printed or pasted into the NCKH report/slides, ERDs and dense diagrams, and pages that already use light images (stay consistent within a page).
  - `dark` for portfolio/showcase visuals, or a page whose other images are dark.
  - State the choice and the reason in one line of your report.
- Style: `ExcalidrawBuilder()` is hand-drawn (Excalifont, roughness 1); `ExcalidrawBuilder(style="clean")` gives Nunito and straight lines for dense diagrams.

## 2. Write and run the generator

Copy `scripts/diagrams/generators/excalidraw_pipeline.py`. Lay out on a grid (constants for width, height, gap) and derive positions from loops, not hand-typed coordinates. API (absolute scene px, y down):

```python
b = ExcalidrawBuilder(style="hand")                      # or "clean"
b.add_box(id, x, y, w, h, title, bg_color, stroke_color, fill_style="solid|hachure|cross-hatch|dots",
          stroke_style="solid|dashed|dotted", rounded=True, font_size=16, text_align="center")
b.add_circle(id, cx, cy, r, title, ...)   b.add_ellipse(id, cx, cy, rx, ry, title, ...)
b.add_diamond(id, cx, cy, w, h, title, ...)
b.add_text(id, x, y, text, font_size=16, color=TEXT, align="left|center|right")
b.add_arrow(id, [(x1, y1), (x2, y2), ...], stroke_color, label=None, start_id=None, end_id=None,
            start_head=None, end_head="arrow", stroke_style="solid", curved=False)
b.connect(id, from_id, to_id, label=None, via=[(x, y), ...])   # bound arrow clipped to both outlines
b.group(group_id, [ids])                                       # move together in the editor
b.export(REPO / "docs/architecture/diagrams", "<name>", theme="light|dark")  # .excalidraw + .html
```

`**C["blue"]` passes `stroke_color` + `bg_color`. `name` is kebab-case. Run: `python scripts/diagrams/generators/<name_snake>.py`.

## 3. Export (sharpest output, exact crop)

```powershell
python scripts/diagrams/capture_diagram.py docs/architecture/diagrams/<name>.excalidraw    # -> assets/<name>.svg
```

- Export goes through Excalidraw's own `exportToSvg`/`exportToBlob`, not a screenshot: the crop is exactly the elements' bounding box plus `--padding` (20 scene px), and the scene's theme is used.
- **SVG is the default**: vector (sharp at any zoom), the font subset embedded, typically 10× smaller than the PNG. A dark SVG gets its colours rewritten, so it stays dark in viewers that ignore CSS filters.
- Use `--format png` (3× by default, `--scale` to change) only for a target that cannot show SVG (Word/thesis export, slides) and for previews.
- Requirements: Node.js on PATH; the local Excalidraw clone (`C:\Users\Tien\Workspace\Personal\tools\excalidraw`, override with `EXCALIDRAW_TOOLS_DIR` or `--tools-dir`) with `node_modules/playwright` and a Playwright Chromium in `%LOCALAPPDATA%\ms-playwright`; network access to `esm.sh` (Excalidraw 0.18.0). "Excalidraw did not start" usually means no network.

Check a PNG preview (see Hard rules), fix overlaps, clipped labels or crossing arrows in the generator, re-run 2–3. Two passes are normal.

## 4. Store and embed

- Commit together: the generator, `<name>.excalidraw`, `<name>.html` and `assets/<name>.svg`.
- Embed with a relative link and descriptive alt text, then name the editable source, e.g. from `docs/architecture/components/core-api.md`:
  `![Upload flow from core-api to ai-service](../diagrams/assets/<name>.svg)` then `Source: [<name>.excalidraw](../diagrams/<name>.excalidraw)`, then the `<details>` text block when the file is "Both" (step 0).
- Replacing a Mermaid block in a "Both" file: keep the section number and prose, put the image above, move the Mermaid into `<details>`. Never touch the `PLAN.md` DAG.
- No `.md` file inside `docs/architecture/diagrams/`: that folder has no document kind and `check-docs` rejects it.
- Hand-edited in the Excalidraw app (skill `excalidraw-preview`)? The `.excalidraw` is now the source: say so in the generator docstring (or delete the generator) and re-export with step 3.

## 5. Verify

```powershell
./scripts/docs/check-docs.ps1     # must print "docs check passed" (relative links, case-sensitive paths)
```

Report: files written, the export line (`svg, WxH, N elements`), the theme chosen and why, check-docs result, and that a preview was inspected.

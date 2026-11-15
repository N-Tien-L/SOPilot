"""Generator for docs/architecture/diagrams/v2-15-wireframes.excalidraw (V2-15 screen skeletons).
Run: python scripts/diagrams/generators/v2_15_wireframes.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from excalidraw_builder import MUTED, ExcalidrawBuilder, C  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

b = ExcalidrawBuilder()
b.add_text("title", 0, 0, "SOPilot V2-15 wireframes (skeleton only)", font_size=28)
b.add_text("sub", 0, 40, "Layout and content blocks, not visual design", 16, MUTED)

GAY = C["gray"]
BLUE, GREEN, ORANGE, RED, YELLOW, VIOLET = (C[k] for k in ("blue", "green", "orange", "red", "yellow", "violet"))


def frame(fid, x, y, w, h, label):
    b.add_text(f"{fid}_l", x, y - 28, label, 18, MUTED)
    b.add_box(fid, x, y, w, h, "", **GAY, rounded=True)


# ---- Row 1 ----
Y1, H1, W1, G = 110, 340, 340, 30
x1, x2, x3, x4 = 0, W1 + G, 2 * (W1 + G), 3 * (W1 + G)

frame("f1", x1, Y1, W1, H1, "1. Sign-in")
b.add_circle("f1o", x1 + W1 / 2, Y1 + 50, 25, "", **BLUE)
b.add_text("f1t", x1 + W1 / 2, Y1 + 90, "SOPilot", 24, align="center")
b.add_text("f1s", x1 + W1 / 2, Y1 + 130, "Ask your SOPs. Get cited answers.", 14, MUTED, align="center")
b.add_box("f1b", x1 + 60, Y1 + 175, 220, 50, "Sign in with Google", **BLUE)
b.add_box("f1d", x1 + 60, Y1 + 245, 220, 44, "Dev sign-in (local only)", stroke_style="dashed")

frame("f2", x2, Y1, W1, H1, "2. Workspace picker")
b.add_text("f2t", x2 + 20, Y1 + 15, "Choose a workspace", 20)
for i, name in enumerate(["Acme Ops  -  OWNER", "Warehouse team  -  MEMBER", "HR handbook  -  ADMIN"]):
    b.add_box(f"f2r{i}", x2 + 20, Y1 + 60 + i * 65, 300, 52, name)
b.add_box("f2n", x2 + 20, Y1 + 260, 300, 44, "+ Create workspace", stroke_style="dashed")

X3 = 2 * (W1 + G)
frame("f3", X3, Y1, 560, H1, "3. Workspace settings (FR-03; PATCH/DELETE /workspaces/current)")
b.add_text("f3t", X3 + 20, Y1 + 12, "Workspace settings", 20)
b.add_box("f3ty", X3 + 330, Y1 + 12, 70, 30, "TEAM", font_size=14, **BLUE)
b.add_box("f3ro", X3 + 410, Y1 + 12, 130, 30, "Your role: OWNER", font_size=14, **VIOLET)
b.add_text("f3n", X3 + 20, Y1 + 52, "Name (OWNER edits; ADMIN/MEMBER read-only)", 14, MUTED)
b.add_box("f3i", X3 + 20, Y1 + 76, 330, 40, "Acme Ops")
b.add_box("f3r", X3 + 365, Y1 + 76, 175, 40, "Rename", **BLUE)
b.add_text("f3u", X3 + 20, Y1 + 130, "Usage: 12 / 50 documents, 80 / 200 MB  (needs an API field: unverified)", 14, MUTED)
b.add_box("f3l", X3 + 20, Y1 + 162, 250, 40, "Leave workspace", font_size=14, stroke_style="dashed")
b.add_text("f3lh", X3 + 285, Y1 + 168, "blocked for the last OWNER\nand PERSONAL workspaces", 14, MUTED)
b.add_box("f3z", X3 + 20, Y1 + 220, 520, 105, "", **RED)
b.add_text("f3zt", X3 + 35, Y1 + 228, "Danger zone", 16, RED["stroke_color"])
b.add_box("f3d", X3 + 35, Y1 + 258, 230, 50, "Delete workspace", **RED)
b.add_text("f3dh", X3 + 280, Y1 + 260, "OWNER only. Type the name\nto confirm. PERSONAL cannot\nbe deleted (409): button off.", 14, MUTED)


def table(pid, x, y, cols, rows, rh=38, fs=14, tint=None):
    cx = x
    for j, (t, w) in enumerate(cols):
        b.add_box(f"{pid}h{j}", cx, y, w, rh, t, font_size=fs, rounded=False, **VIOLET)
        cx += w
    for i, r in enumerate(rows):
        cx = x
        for j, (t, w) in enumerate(cols):
            kw = (tint or {}).get((i, j), {})
            b.add_box(f"{pid}r{i}c{j}", cx, y + rh * (i + 1), w, rh, r[j], font_size=fs, rounded=False, **kw)
            cx += w


# ---- Row 2: main shell + chat ----
Y2 = Y1 + H1 + 90
CW, CH = 1000, 560
frame("c0", 0, Y2, CW, CH, "5. Main shell + chat (core screen)")
b.add_box("cbar", 0, Y2, CW, 44, "SOPilot   |   Workspace: Acme Ops  v                          Avatar  v", **VIOLET)
b.add_box("cnav", 0, Y2 + 44, 140, CH - 44, "", **GAY)
for i, n in enumerate(["Chat", "Documents", "Members", "Gaps", "Settings"]):
    kw = BLUE if i == 0 else {}
    b.add_box(f"cn{i}", 10, Y2 + 60 + i * 48, 120, 38, n, **kw)
b.add_box("clist", 140, Y2 + 44, 220, CH - 44, "", **GAY)
b.add_box("cl0", 150, Y2 + 58, 200, 40, "+ New chat", **BLUE)
for i, n in enumerate(["PPE policy ...", "Leave request ...", "Fire drill steps ..."]):
    b.add_box(f"cl{i + 1}", 150, Y2 + 110 + i * 50, 200, 42, n, font_size=14)
b.add_text("clh", 250, Y2 + CH - 50, "rename / delete per chat\nvisible to creator only", 14, MUTED, align="center")

MX = 380
b.add_box("u1", 690, Y2 + 62, 290, 42, "What is the PPE policy?", **BLUE)
b.add_box("a1", MX, Y2 + 120, 580, 150, "", bg_color="#ffffff")
b.add_text("a1t", MX + 15, Y2 + 132, "Answer streams in here, with inline markers [1] [2] [3]", 16)
b.add_box("a1c1", MX + 15, Y2 + 190, 150, 36, "[1] SOP-Safety p.4", font_size=14, **GREEN)
b.add_box("a1c2", MX + 175, Y2 + 190, 150, 36, "[2] Handbook p.12", font_size=14, **GREEN)
b.add_box("a1c3", MX + 335, Y2 + 190, 230, 36, "[3] Old version (no viewer)", font_size=14, **ORANGE)
b.add_text("a1f", MX + 15, Y2 + 238, "thumbs up  /  thumbs down  /  optional comment", 14, MUTED)
b.add_box("w1", MX, Y2 + 285, 580, 36, "Check the figures against the source  (done.warnings)", font_size=14, **YELLOW)
b.add_box("r1", MX, Y2 + 335, 580, 110, "", **ORANGE)
b.add_text("r1t", MX + 15, Y2 + 347,
           "Refusal NO_EVIDENCE: nothing found in your SOPs\nClosest documents:  [SOP-Safety]  [Onboarding]\n"
           "OUT_OF_SCOPE / INPUT_INVALID: same card, no document list", 14)
b.add_box("ci", MX, Y2 + CH - 70, 480, 46, "Ask a question about your SOPs...")
b.add_box("cs", MX + 490, Y2 + CH - 70, 90, 46, "Send", **BLUE)

# ---- Row 2 right: knowledge gaps ----
RX = CW + 40
frame("g0", RX, Y2, 720, 430, "6. Knowledge gaps (FR-17; GET /knowledge-gaps, resolve)")
b.add_text("g0t", RX + 20, Y2 + 12, "Knowledge gaps", 20)
b.add_text("g0n", RX + 20, Y2 + 44, "OWNER/ADMIN only (MEMBER gets 403, so the nav item is hidden)", 14, MUTED)
b.add_box("g0a", RX + 20, Y2 + 78, 130, 36, "Open (3)", font_size=14, **BLUE)
b.add_box("g0b", RX + 160, Y2 + 78, 130, 36, "Resolved", font_size=14)
table("g", RX + 20, Y2 + 130,
      [("Question (PII masked)", 400), ("Flagged as", 130), ("Action", 150)],
      [("How do I request overtime?", "Refused", "Resolve"),
       ("Forklift licence renewal?", "Downvoted", "Resolve"),
       ("Visitor badge for [email]?", "Refused", "Resolve")])
b.add_box("g0i", RX + 20, Y2 + 306, 430, 40, "Optional note, then Mark resolved", font_size=14, stroke_style="dashed")
b.add_box("g0s", RX + 460, Y2 + 306, 160, 40, "Mark resolved", font_size=14, **BLUE)
b.add_text("g0f", RX + 20, Y2 + 360,
           "limit / offset paging.  No asker identity is shown (the API masks it).\n"
           "Assumed, not in the API doc: 'Flagged as' and any date column.\n"
           "Filling a gap = tell the department publisher outside the app (ADR-009 5).", 14, MUTED)

# ---- Row 3: documents ----
Y3 = Y2 + CH + 90
DW = 1150
frame("d0", 0, Y3, DW, 390, "4. Documents (FR-07, FR-26, FR-27; upload = V2-31, viewer = V2-32)")
b.add_text("d0t", 20, Y3 + 12, "Documents", 20)
b.add_box("d0c", 20, Y3 + 50, 150, 36, "Category  v", font_size=14)
b.add_box("d0g", 180, Y3 + 50, 150, 36, "Tag  v", font_size=14)
b.add_box("d0s", 340, Y3 + 50, 150, 36, "Status  v", font_size=14)
b.add_box("d0u", DW - 190, Y3 + 50, 170, 36, "+ Upload (V2-31)", font_size=14, stroke_style="dashed")
ST = {"Ready": GREEN, "Processing": YELLOW, "Failed": RED}
rows = [
    ("SOP-Safety.pdf", "PDF", "Safety", "ppe, fire", "Workspace", "Ready", "v3", "An N.  11-10", "Download"),
    ("Onboarding.md", "MD", "HR", "new-hire", "Dept: HR", "Processing", "v1", "Tien L.  today", "-"),
    ("Fire-drill.pdf", "PDF", "Safety", "fire", "Workspace", "Failed", "v2", "An N.  11-12", "Retry"),
    ("Leave-policy.pdf", "PDF", "HR", "leave", "Dept: HR, Ops", "Ready", "v1", "An N.  11-02", "Download"),
]
tint = {(i, 5): ST[r[5]] for i, r in enumerate(rows)}
table("d", 20, Y3 + 104,
      [("Title", 200), ("Type", 60), ("Category", 110), ("Tags", 120), ("Visibility", 140), ("Status", 120),
       ("Ver", 60), ("Uploaded by", 160), ("Action", 110)], rows, rh=40, tint=tint)
b.add_text("d0f", 20, Y3 + 104 + 40 * 5 + 15,
           "Processing = UPLOADED or PROCESSING; the list polls while any row is Processing.   Failed: fixed failure sentence per code, Retry reprocesses the same file.\n"
           "Cursor paging: Load more.   Members see masked departments.   12 / 50 documents (quota default).   Row click opens detail (V2-32).", 14, MUTED)

# ---- Row 4: members + invitations ----
Y4 = Y3 + 390 + 90
frame("m0", 0, Y4, DW, 320, "7a. Members (FR-22; GET /members, PATCH, suspend, delete)")
b.add_text("m0t", 20, Y4 + 12, "Members", 20)
table("m", 20, Y4 + 52,
      [("Name", 130), ("Email", 190), ("Employee ID", 120), ("Job title", 130), ("Department", 130), ("Role", 90),
       ("Status", 100), ("Actions", 220)],
      [("Tien L.", "tien@acme.com", "E-001", "Ops lead", "Operations", "OWNER", "Active", "Edit"),
       ("An N.", "an@acme.com", "E-014", "HR admin", "HR", "ADMIN", "Active", "Edit | Suspend"),
       ("Binh T.", "binh@acme.com", "-", "Picker", "Warehouse", "MEMBER", "Suspended", "Reactivate | Remove")],
      tint={(2, 6): ORANGE, (0, 5): VIOLET})
b.add_text("m0f", 20, Y4 + 52 + 38 * 4 + 14,
           "OWNER/ADMIN only.  Only an OWNER can make or change an OWNER (403 for ADMIN).  The last OWNER cannot be removed (409 LAST_OWNER).\n"
           "Employee ID is unique per workspace (409 EMPLOYEE_CODE_TAKEN).  Departments are flat and managed in V2-33.", 14, MUTED)

IX = DW + 40
frame("i0", IX, Y4, 640, 320, "7b. Invitations (FR-04; GET/POST/DELETE /invitations)")
b.add_text("i0t", IX + 20, Y4 + 12, "Invitations", 20)
b.add_box("i0n", IX + 480, Y4 + 8, 140, 36, "+ Invite", font_size=14, **BLUE)
table("i", IX + 20, Y4 + 52,
      [("Email", 190), ("Role", 80), ("Dept", 100), ("Status", 130), ("Action", 100)],
      [("new@acme.com", "MEMBER", "HR", "Pending, 6d", "Revoke"),
       ("old@acme.com", "ADMIN", "Ops", "Expired", "Revoke")],
      tint={(0, 3): YELLOW, (1, 3): RED})
b.add_text("i0f", IX + 20, Y4 + 52 + 38 * 3 + 14,
           "Link valid 7 days, single use, revocable.\nAccepting needs the same Google email as the invitation\n(409 INVITATION_EMAIL_MISMATCH).", 14, MUTED)

DX = IX + 640 + 40
frame("v0", DX, Y4, 400, 430, "7c. Invite dialog (POST /invitations)")
b.add_text("v0t", DX + 20, Y4 + 12, "Invite a member", 20)
for i, (lbl, kw) in enumerate([("Email *", {}), ("Role *   MEMBER  v", {}), ("Employee ID (optional)", {"stroke_style": "dashed"}),
                               ("Job title (optional)", {"stroke_style": "dashed"}), ("Department (optional)  v", {"stroke_style": "dashed"})]):
    b.add_box(f"v0f{i}", DX + 20, Y4 + 52 + i * 52, 360, 42, lbl, font_size=14, **kw)
b.add_box("v0b", DX + 20, Y4 + 322, 360, 44, "Create invitation", **BLUE)
b.add_box("v0l", DX + 20, Y4 + 376, 360, 40, "inviteUrl (shown once)   Copy", font_size=14, **YELLOW)

b.export(REPO / "docs/architecture/diagrams", "v2-15-wireframes", theme="light")

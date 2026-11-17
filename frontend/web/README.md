# SOPilot web (`frontend/web`)

Next.js 16 (App Router), React 19, TypeScript strict, Tailwind 4, used as a **client-rendered app** ([ADR-010](../../docs/architecture/decisions/adr-010-frontend-stack.md)). Design and constraints: [frontend.md](../../docs/architecture/components/frontend.md). Rules for changes: [.claude/rules/frontend.md](../../.claude/rules/frontend.md).

Implemented (V2-38): same-origin proxy, API client, in-memory session, SSE client, TanStack Query, Vitest. Implemented (V2-15): Google and dev sign-in, shell and navigation, workspace picker and settings, chat with citations, documents list, members (read-only) and knowledge gaps. Implemented (V2-31, V2-32): multi-document upload and the recognized-content viewer (below). In review (V2-33): member, department, category, invitation, publisher and audit-log administration and the document metadata and access dialog (below).

## Run

```powershell
cd frontend/web
pnpm install
pnpm dev          # http://localhost:3000
```

core-api and ai-service must be running (see [local development](../../docs/operations/local-development.md)). Backend targets are **run-time** server-side variables read by `proxy.ts`; copy `.env.example` to your own env file and adjust if the defaults (`http://localhost:8080`, `http://localhost:8000`) do not fit.

| Variable | Used by | Meaning |
|---|---|---|
| `CORE_API_URL` | `proxy.ts` (run time) | core-api base URL; receives `/api/v1/**` |
| `AI_SERVICE_URL` | `proxy.ts` (run time) | ai-service base URL; receives `/ai/v1/**` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | build time | Google sign-in button on `/login` (decided in V2-15: stays build time, local only); empty shows a notice and leaves the dev sign-in |

core-api's `SOPILOT_FRONTEND_ORIGIN` must equal the origin of the page (`http://localhost:3000` for `pnpm dev` and for the compose `web` service); refresh and logout check the `Origin` header.

The browser only talks to its own origin. There is no `NEXT_PUBLIC_API_URL`.

A request body above 25 MB is rejected by Next itself with a 500 before it reaches core-api (whose limit is 20 MB and which answers `413 FILE_TOO_LARGE`), so upload code must check the size on the client first.

## Scripts

| Command | Purpose |
|---|---|
| `pnpm build` | production build (standalone output; type-checks under `strict`) |
| `pnpm lint` | ESLint, zero errors expected |
| `pnpm test` | Vitest unit tests (`**/*.test.ts`, Node environment) |

Repo-level: `./scripts/validate-build.ps1 -Scope web` runs build, lint and test.

## Layout

| Path | Contents |
|---|---|
| `proxy.ts`, `lib/server/proxy-target.ts` | same-origin proxy to core-api and ai-service; `next.config.ts` sets `compress: false` (SSE must not be buffered) and `experimental.proxyClientMaxBodySize` above core-api's 20 MB upload limit |
| `lib/api/` | the only `fetch` caller: core-api adapter (envelope, errors, `traceId`), ai-service adapter (plain JSON, `{detail}`), contract types |
| `lib/session/` | in-memory access token, refresh single-flight (Web Locks, `BroadcastChannel` fallback), dev login, switch workspace, sign-out |
| `lib/sse/` | SSE parser, `streamAnswer` (fetch stream with defined end states), answer reducer, open-stream registry |
| `lib/query/` | TanStack Query v5 client, workspace-scoped keys, `resetWorkspaceState` |
| `store/session-store.ts` | Zustand session view (user, workspace); memory only |
| `providers/` | `QueryProvider`, `SessionProvider` (restores the session from the HttpOnly cookie) |
| `app/(app)/`, `components/app/`, `components/chat/`, `lib/chat/` | V2-15 screens, shell, chat and its pure logic |
| `lib/upload/`, `store/upload-store.ts`, `components/documents/` | V2-31 upload: `queue.ts` (pure state machine: 10 files per batch, 3 in flight, per-file state and retry), `failure.ts` (API error → message and action), `validate.ts` (client type and size check), `controller.ts` (requests and polling, outside React), the store, and `UploadDialog` / `UploadManager` mounted in the `(app)` layout |
| `lib/viewer/`, `components/viewer/`, `app/(app)/documents/[id]/` | V2-32 viewer: `offsets.ts` (pure code point ↔ UTF-16 mapping, page segments; Vitest with emoji), `labels.ts` (version notice, warning text), `ContentViewer` (shared by the document page and the citation dialog), `SafeMarkdown` (no raw HTML), `CitationViewerModal` |
| `lib/admin/`, `components/admin/`, `app/(app)/members/`, `app/(app)/audit/`, `app/invite/` | V2-33 administration: pure rules in `metadata.ts` (document patch, form validation, `planAccess`), `members.ts` (role and action rules), `audit.ts` (labels), `invite.ts` (token from the link fragment); panels for members, invitations, departments and categories (`NamedListPanel`), publishers; the audit page and the public `/invite` route |
| `components/documents/MetadataDialog.tsx` | V2-33 document details: metadata form with source labels and suggestions, and the access section |
| `lib/api/endpoints.ts`, `lib/query/hooks.ts` | typed endpoint calls and workspace-keyed queries |
| `components/ui/` | carried-over CSS-module primitives, frozen; new UI is Tailwind 4 on the tokens in `app/globals.css` (V2-15 decision) |

## Upload behaviour (V2-31)

- One `POST /api/v1/documents` per file (no batch endpoint), at most 10 files per batch and 3 requests in flight. Files are checked in the browser first (PDF or Markdown, at most 20 MB); a refused file is listed as failed with its own reason and takes a slot until removed or replaced.
- The batch lives in the `(app)` layout, not in the dialog: closing the dialog never cancels an upload, and a small button reopens it. The browser's leave-page warning is on only while a file is uploading or waiting to be sent. A workspace switch or sign-out aborts the batch (R7) and asks for confirmation first while files are still being sent.
- After the upload only "Processing" is shown. Status polling (`GET /documents/{id}`, rounds 3 s apart, never overlapping) runs only while some file is processing and gives up after 5 failed reads (the row offers Retry). The documents list has its own 5 s refresh while any listed document is not finished.
- Failure actions follow TECH-V2-core-api §5.5: network error → Resend; transient error → Retry; content error → Replace file or Remove. For a stored document that failed while processing, Retry calls `POST /documents/{id}/retry`, Replace file uploads a new version, Delete asks for confirmation.
- Uploads are `WORKSPACE`-visible with no category or tags (department visibility and metadata are V2-33). The Upload button shows only for the workspace publisher (`GET /members/me` → `publisherOf.workspace`); the server stays the authority.
- A duplicate links to the existing document's page (`/documents/<id>`). `lib/upload/guard.ts` holds the leave prompt; the shared `Modal` traps and restores keyboard focus.

## Recognized content and the citation viewer (V2-32)

- `/documents/<id>` ("Content recognized by the system", FR-31) opens only when the document has a current version. It shows the canonical Markdown the system indexed, "Page N" markers for PDFs, warnings only when the API returns them, removed header/footer blocks in a collapsed list, the sentence that `READY` is not "checked", and "Version N is used for Q&A; version N+1 is processing / failed to process" when the latest version differs. There is no editor.
- The original PDF is the browser's native viewer in an iframe at `#page=N`, loaded **on demand** (the first "Show original PDF" or "Page N" click asks core-api for a signed URL; it is reused until about 20 s before it expires). No PDF library. On a narrow screen the PDF and the text are two tabs and a "Page N" click switches to the PDF.
- The citation viewer (`Open in document` under an expanded source in chat) is the same `ContentViewer` in a dialog. It converts the citation's code point offsets to UTF-16 on the canonical Markdown (`citationRange`) and marks the covered blocks in the formatted view and the exact range in the "Markdown source" view. An old-version citation shows only the stored passage and the label and never calls the viewer.
- No access, an unknown id, a document not `READY` and a replaced version all end in one "not available" screen (the API answers `404`).
- The viewer asks for `download-url?disposition=inline` (the "Download original" button keeps the default attachment). In compose core-api reaches MinIO as `minio:9000`, so it signs download links with `SOPILOT_S3_PUBLIC_ENDPOINT` (compose sets `http://localhost:59000`, or `V2_MINIO_API_PORT`); a core-api run from source with `SOPILOT_S3_ENDPOINT=http://localhost:59000` needs no extra setting.

## Administration and document metadata (V2-33)

- `/members` (OWNER and ADMIN) has tabs Members, Invitations, Departments, Categories and (OWNER only) Publishers. Departments, and the department fields in forms, are hidden in a personal workspace and while the workspace has one member. `/audit` (OWNER only, nav item "Audit log") lists `GET /audit-logs` with action, actor and date filters and cursor paging. The UI hides what the role cannot do; every refusal from the API is shown in context with its fixed message and trace id.
- Member profile: full name, employee code, job title, department, role. A role change ends that member's sessions (the form says so). Suspend, reactivate and remove ask for confirmation; your own row offers only Edit (no suspend or remove), and an admin gets none on an owner.
- Invitations: the created link (`/invite#token=...`) is shown **once** in a dialog with a copy button; the list never shows it again. `/invite` is public: it reads the token from the URL fragment, removes it from the address bar, and keeps it in memory only (a signed-out visitor is sent to sign-in and back). Accepting a link, or a pending invitation of the signed-in account (header badge "N invitations" -> `/invite`), switches the session to the new workspace.
- Departments and categories are flat lists: create, rename, archive/restore, delete (refused by the server while something uses the item; archiving stays available).
- Document details (`Edit` on `/documents` rows and on `/documents/<id>`, only for the responsible publisher of the document, and for an OWNER, who may still transfer it; an ADMIN gets the read-only view). One form pre-filled from the document, each field with its source (`fieldSources`); an empty title keeps the current one (the key is not sent); description and at least one tag are required in the UI, a category only when the workspace has categories ([V2-25](../../docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-25-async-metadata-suggestion.md) section 2a). Document code, revision and effective date are read-only ("extracted automatically, may be wrong"). A suggested title is offered with a button; a suggested **new** category is created by OWNER/ADMIN with one button (`POST /categories`), publishers see it as text. Suggestions never block anything: the dialog is optional, and a document still processing or FAILED says so.
- Access ("Who can read this"): a publisher changes the reader departments inside the same scope (`PUT /documents/{id}/visibility`, the owning department stays). Switching between the whole workspace and departments, or moving to another owning department, is a transfer of responsibility that only an OWNER does (`PUT /documents/{id}/ownership`, [ADR-009](../../docs/architecture/decisions/adr-009-department-publishers.md) decision 8); other roles see why the button is disabled. `lib/admin/metadata.ts` `planAccess` decides which call is made.

## Docker

The image is built from `Dockerfile` (standalone `node server.js`) and needs `CORE_API_URL` and `AI_SERVICE_URL` at run time. `docker-compose.yml` sets them to the compose service names.

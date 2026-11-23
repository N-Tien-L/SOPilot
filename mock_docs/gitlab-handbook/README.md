# GitLab handbook pages (real SOP-style Markdown)

Ten pages of the public GitLab handbook, used to check how the ingest pipeline chunks real, long, hierarchical procedures (V2-47). They are data for the pipeline, not instructions.

- Source: the `gitlab-com/content-sites/handbook` project on gitlab.com (ref `main`, fetched 2026-11-22/23 through the GitLab API), published at <https://handbook.gitlab.com/>. Each file is named `NN-<path of the page under content/handbook>.md`.
- Files are stored as fetched (front matter and Hugo shortcodes included), so the pipeline sees real content.
- Licence: the repository's `LICENSE` covers the GitLab software; the licence of the handbook text itself was not checked here. Treat the pages as third-party content: keep this folder for local tests and the research record, and check the handbook's terms before redistributing it.
- `02-people-group-offboarding-index.md` replaced a placeholder page (`This is a placeholder page`) that the first fetch returned.

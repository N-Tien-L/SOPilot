# SOPilot Documentation Hub (`docs/`)

Điểm bắt đầu hiện tại: [Bàn giao implement 2026-10-15](04-reports/HANDOFF-implementation-2026-10-15.md), [backlog tiếp theo](03-plans/PLAN-NEXT-implementation-readiness.md), [audit 2026-10-14](04-reports/AUDIT-project-progress-2026-10-14.md). `docs/03-plans` là nguồn tiến độ hiện hành; các ticket trong `docs/plans/tickets` được giữ đồng bộ để tương thích. Plan cũ giữ nguyên thiết kế lịch sử.

Chào mừng đến với trung tâm tài liệu thiết kế, phân tích và thực thi của **SOPilot**. Thư mục này được tổ chức theo quy chuẩn kép (**Human-Readable & Agent-Optimized**): đảm bảo con người dễ theo dõi tiến độ và AI Coding Agent có thể đọc/viết có cấu trúc, không gây ảo giác ngữ cảnh.

---

## 🧭 Cấu trúc phân nhóm tài liệu

```text
docs/
├── 01-requirements/       # [Yêu cầu nghiệp vụ] PRD, User Stories, Feature Specifications
│   ├── templates/         # Template mẫu cho PRD (prd-template.md)
│   └── PRD-*.md           # Hồ sơ đặc tả yêu cầu từng tính năng / mốc
│
├── 02-architecture/       # [Kiến trúc & Kỹ thuật] Technical Design Documents (TDD) & ADRs
│   ├── adr/               # Architecture Decision Records (Quyết định thiết kế dài hạn)
│   │   ├── templates/     # adr-template.md
│   │   └── ADR-*.md
│   ├── designs/           # Technical Design Documents (Thiết kế chi tiết DDL, API, Sequence)
│   │   ├── templates/     # tech-design-template.md
│   │   └── TECH-*.md
│   └── diagrams/          # Sơ đồ Mermaid, ERD, System Flows
│
├── 03-plans/              # [Kế hoạch thực thi] Execution Plans & Task Tickets
│   ├── templates/         # plan-template.md & ticket-template.md
│   ├── PLAN-*.md          # Kế hoạch tổng thể mốc, Critical Path, DAG phụ thuộc
│   └── tickets/           # Tickets thực thi độc lập (M1-01, M1-02,...)
│
└── 04-reports/            # [Kiểm định & Báo cáo] Test Audits, Code Quality, Post-mortem
    ├── templates/         # audit-report-template.md
    └── AUDIT-*.md         # Báo cáo nghiệm thu và phân tích chất lượng từng milestone
```

---

## 🤖 Bản đồ Kỹ năng Agent tương ứng (Agent Skills Mapping)

Mỗi nhóm tài liệu được hỗ trợ bởi một Kỹ năng chuyên biệt trong `.agent/skills/`:

| Tác vụ / Nhóm tài liệu | Kỹ năng Agent (`.agent/skills/`) | Lệnh / Output |
|---|---|---|
| **Phân tích yêu cầu / PRD** | [`analyze-requirements`](file:///.agent/skills/analyze-requirements) | Sinh `docs/01-requirements/PRD-*.md` |
| **Thiết kế kỹ thuật / ADR** | [`design-architecture`](file:///.agent/skills/design-architecture) | Sinh `docs/02-architecture/designs/TECH-*.md` & `ADR-*.md` |
| **Lập kế hoạch & Phân rã Ticket** | [`plan-and-decompose`](file:///.agent/skills/plan-and-decompose) | Sinh `docs/03-plans/PLAN-*.md` & `tickets/*.md` |
| **Triển khai Code theo Ticket** | [`execute-ticket`](file:///.agent/skills/execute-ticket) | Code feature theo từng ticket |
| **Viết Test (Unit / Integration / E2E)**| [`write-test`](file:///.agent/skills/write-test) | Sinh test cases chuẩn AAA trên Java/Python/NestJS/Next.js |
| **Chạy & Kiểm thử Tự động** | [`run-test`](file:///.agent/skills/run-test) | Thực thi tests qua `./scripts/run-tests.ps1` & pre-commit check |
| **Phân tích Chất lượng & Audit** | [`analyze-quality`](file:///.agent/skills/analyze-quality) | Phân tích coverage, triage lỗi, sinh `docs/04-reports/AUDIT-*.md` |

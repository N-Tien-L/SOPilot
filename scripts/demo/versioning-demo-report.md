# Group 1 Document Versioning Demo Report

- **Workspace:** `SOPilot Acceptance Demo — Multi-Role` (`01a21055-7743-724c-b084-269ca2ab5eba`)
- **Document ID:** `01a21247-f4d6-7299-8220-0b781ae036b7`
- **Question:** `Theo SOP-OPS-07, phụ cấp trực on-call ngày thường, cuối tuần, giới hạn ca trực mỗi tháng và SLA phản hồi sự cố P1 là bao nhiêu?`
- **Result:** **8/8 checks passed** (citations verified from persisted conversations; SSE parser in `demo-versioning.py` updated to read `event: citations`)

| Check | Status | Details |
|---|---|---|
| `v1_ready_and_metadata` | **PASS** | docId=01a21247-f4d6-7299-8220-0b781ae036b7, v1=01a21247-f4d6-7f1d-9a02-93d811e31518, title='ops-oncall-allowance-2025', category='Vận hành & An toàn' |
| `qa_v1_answers_old_figures` | **PASS** | outcome=ANSWERED, elapsed=104.3s (cold Modal), citations=2 (all `versionId=01a21247-f4d6-7f1d-9a02-93d811e31518`), figures: 200.000 / 400.000 / 8 ca / 30 phút |
| `v2_activated_and_v1_superseded` | **PASS** | v2=01a21249-ce51-7e33-bfcf-8b9879994a73, history={2: 'READY', 1: 'SUPERSEDED'} |
| `title_synced_to_v2_filename` | **PASS** | title='ops-oncall-allowance-2026' (expected 'ops-oncall-allowance-2026') |
| `category_inherited_from_v1` | **PASS** | category='Vận hành & An toàn' |
| `qa_v2_answers_new_figures_zero_v1_leak` | **PASS** | outcome=ANSWERED, elapsed=14.22s (warm Modal), citations=3 (all `versionId=01a21249-ce51-7e33-bfcf-8b9879994a73`), figures: 350.000 / 700.000 / 6 ca / 10 phút, 0 v1 leak |
| `unchanged_reupload_rejected_409` | **PASS** | HTTP 409, code=DOCUMENT_UNCHANGED |
| `hr_member_blocked_from_eng_v2` | **PASS** | outcome=REFUSED_NO_EVIDENCE, refusalReason=NO_EVIDENCE, elapsed=6.66s |

## Q&A Answers

### v1 (`ops-oncall-allowance-2025.md`, 104.3s)

Theo quy định trong SOP-OPS-07, các thông tin cụ thể như sau:

**1. Phụ cấp trực on-call:**
*   **Ngày thường (Thứ 2–Thứ 6, 18:00–08:30 ICT):** 200.000 VND/ca đêm [1].
*   **Cuối tuần hoặc ngày lễ (phủ sóng 24 giờ):** 400.000 VND/ngày [1].
*   **Điều kiện áp dụng:** Phụ cấp được trả cùng bảng lương hàng tháng dựa trên lịch trình PagerDuty đã được phê duyệt [1].

**2. Giới hạn ca trực mỗi tháng:**
*   Một kỹ sư chỉ được lên lịch tối đa **8 ca trực** trong một tháng [2].

**3. SLA phản hồi sự cố P1 (Priority 1):**
*   Kỹ sư trực chính phải xác nhận (acknowledge) và bắt đầu phân tích (triage) trong vòng **30 phút** kể từ khi nhận sự cố [2].
*   **Ngoại lệ/Điều kiện nâng cấp:** Nếu cảnh báo P1 không được xác nhận sau 30 phút, hệ thống sẽ tự động nâng cấp (escalate) lên Trưởng bộ phận Kỹ thuật [2].

### v2 (`ops-oncall-allowance-2026.md`, 14.22s)

Theo tài liệu SOP-OPS-07 (phiên bản 2.0, có hiệu lực từ 2026-11-01), các thông tin cụ thể như sau:

**1. Phụ cấp trực on-call:**
*   **Ngày thường (Thứ 2–Thứ 6, 18:00–08:30 ICT):** 350.000 VND/ca đêm [1].
*   **Cuối tuần hoặc ngày lễ (phủ sóng 24 giờ):** 700.000 VND/ngày [1].
*   **Cách thanh toán:** Phụ cấp được trả cùng bảng lương hàng tháng dựa trên lịch trình PagerDuty đã được phê duyệt [1].

**2. Giới hạn ca trực mỗi tháng:**
*   Một kỹ sư chỉ được xếp lịch tối đa **6 ca trực** trong một tháng [2].

**3. SLA phản hồi sự cố P1 (Priority 1):**
*   Kỹ sư trực chính phải xác nhận (acknowledge) và bắt đầu phân tích (triage) trong vòng **10 phút** kể từ khi nhận sự cố [2].
*   Nếu sự cố P1 chưa được xác nhận sau 10 phút, hệ thống sẽ tự động nâng cấp (escalate) lên Trưởng bộ phận Kỹ thuật [2].

*Lưu ý: Tài liệu này chỉ dành cho thành viên nhóm Kỹ thuật (Engineering team members) [3].*

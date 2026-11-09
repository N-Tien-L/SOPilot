---
id: V2-34
title: "Hạ tầng: endpoint LLM tự host (Qwen3.5-9B FP8, vLLM) trên Modal và kiểm nhanh"
type: chore
status: todo
created: 2026-11-09
updated: 2026-11-09
author: "Owner"
scope: infra
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-02]
blocks: [V2-10]
branch: "infra/modal-llm-endpoint"
assignee: pair
---

# TICKET V2-34: Endpoint LLM tự host trên Modal

> **Phạm vi (Scope):** `infra` | **Độ phức tạp:** `M` | **Ưu tiên:** `P0`
> **Kế hoạch cha:** `PLAN-V2-SOPILOT-MVP` | **Nhánh làm việc:** `infra/modal-llm-endpoint`

---

## 1. Bối cảnh & Mục tiêu
Owner đã chốt model sinh câu trả lời là Qwen3.5-9B FP8, vLLM, GPU L4 (A10 nếu L4 quá chậm) và một lần kiểm nhanh khoảng 20 câu trước khi cam kết (ADR-006 §4.4, "Chốt model sinh câu trả lời"). `V2-10` cần một endpoint thật để chạy kiểm nhanh đó và test thủ công. Ticket này dựng và kiểm endpoint OpenAI-compatible trên Modal; **không sửa code `services/ai-service`**. Quyết định model, chi phí và ứng viên thay thế ở ADR-006 §4.4, không nhắc lại ở đây.

Giới hạn:
- Hạ tầng nằm ngoài repo. Không thêm dependency vào `pyproject.toml`. Script Modal (nếu có) đặt ngoài `services/ai-service` và **phải được owner duyệt trước khi viết** (CLAUDE.md mục 12).
- Khóa và URL thật không ghi vào repo hay tài liệu; dùng placeholder (`<LLM_BASE_URL>`, `<LLM_API_KEY>`).
- **Cảnh báo dữ liệu:** mọi prompt gửi tới Modal rời khỏi máy owner. Khi chạy thử chỉ dùng `sop-main`/dữ liệu mẫu, không dùng tài liệu nội bộ thật.

---

## 2. Tiêu chí Hoàn thành
Mỗi tiêu chí kèm cách kiểm; kết quả ghi vào mục 5 (bằng chứng) khi thực hiện.

- [ ] Endpoint Modal chạy vLLM với Qwen3.5-9B FP8 trên L4 (A10 nếu L4 quá chậm), phục vụ `/v1/chat/completions` và `/v1/models`. *Kiểm:* `curl` hai đường dẫn với khóa của owner, `/v1/models` trả đúng model id, chat trả 200.
- [ ] Ghi lại model id, revision, GPU, ngày và chi phí mỗi lần khởi động (ADR-006 §4.4). *Kiểm:* bảng ở mục 5 có đủ cột, revision lấy từ Hugging Face (mở model card chính thức, ADR ghi nguồn hiện là thứ cấp).
- [ ] `enable_thinking=false` có hiệu lực qua `chat_template_kwargs` (và/hoặc `--default-chat-template-kwargs`). *Kiểm:* gửi cùng một câu có và không cờ, so số token đầu ra với độ dài câu hiển thị, ghi kết quả; ghi rõ nếu cờ chỉ ẩn token suy luận.
- [ ] Đo TTFT lạnh và nóng cùng token/giây trên một lượt mẫu (`temperature=0`, stream). *Kiểm:* ghi số đo, GPU và cách đo vào mục 5.
- [ ] Khóa chỉ nằm trong môi trường của owner, không có trong repo; `.env.example` có biến `SOPILOT_LLM_*` với giá trị giả (đã có từ `V2-10` mốc 2). *Kiểm:* `./scripts/check-env.ps1` và gitleaks không báo; `git diff` không có khóa hay URL thật.
- [ ] Kiểm điều khoản Modal về việc dùng hai tài khoản Starter (ADR-006 §4.4 ghi "chưa kiểm") và ghi kết luận kèm ngày đọc. *Kiểm:* đọc điều khoản dịch vụ và trang giá; kết luận ghi ở mục 5, nếu không cho phép thì báo owner để sửa ADR-006 §4.4.
- [ ] Chi phí dự kiến nằm trong hạn mức $30/tháng mỗi tài khoản; ghi cách giới hạn: scale-to-zero, idle timeout ngắn (30–60 giây), không ghim region, không non-preemptible, cảnh báo ngân sách workspace. *Kiểm:* cấu hình đã áp dụng được liệt kê ở mục 5; chi phí thực của lần kiểm nhanh so với ước tính $1–3 của ADR.

---

## 3. Hướng dẫn Triển khai
1. **Duyệt script (owner).** Đề xuất vị trí script Modal ngoài `services/ai-service` (ví dụ thư mục `infrastructure/modal/`); chờ owner đồng ý trước khi viết.
2. **Triển khai.** vLLM phục vụ OpenAI-compatible, trọng số cache trong Modal Volume, scale-to-zero, bảo vệ bằng khóa Bearer đặt trong Modal Secret.
3. **Kiểm** theo mục 2; ghi số đo và chi phí ngay sau mỗi lần chạy.
4. **Ghi kết quả** vào mục 5. Nếu L4 quá chậm hoặc Qwen3.5 lỗi với vLLM, dùng bảng ứng viên của ADR-006 §4.4 và báo owner; không tự đổi model.
5. **Bàn giao cho `V2-10`:** owner đặt `SOPILOT_LLM_*` trong môi trường của mình (không ghi vào repo).

---

## 4. Yêu cầu Kiểm thử
| Loại | Nội dung | Công cụ | Lệnh |
|---|---|---|---|
| Thủ công | `/v1/models`, `/v1/chat/completions`, cờ `enable_thinking`, TTFT lạnh/nóng, token/giây | `curl` | — |
| Tài liệu | frontmatter, quan hệ `depends_on`/`blocks`, link | `check-docs.ps1` | `./scripts/check-docs.ps1` |

---

## 5. Bằng chứng (điền khi thực hiện; chưa có số đo)

| Mục | Giá trị |
|---|---|
| Model id / revision | — |
| GPU | — |
| Ngày chạy | — |
| Chi phí mỗi lần khởi động | — |
| TTFT lạnh / nóng, token/giây | — |
| Kết quả `enable_thinking=false` | — |
| Kết luận điều khoản hai tài khoản | — |

---

## 6. Tóm tắt File thay đổi
Chỉ tài liệu (ticket này, PLAN, `V2-10`). Script Modal, nếu có, nằm ngoài `services/ai-service` và cần owner duyệt.

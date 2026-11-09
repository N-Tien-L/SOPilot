---
id: V2-34
title: "Hạ tầng: endpoint LLM tự host (Qwen3.5-9B FP8, vLLM) trên Modal và kiểm nhanh"
type: chore
status: done
created: 2026-11-09
updated: 2026-11-09
author: "Owner"
scope: infra
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-02]
blocks: [V2-10, V2-35]
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
- Hạ tầng nằm ngoài repo. Không thêm dependency vào `pyproject.toml`. Script Modal đặt tại `infrastructure/modal/` (owner duyệt 2026-11-09).
- Khóa và URL thật không ghi vào repo hay tài liệu; dùng placeholder (`<LLM_BASE_URL>`, `<LLM_API_KEY>`).
- **Cảnh báo dữ liệu:** mọi prompt gửi tới Modal rời khỏi máy owner. Khi chạy thử chỉ dùng `sop-main`/dữ liệu mẫu, không dùng tài liệu nội bộ thật.

---

## 2. Tiêu chí Hoàn thành
Mỗi tiêu chí kèm cách kiểm; kết quả ghi vào mục 5 (bằng chứng) khi thực hiện.

- [x] Endpoint Modal chạy vLLM với Qwen3.5-9B FP8 trên L4 (A10 nếu L4 quá chậm), phục vụ `/v1/chat/completions` và `/v1/models`. *Kiểm:* `test_endpoint.py` với khóa của owner: `/v1/models` trả 200 và đúng model id, 17 lượt chat stream đều trả kết quả (mục 5).
- [ ] Ghi lại model id, revision, GPU, ngày và chi phí mỗi lần khởi động (ADR-006 §4.4). *Kiểm:* bảng ở mục 5 có đủ cột, revision lấy từ Hugging Face. *Còn thiếu:* chi phí thật từ trang Usage của Modal (hiện mới là ước tính từ thời gian đo). → *Owner chốt 2026-11-09: đóng ticket, phần còn thiếu chuyển thành tiêu chí của `V2-10`.*
- [x] `enable_thinking=false` có hiệu lực qua `chat_template_kwargs` (và/hoặc `--default-chat-template-kwargs`). *Kiểm:* gửi cùng một câu có và không cờ, so số token đầu ra (`usage.completion_tokens`) với độ dài câu hiển thị; đối chiếu template Jinja của revision đã ghim (mục 5).
- [x] Đo TTFT lạnh và nóng cùng token/giây trên một lượt mẫu (`temperature=0`, stream). *Kiểm:* `test_endpoint.py --benchmark` ngày 2026-11-09; số đo, GPU và cách đo ở mục 5.
- [x] Khóa chỉ nằm trong môi trường của owner, không có trong repo; `.env.example` có biến `SOPILOT_LLM_*` với giá trị giả (đã có từ `V2-10` mốc 2). *Kiểm:* `./scripts/check-env.ps1` và gitleaks không báo; `git diff` không có khóa hay URL thật.
- [ ] Kiểm điều khoản Modal về việc dùng hai tài khoản Starter (ADR-006 §4.4 ghi "chưa kiểm") và ghi kết luận kèm ngày đọc. *Kiểm:* đọc điều khoản dịch vụ và trang giá; kết luận ghi ở mục 5 kèm trích dẫn điều khoản và link; nếu không cho phép thì báo owner để sửa ADR-006 §4.4. *Còn thiếu:* trích dẫn nguyên văn điều khoản. → *Owner chốt 2026-11-09: đóng ticket, phần còn thiếu chuyển thành tiêu chí của `V2-10`.*
- [ ] Chi phí dự kiến nằm trong hạn mức $30/tháng mỗi tài khoản; ghi cách giới hạn: scale-to-zero, idle timeout ngắn (30–60 giây), không ghim region, không non-preemptible, cảnh báo ngân sách workspace. *Kiểm:* cấu hình đã áp dụng được liệt kê ở mục 5; chi phí thực của lần kiểm nhanh so với ước tính $1–3 của ADR. *Còn thiếu:* chi phí thật và xác nhận đã đặt cảnh báo ngân sách. → *Owner chốt 2026-11-09: đóng ticket, phần còn thiếu chuyển thành tiêu chí của `V2-10`.*

---

## 3. Hướng dẫn Triển khai
1. **Duyệt script (owner).** Owner duyệt vị trí `infrastructure/modal/` ngày 2026-11-09. Đã tạo `serve_vllm.py`, `test_endpoint.py`, `README.md`.
2. **Triển khai.** vLLM phục vụ OpenAI-compatible, trọng số cache trong Modal Volume (`sopilot-hf-cache`, `sopilot-vllm-cache`), scale-to-zero (`scaledown_window=60`), bảo vệ bằng Bearer token trong Modal Secret `sopilot-vllm-secret`.
3. **Kiểm** theo mục 2 bằng `python infrastructure/modal/test_endpoint.py`.
4. **Ghi kết quả** vào mục 5.
5. **Bàn giao cho `V2-10`:** owner đặt `SOPILOT_LLM_*` trong `.env` môi trường của mình (không ghi vào repo).

---

## 4. Yêu cầu Kiểm thử
| Loại | Nội dung | Công cụ | Lệnh |
|---|---|---|---|
| Thủ công | `/v1/models`, `/v1/chat/completions`, cờ `enable_thinking`, TTFT lạnh/nóng, token/giây | `test_endpoint.py` / `curl` | `python infrastructure/modal/test_endpoint.py --benchmark` |
| Cú pháp & Tài liệu | Biên dịch Python, frontmatter, quan hệ `depends_on`/`blocks`, link | `python -m py_compile`, `check-docs.ps1` | `./scripts/check-docs.ps1` |

---

## 5. Bằng chứng

| Mục | Giá trị |
|---|---|
| Model id / revision | `Qwen/Qwen3.5-9B` (revision SHA: `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, Apache 2.0) |
| GPU | NVIDIA L4 (24 GB VRAM) |
| Ngày chạy / cấu hình | 2026-11-09. vLLM `0.33.0`, image `nvidia/cuda:13.0.2-devel-ubuntu22.04`, `--quantization fp8`, `--language-model-only`, `--max-model-len 8192`, `--gpu-memory-utilization 0.90`, `--default-chat-template-kwargs '{"enable_thinking": false}'`. Giới hạn chi phí: `scaledown_window=60`, không ghim region, không non-preemptible, khóa Bearer trong Modal Secret (deploy bị từ chối nếu thiếu khóa). |
| Chi phí mỗi lần khởi động | **Ước tính, chưa đối chiếu Usage:** khởi động lạnh 494 giây × $0,000222/giây GPU L4 ≈ $0,11 (chưa gồm CPU/RAM). Cả lượt đo (khởi động + 17 lượt sinh ~11K token + 60 giây chờ thu về 0) khoảng 17 phút GPU ≈ $0,23, cộng CPU/RAM ước ~$0,06 → ~$0,30. Chi phí thật: — |
| TTFT lạnh / nóng, token/giây | Đo từ máy owner (Việt Nam) tới endpoint `us-east`, stream, `temperature=0`, 15 câu mẫu VI/EN (5 câu âm), không có ngữ cảnh RAG. **Lạnh:** 494 giây từ lúc gọi `/v1/models` khi container ở 0 tới lúc server sẵn sàng (boot, nạp trọng số từ Volume, lượng tử hóa FP8, biên dịch), sát `startup_timeout` 600 giây. **Nóng:** TTFT trung bình 1145 ms (975–1289 ms), đo phía client nên gồm cả độ trễ mạng và bắt tay TLS mỗi request. **Tốc độ sinh:** 24,3 token/giây (24,2–24,5), số token lấy từ `usage`. Câu trả lời dài 129–1422 token, tức khoảng 5–58 giây mỗi câu. |
| Kết quả `enable_thinking=false` | Cùng một câu tiếng Việt: `false` → 214 token, 772 ký tự, không có thẻ `<think>`/`</think>`; `true` → 1449 token, 4926 ký tự, có khối "Thinking Process" và thẻ `</think>`. Số token đầu ra khớp với độ dài câu hiển thị, nên cờ **ngừng sinh** suy luận chứ không chỉ ẩn token. Khớp với `chat_template.jinja` của revision đã ghim: khi `enable_thinking is false`, template chèn `<think>\n\n</think>\n\n`; khi không truyền cờ thì mặc định bật suy luận, nên cần `--default-chat-template-kwargs`. |
| Kết luận điều khoản hai tài khoản | **Chưa có trích dẫn nguyên văn, cần owner kiểm lại.** Ghi nhận ban đầu (2026-11-09, `modal.com/terms`): **nghiêm cấm** tạo nhiều tài khoản cá nhân để lách hạn mức hoặc tích lũy credit miễn phí (credit farming/circumvention). Vi phạm có thể dẫn tới khóa mọi tài khoản liên quan. **Kết luận:** Vận hành trên **1 tài khoản Starter duy nhất** ($30/tháng compute miễn phí), quản lý chặt idle timeout (60s). Cần sửa ADR-006 §4.4 ghi nhận kết luận này. |

---

**Nghiệm thu (owner, 2026-11-09):** `done`. Endpoint, cờ `enable_thinking` và số đo TTFT/token mỗi giây có bằng chứng thật (DoD 1, 3, 4, 5). DoD 2, 6, 7 chưa đủ bằng chứng; owner chấp nhận đóng và chuyển sang `V2-10`: chi phí thật so với ước tính, cảnh báo ngân sách, trích dẫn điều khoản Modal về nhiều tài khoản và sửa ADR-006 §4.4 (ngân sách hiện tính trên hai tài khoản). Rủi ro đã biết: khởi động lạnh 494 giây sát `startup_timeout` 600 giây; làm nóng endpoint trước khi chạy eval hoặc demo.

---

## 6. Tóm tắt File thay đổi
- `infrastructure/modal/serve_vllm.py` (mới): Triển khai vLLM trên Modal L4, volume caching, scale-to-zero.
- `infrastructure/modal/test_endpoint.py` (mới): Script kiểm tra endpoint, cờ thinking, benchmark TTFT/throughput.
- `infrastructure/modal/README.md` (mới): Hướng dẫn thiết lập secret, deploy, kiểm thử và cấu hình `.env`.
- `docs/03-plans/tickets/V2-34-infra-modal-llm-endpoint.md`: Cập nhật trạng thái và bằng chứng.
- `docs/03-plans/PLAN-V2-sopilot-mvp.md`: `V2-34` chuyển `in-progress`.

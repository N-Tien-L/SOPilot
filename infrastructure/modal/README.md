# Modal LLM Endpoint (vLLM on L4 GPU)

> **Ticket:** `V2-34` | **Phạm vi:** `infra` | **Kế hoạch cha:** `PLAN-V2-SOPILOT-MVP`  
> **Quyết định kiến trúc:** [ADR-006 §4.4](../../docs/02-architecture/adr/ADR-006-free-tier-providers-and-environments.md) | **Thiết kế:** [TECH-V2-ai-service §4.2, §4.3](../../docs/02-architecture/designs/TECH-V2-ai-service.md)

Thư mục này chứa script triển khai và kiểm thử endpoint OpenAI-compatible phục vụ model mã nguồn mở **Qwen3.5-9B** (FP8) chạy bằng **vLLM** trên nền tảng **Modal** (GPU NVIDIA L4 24GB).

---

## 1. Mục tiêu kiến trúc & Ràng buộc

1. **Độc lập hạ tầng:** Toàn bộ code triển khai hạ tầng nằm ngoài `services/ai-service`, không làm ô nhiễm `pyproject.toml` của service.
2. **Chuẩn giao tiếp:** Cung cấp API tương thích OpenAI chuẩn (`/v1/chat/completions`, `/v1/models`), được `services/ai-service/src/sopilot_ai/providers/llm.py` tiêu thụ trực tiếp qua HTTP.
3. **Kiểm soát chi phí:**
   - Dùng gói **Modal Starter** ($30 compute credits miễn phí mỗi tháng).
   - GPU **NVIDIA L4** ($0.80/giờ).
   - Tự động thu về 0 (**scale-to-zero**) sau 60 giây rảnh (`scaledown_window=60`).
   - Không ghim region (tránh hệ số phụ phí ×1.15–1.75), không non-preemptible.
   - Cache trọng số mô hình trong `modal.Volume` (`sopilot-hf-cache` và `sopilot-vllm-cache`) để giảm thời gian khởi động lạnh.
4. **An toàn dữ liệu & Bí mật:**
   - Không bao giờ commit URL thật hoặc API key thật vào Git.
   - Mọi prompt gửi lên Modal rời khỏi máy local, chỉ dùng dữ liệu mẫu / `sop-main`, tuyệt đối không dùng tài liệu nội bộ thật.
   - **Lưu ý điều khoản (ToS):** Điều khoản dịch vụ của Modal nghiêm cấm tạo nhiều tài khoản Starter để trục lợi miễn phí (credit farming). Dự án vận hành trên **1 tài khoản Starter duy nhất** và quản lý thời gian bật/tắt hợp lý.

---

## 2. Hướng dẫn Triển khai (Deployment)

### Bước 1: Cài đặt Modal CLI và Đăng nhập
```bash
# Cài đặt Modal CLI (nếu chưa có)
pip install modal

# Xác thực tài khoản Modal
modal setup
```

### Bước 2: Tạo Modal Secret cho API Key
Tạo secret để bảo vệ endpoint bằng Bearer token:
```bash
# Thay thế <YOUR_RANDOM_SECRET_KEY> bằng chuỗi ngẫu nhiên bí mật của bạn
modal secret create sopilot-vllm-secret VLLM_API_KEY="<YOUR_RANDOM_SECRET_KEY>"
```
Secret phải có khóa `VLLM_API_KEY`. Nếu thiếu secret hoặc khóa, `modal deploy` bị từ chối và container không khởi động: endpoint không bao giờ chạy mà không có xác thực.

Đặt cảnh báo ngân sách cho workspace Modal trên dashboard (Settings → Usage/Billing) trước lần deploy đầu.

### Bước 3: (Tùy chọn) Tải trước trọng số mô hình
Để lần khởi động đầu tiên không bị timeout tải file, có thể chạy hàm nạp trước weights vào Volume:
```bash
modal run infrastructure/modal/serve_vllm.py::download_model
```

### Bước 4: Triển khai ứng dụng lên Modal
```bash
modal deploy infrastructure/modal/serve_vllm.py
```
Sau khi lệnh deploy hoàn thành, Modal sẽ cấp một URL công khai có dạng:
```
https://<workspace-name>--sopilot-vllm-serve.modal.run
```

---

## 3. Kiểm thử & Đo đạc Endpoint

Đo TTFT lạnh: đợi container thu về 0 (hơn 60 giây không có request, xem `modal app list` hoặc dashboard) rồi mới chạy script; câu đầu tiên khi đó mới là lần chạy lạnh. Timeout mặc định mỗi request là 900 giây (`--timeout`) để chờ khởi động lạnh.

Sử dụng script `test_endpoint.py` đi kèm để kiểm tra:
- Khả năng phản hồi của `/v1/models` và `/v1/chat/completions`.
- Đo thời gian đến token đầu tiên (**TTFT**) lạnh và nóng.
- Đo tốc độ sinh từ (**tokens/second**).
- Kiểm tra cờ `enable_thinking=false` (xác nhận model đóng `<think>` tag ngay từ prompt).

```bash
python infrastructure/modal/test_endpoint.py \
  --base-url "https://<workspace-name>--sopilot-vllm-serve.modal.run/v1" \
  --api-key "<YOUR_RANDOM_SECRET_KEY>" \
  --model "Qwen/Qwen3.5-9B" \
  --benchmark
```

Hoặc kiểm tra thủ công bằng `curl`:
```bash
# 1. Kiểm tra danh sách model
curl -X GET "https://<workspace-name>--sopilot-vllm-serve.modal.run/v1/models" \
  -H "Authorization: Bearer <YOUR_RANDOM_SECRET_KEY>"

# 2. Gửi thử một câu hỏi
curl -X POST "https://<workspace-name>--sopilot-vllm-serve.modal.run/v1/chat/completions" \
  -H "Authorization: Bearer <YOUR_RANDOM_SECRET_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [{"role": "user", "content": "Quy trình nghỉ phép của công ty gồm các bước nào?"}],
    "temperature": 0.0,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

---

## 4. Cấu hình cho SOPilot V2 (`services/ai-service`)

Sau khi endpoint hoạt động, cập nhật file `.env` tại thư mục gốc của repo:

```dotenv
# --- ai-service answer LLM (V2-10, ADR-006 §4.4) ---
SOPILOT_LLM_BASE_URL=https://<workspace-name>--sopilot-vllm-serve.modal.run/v1
SOPILOT_LLM_MODEL=Qwen/Qwen3.5-9B
SOPILOT_LLM_API_KEY=<YOUR_RANDOM_SECRET_KEY>
SOPILOT_LLM_RPM=60
SOPILOT_LLM_TPM=200000
SOPILOT_LLM_CONTEXT_MAX_TOKENS=8192
```

Sau đó kiểm tra tính hợp lệ bằng lệnh:
```powershell
./scripts/check-env.ps1
```

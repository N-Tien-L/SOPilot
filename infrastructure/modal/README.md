# Modal LLM Endpoint (vLLM on A10 GPU)

> **Ticket:** `V2-34` | **Phạm vi:** `infra` | **Kế hoạch cha:** `PLAN-V2-SOPILOT-MVP`  
> **Quyết định kiến trúc:** [ADR-006 §4.4](../../docs/02-architecture/adr/ADR-006-free-tier-providers-and-environments.md) | **Thiết kế:** [TECH-V2-ai-service §4.2, §4.3](../../docs/02-architecture/designs/TECH-V2-ai-service.md)

Thư mục này chứa script triển khai và kiểm thử endpoint OpenAI-compatible phục vụ model mã nguồn mở **Qwen3.5-9B** (FP8) chạy bằng **vLLM** trên nền tảng **Modal** (GPU NVIDIA A10 24GB).

---

## 1. Mục tiêu kiến trúc & Ràng buộc

1. **Độc lập hạ tầng:** Toàn bộ code triển khai hạ tầng nằm ngoài `services/ai-service`, không làm ô nhiễm `pyproject.toml` của service.
2. **Chuẩn giao tiếp:** Cung cấp API tương thích OpenAI chuẩn (`/v1/chat/completions`, `/v1/models`), được `services/ai-service/src/sopilot_ai/providers/llm.py` tiêu thụ trực tiếp qua HTTP.
3. **Kiểm soát chi phí:**
   - Dùng gói **Modal Starter** ($30 compute credits miễn phí mỗi tháng).
   - GPU **NVIDIA A10** (khoảng $1.10/giờ; đối chiếu trang Pricing của Modal). Đổi từ L4 ($0.80/giờ) vì L4 chỉ đạt 24,3 token/giây (V2-34 mục 5); A10 có băng thông bộ nhớ gấp đôi, mà tốc độ sinh phụ thuộc chủ yếu vào băng thông. ADR-006 §4.4 cho phép A10. A10 (Ampere) không có FP8 phần cứng: vLLM chạy FP8 chỉ cho trọng số (Marlin W8A16), chất lượng tương đương, TTFT có thể khác L4.
   - Tự động thu về 0 (**scale-to-zero**) sau 60 giây rảnh (`scaledown_window=60`).
   - Tối đa một container (`max_containers=1`): quá 32 request đồng thời thì request xếp hàng, không bật container GPU thứ hai.
   - Không ghim region (tránh hệ số phụ phí ×1.15–1.75), không non-preemptible.
   - Cache trọng số mô hình trong `modal.Volume` (`sopilot-hf-cache` và `sopilot-vllm-cache`) để giảm thời gian khởi động lạnh.
4. **An toàn dữ liệu & Bí mật:**
   - Không bao giờ commit URL thật hoặc API key thật vào Git.
   - Mọi prompt gửi lên Modal rời khỏi máy local, chỉ dùng dữ liệu mẫu / `sop-main`, tuyệt đối không dùng tài liệu nội bộ thật.
   - **Tài khoản:** dự án dùng hai tài khoản Starter, mỗi tài khoản một thẻ thanh toán riêng (owner chốt 2026-11-09, V2-10). Mỗi tài khoản deploy và giữ secret riêng; URL đổi theo tên workspace.

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

### Rerank chung container (V2-35)

`serve_vllm.py` là một `@app.cls` (`Serve`): `@modal.enter` nạp `bge-reranker-v2-m3` (CrossEncoder, CUDA, fp32, `max_length=512`, revision ghim) rồi khởi động vLLM với `--gpu-memory-utilization 0.85`. Hai `@modal.web_server` dùng chung một container và một GPU, nhưng có hai URL:

```
https://<workspace-name>--sopilot-vllm-serve.modal.run    # /v1/chat/completions, /v1/models
https://<workspace-name>--sopilot-vllm-rerank.modal.run   # POST /v1/rerank
```

`POST /v1/rerank` nhận `{"query": str, "passages": [str]}` (tối đa 64 passage) và trả `{"logits": [float]}` cùng thứ tự; Bearer là `VLLM_API_KEY`, thiếu hoặc sai trả `401`. Lần đầu chạy `modal run infrastructure/modal/serve_vllm.py::download_model` để tải thêm trọng số reranker vào Volume. Kiểm tra: `python infrastructure/modal/test_endpoint.py --rerank` (cần `SOPILOT_RERANK_BASE_URL`). Container ngủ sau 60 giây nhàn rỗi, nên làm nóng trước khi chạy eval (khởi động lạnh khoảng 160 giây khi cache FlashInfer đã có trên volume, lần đầu khoảng 320 giây; lớn hơn timeout rerank 30 giây của ai-service).

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

Sau khi endpoint hoạt động, cập nhật file `services/ai-service/.env` (sao từ `services/ai-service/.env.example`):

```dotenv
# --- ai-service answer LLM (V2-10, ADR-006 §4.4) ---
SOPILOT_LLM_BASE_URL=https://<workspace-name>--sopilot-vllm-serve.modal.run/v1
SOPILOT_LLM_MODEL=Qwen/Qwen3.5-9B
SOPILOT_LLM_API_KEY=<YOUR_RANDOM_SECRET_KEY>
# Rerank trên GPU (V2-35); cùng khóa, URL khác. Bật bằng RERANK_ENABLED=true, RERANK_PROVIDER=modal
SOPILOT_RERANK_BASE_URL=https://<workspace-name>--sopilot-vllm-rerank.modal.run/v1
SOPILOT_LLM_RPM=60
SOPILOT_LLM_TPM=200000
SOPILOT_LLM_CONTEXT_MAX_TOKENS=8192
```

Sau đó kiểm tra tính hợp lệ bằng lệnh:
```powershell
./scripts/check-env.ps1
```

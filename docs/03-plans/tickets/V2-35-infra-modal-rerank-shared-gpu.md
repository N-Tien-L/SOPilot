---
id: V2-35
title: "Hạ tầng + ai-service: rerank bge-reranker-v2-m3 trên GPU, chung container A10 với vLLM"
type: feat
status: todo
created: 2026-11-09
updated: 2026-11-09
author: "Owner"
scope: infra
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-34]
blocks: [V2-18]
branch: "feat/infra-modal-rerank"
assignee: pair
---

# TICKET V2-35: Rerank trên GPU chung container với vLLM

> **Phạm vi (Scope):** `infra` + `ai` | **Độ phức tạp:** `L` | **Ưu tiên:** `P1`
> **Kế hoạch cha:** `PLAN-V2-SOPILOT-MVP` | **Nhánh làm việc:** `feat/infra-modal-rerank`

---

## 1. Bối cảnh & Mục tiêu
Rerank `bge-reranker-v2-m3` trên CPU mất 15,7–18,1 giây/câu ([AUDIT-eval-rq1-rq3](../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) RQ2/RQ2b), nên `V2-07` không bật mặc định. Chế độ truy xuất mặc định (hybrid, dense hay có rerank) còn treo và đã chuyển sang `V2-10`/`V2-18` ([V2-07](V2-07-run-rq1-rq3-rq5.md) §6).

Ticket này đưa reranker lên GPU A10 **trong cùng container Modal** với vLLM của `V2-34` (`infrastructure/modal/serve_vllm.py`), để có số đo độ trễ thật và chạy lại RQ2/RQ2b nhanh. Owner chọn phương án chung container ngày 2026-11-09. Lý do: không thêm GPU và không thêm lượt khởi động lạnh riêng. Một endpoint rerank riêng trên tài khoản Modal thứ hai của owner vẫn là phương án dự phòng nếu chung container không đạt (VRAM, TTFT).

Giới hạn:
- Giữ thang điểm của RQ2/RQ3: dùng sentence-transformers `CrossEncoder`, `max_length=512`, lấy logit thô rồi áp sigmoid ở client như `LocalRerankProvider`. Không dùng endpoint pooling `/score` của vLLM.
- Embedder `bge-m3` vẫn chạy local.
- Không bật rerank mặc định, không chọn chế độ truy xuất mặc định, không hiệu chỉnh `thresholds.hybrid_rerank`. Các việc đó quyết sau khi có số đo của ticket này.
- **Dữ liệu:** nội dung chunk gửi lên Modal, cùng mức với prompt hiện tại. Chỉ dùng `sop-main`/`sop-main-v2` và dữ liệu mẫu.

---

## 2. Tiêu chí Hoàn thành

**Quyết định trước khi làm (owner)**

- [ ] Hành vi khi rerank lỗi hoặc hết thời gian chờ: (a) dừng như hiện tại (`RerankError` → lỗi lượt hỏi), hay (b) hạ xuống `hybrid` không rerank (đổi cổng và ngưỡng giữa chừng). Đề xuất (a).
- [ ] Đồng ý thêm `sentence-transformers` vào image Modal. Nếu chọn phương án cổng vào ở Bước 0 thì thêm cả `fastapi` (CLAUDE.md, quy tắc 12). Không đổi `pyproject.toml` của ai-service.

**Hạ tầng Modal**

- [ ] Spike (Bước 0) quyết phương án: hai `@modal.web_server` trong một `@app.cls` dùng chung container (không cần proxy), hoặc một cổng vào FastAPI trên port mở ra ngoài, chuyển tiếp `/v1/*` (kể cả SSE) tới vLLM ở `127.0.0.1`. Ghi kết quả vào mục 5.
- [ ] Container nạp reranker trước, rồi khởi động vLLM với `--gpu-memory-utilization` hạ từ 0,90 (đề xuất 0,85); `--max-model-len 8192` vẫn khởi động được. Ghi VRAM đo được.
- [ ] `POST /v1/rerank` nhận `{query, passages[]}` và trả `{logits[]}` cùng thứ tự với `passages`. Kiểm Bearer bằng `hmac.compare_digest` với `VLLM_API_KEY`: thiếu hoặc sai khóa trả `401`, không log khóa hay nội dung passage.
- [ ] `/v1/models` và chat stream vẫn chạy như `V2-34`. `test_endpoint.py` có thêm tùy chọn `--rerank` đo p50/p95 cho 25 cặp, 10 lượt nóng.

**Khớp điểm và hiệu năng**

- [ ] Khớp điểm: cùng 25 ứng viên × ≥ 20 câu dev, chấm bằng CPU local và GPU remote. Sau sigmoid chênh tuyệt đối ≤ 1e-3 (fp32) và thứ hạng top 5 trùng 100 %. Không đạt thì dừng và hỏi owner (fp16 cần dung sai khác).
- [ ] Độ trễ rerank khi nóng, so với 15,7 s/câu trên CPU, ghi vào mục 5.
- [ ] TTFT nóng và token/giây của chat sau khi giảm KV cache không tệ hơn số đo A10 trước thay đổi quá 10 % (A10, `gpu-memory-utilization` 0,90: TTFT nóng 943 ms, 47,9 token/s, [V2-10](V2-10-ai-service-qa-pipeline.md) mốc 5 A).
- [ ] (Chuyển từ V2-10, owner chốt 2026-11-09) Đưa cache JIT của FlashInfer (`~/.cache/flashinfer`, hoặc biến môi trường cache mà FlashInfer của vLLM 0.33.0 dùng) vào volume, để khởi động lạnh không build lại module sampling. Ghi thời gian khởi động lạnh trước và sau (trước: 264 s trên A10).

**ai-service và eval**

- [ ] `providers/rerank.py`: `RemoteRerankProvider` (`provider: modal`) gọi `{providers.modal.base_url}/rerank` qua httpx với timeout cấu hình được. HTTP lỗi, timeout hay JSON sai đều thành `RerankError`. Áp cùng `_sigmoid`; `passages` rỗng thì không gọi mạng. `build_rerank_provider` nhận `local | modal | none`.
- [ ] `config/models.yaml` và `.env.example` khai báo provider và timeout. Khóa vẫn là `SOPILOT_LLM_API_KEY`, không có biến bí mật mới.
- [ ] Unit test với httpx `MockTransport`: thành công, `401`, timeout, số logit lệch số passage, `passages` rỗng.
- [ ] `eval/`: config rerank nhận `provider: modal`, gọi cùng `RemoteRerankProvider`. Chạy lại RQ2/RQ2b trên `sop-main` và `sop-main-v2`; số liệu khớp RQ2 cũ trong dung sai của tiêu chí khớp điểm. Kết quả và độ trễ ghi vào mục 5.

**Tài liệu**

- [ ] TECH-V2-ai-service §4.3/§6.4 (provider rerank từ xa, endpoint `/v1/rerank`), ADR-006 §4.4 (rerank chạy cùng endpoint Modal), `infrastructure/modal/README.md`. `check-docs.ps1` xanh.

---

## 3. Hướng dẫn Triển khai Từng bước

### Bước 0: Spike phương án phục vụ (≤ 1 giờ GPU)
- **File:** script thử trong scratchpad, không commit.
- Thử hai `@modal.web_server` (port 8000 và 8001) trên một `@app.cls` và xác nhận hai URL cùng trỏ vào một container (một GPU, cùng process id). Không được thì chọn cổng vào FastAPI.

### Bước 1: Container Modal
- **File:** `infrastructure/modal/serve_vllm.py` (MODIFY)
- Image thêm `sentence-transformers`, cùng phiên bản với ai-service. Ghim revision `BAAI/bge-reranker-v2-m3` `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` (như `eval/configs/rq2-rerank-bge-m3.yaml`). `download_model` tải cả reranker vào `sopilot-hf-cache`.
- Nạp `CrossEncoder(..., device="cuda", max_length=512)` trước, chạy vLLM sau. Giữ `scaledown_window=60`, `max_containers=1`, `startup_timeout` 600 (theo dõi khởi động lạnh).

### Bước 2: Đo endpoint
- **File:** `infrastructure/modal/test_endpoint.py` (MODIFY): `--rerank`, `--rerank-parity <file cặp>`.

### Bước 3: Provider phía ai-service
- **File:** `services/ai-service/src/sopilot_ai/providers/rerank.py`, `providers/registry.py`, `config/models.yaml`, `.env.example` (MODIFY); `tests/unit/test_rerank_remote.py` (CREATE).

### Bước 4: Harness
- **File:** `eval/sopilot_eval/retrievers.py`, config mới `eval/configs/rq2-rerank-modal.yaml` (CREATE).

### Bước 5: Tài liệu và số đo
- Ghi mục 5, sửa TECH/ADR/README, cập nhật PLAN.

---

## 4. Yêu cầu Kiểm thử

| Loại Test | Nội dung | Lệnh |
|---|---|---|
| Unit | `RemoteRerankProvider`: thành công, 401, timeout, số logit lệch, rỗng; `build_rerank_provider` với ba provider | `./scripts/run-tests.ps1 -Scope ai-service -Type unit` |
| Build | ruff + compileall | `./scripts/validate-build.ps1 -Scope ai` |
| Eval | test harness hiện có xanh; config modal chạy được | `cd eval; uv run pytest -q` |
| Thủ công (Modal) | `/v1/rerank` 200/401, khớp điểm CPU–GPU, độ trễ, TTFT chat sau đổi VRAM | `python infrastructure/modal/test_endpoint.py --rerank` |

---

## 5. Bằng chứng

*(Điền khi thực hiện: phương án Bước 0, VRAM, độ trễ rerank p50/p95, khớp điểm, TTFT/token/giây trước và sau, kết quả RQ2/RQ2b, chi phí GPU.)*

---

## 6. Lệnh Kiểm tra Nhanh
```powershell
./scripts/validate-build.ps1 -Scope ai
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/check-docs.ps1
```

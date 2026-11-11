---
id: V2-35
title: "Hạ tầng + ai-service: rerank bge-reranker-v2-m3 trên GPU, chung container A10 với vLLM"
type: feat
status: done
created: 2026-11-09
updated: 2026-11-11
author: "Owner"
scope: infra
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-34]
blocks: [V2-18, V2-37]
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

- [x] Hành vi khi rerank lỗi hoặc hết thời gian chờ: (a) dừng như hiện tại (`RerankError` → lỗi lượt hỏi), hay (b) hạ xuống `hybrid` không rerank (đổi cổng và ngưỡng giữa chừng). Đề xuất (a).
  *Chốt:* (a), theo đề xuất, sau khi owner được giải thích trade-off và yêu cầu xử lý nốt các việc còn mở (2026-11-09). Code dừng với `RerankError`, không hạ xuống hybrid. Owner xác nhận lại khi nghiệm thu.
- [x] Đồng ý thêm `sentence-transformers` vào image Modal. Nếu chọn phương án cổng vào ở Bước 0 thì thêm cả `fastapi` (CLAUDE.md, quy tắc 12). Không đổi `pyproject.toml` của ai-service.

**Hạ tầng Modal**

- [x] Spike (Bước 0) quyết phương án: hai `@modal.web_server` trong một `@app.cls` dùng chung container (không cần proxy), hoặc một cổng vào FastAPI trên port mở ra ngoài, chuyển tiếp `/v1/*` (kể cả SSE) tới vLLM ở `127.0.0.1`. Ghi kết quả vào mục 5.
- [x] Container nạp reranker trước, rồi khởi động vLLM với `--gpu-memory-utilization` hạ từ 0,90 (đề xuất 0,85); `--max-model-len 8192` vẫn khởi động được. Ghi VRAM đo được.
  VRAM đo được: 21 180 / 23 028 MiB đã dùng khi vLLM sẵn sàng; reranker giữ 2,12 GiB (mục 5).
- [x] `POST /v1/rerank` nhận `{query, passages[]}` và trả `{logits[]}` cùng thứ tự với `passages`. Kiểm Bearer bằng `hmac.compare_digest` với `VLLM_API_KEY`: thiếu hoặc sai khóa trả `401`, không log khóa hay nội dung passage.
- [x] `/v1/models` và chat stream vẫn chạy như `V2-34`. `test_endpoint.py` có thêm tùy chọn `--rerank` đo p50/p95 cho 25 cặp, 10 lượt nóng.

**Khớp điểm và hiệu năng**

- [x] Khớp điểm: cùng 25 ứng viên × ≥ 20 câu dev, chấm bằng CPU local và GPU remote. Sau sigmoid chênh tuyệt đối ≤ 1e-3 (fp32) và thứ hạng top 5 trùng 100 %. Không đạt thì dừng và hỏi owner (fp16 cần dung sai khác).
- [x] Độ trễ rerank khi nóng, so với 15,7 s/câu trên CPU, ghi vào mục 5.
- [x] TTFT nóng và token/giây của chat sau khi giảm KV cache không tệ hơn số đo A10 trước thay đổi quá 10 % (A10, `gpu-memory-utilization` 0,90: TTFT nóng 943 ms, 47,9 token/s, [V2-10](V2-10-ai-service-qa-pipeline.md) mốc 5 A).
- [x] (Chuyển từ V2-10, owner chốt 2026-11-09) Đưa cache JIT của FlashInfer (`~/.cache/flashinfer`, hoặc biến môi trường cache mà FlashInfer của vLLM 0.33.0 dùng) vào volume, để khởi động lạnh không build lại module sampling. Ghi thời gian khởi động lạnh trước và sau (trước: 264 s trên A10).

**ai-service và eval**

- [x] `providers/rerank.py`: `RemoteRerankProvider` (`provider: modal`) gọi `{providers.modal.base_url}/rerank` qua httpx với timeout cấu hình được. HTTP lỗi, timeout hay JSON sai đều thành `RerankError`. Áp cùng `_sigmoid`; `passages` rỗng thì không gọi mạng. `build_rerank_provider` nhận `local | modal | none`.
- [x] `config/models.yaml` và `.env.example` khai báo provider và timeout. Khóa vẫn là `SOPILOT_LLM_API_KEY`, không có biến bí mật mới.
- [x] Unit test với httpx `MockTransport`: thành công, `401`, timeout, số logit lệch số passage, `passages` rỗng.
- [x] `eval/`: config rerank nhận `provider: modal`, gọi cùng `RemoteRerankProvider`. Chạy lại RQ2/RQ2b trên `sop-main` và `sop-main-v2`; số liệu khớp RQ2 cũ trong dung sai của tiêu chí khớp điểm. Kết quả và độ trễ ghi vào mục 5.

**Tài liệu**

- [x] TECH-V2-ai-service §4.3/§6.4 (provider rerank từ xa, endpoint `/v1/rerank`), ADR-006 §4.4 (rerank chạy cùng endpoint Modal), `infrastructure/modal/README.md`. `check-docs.ps1` xanh.

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

Đo ngày 2026-11-09, GPU A10, endpoint `us-east`, từ máy owner (Việt Nam); số độ trễ phía client gồm mạng.

| Hạng mục | Kết quả |
|---|---|
| Bước 0 (spike) | Hai `@modal.web_server` (8000, 8001) trong một `@app.cls` tạo **một** function `Svc.*` với `max_containers=1`, hai URL riêng nhưng cùng container. Spike chạy trên CPU, app đã dừng. **Hệ quả:** hai host khác nhau, nên rerank cần `SOPILOT_RERANK_BASE_URL` (provider đọc `providers.modal.rerank_base_url`), không phải `{base_url}/rerank` như ticket viết. Không cần proxy và không thêm `fastapi` (server rerank dùng `http.server` của thư viện chuẩn). |
| Container | `Serve` (`serve_vllm.py`): `@modal.enter` nạp CrossEncoder fp32 trên CUDA rồi chạy vLLM `--gpu-memory-utilization 0.85`, `--max-model-len 8192` vẫn khởi động. Image thêm `sentence-transformers==6.2.0` (khớp `uv.lock`). URL chat giữ nguyên nhờ `label`. |
| VRAM | **Chưa ghi được** số VRAM từng phần: log của container đo không còn truy được. Chỉ có bằng chứng gián tiếp: vLLM khởi động và phục vụ ổn ở 0,85 cạnh reranker. |
| Khởi động lạnh | 260 giây (`/v1/models` khi container ở 0), so với 494 giây ở V2-34 (hai lần đo khác điều kiện, chưa so sánh chặt). |
| `/v1/rerank` | Thiếu khóa → `401`. 25 passage × 10 lượt nóng: p50 **1386 ms**, p95 1407 ms (`test_endpoint.py --rerank`). |
| Chat trước/sau | Trước (A10, 15 câu): TTFT nóng 949 ms, 46,6 token/giây. Sau (0,85 + reranker): 841 ms, 47,2 token/giây. Không tệ hơn quá 10 %. |
| Khớp điểm CPU–GPU | 24 câu dev `sop-main` × 25 ứng viên (fp32): chênh sigmoid tối đa **2,7e-6** (ngưỡng 1e-3); top 5 trùng **24/24** câu. Đo bằng hai lượt `run` (CPU `rq2-rerank-bge-m3.yaml`, GPU `rq2-rerank-modal.yaml`) so `per_question.jsonl`. Không thêm `--rerank-parity` vào `test_endpoint.py` (script không có sentence-transformers). |
| RQ2 `sop-main-v2` test (3 lần) | `hybrid` recall@5 0,835 / MRR 0,6714; `hybrid-rerank` **0,9525 / 0,9101**, trùng số cũ (0,9525 / 0,9101). p50/câu **976 ms** (p95 1074 ms) so với 18 129 ms trên CPU. Thứ hạng ổn định giữa các lượt. |
| RQ2b `sop-main-v2` test | `dense` 0,9125 / 0,7926; `hybrid-legacy-w` 0,8725 / 0,7163; `dense-rerank` 0,9525 / 0,9115; `hybrid-legacy-w-rerank` 0,9575 / 0,9141: **trùng số RQ2b cũ** ở cả bốn dòng. p50 rerank khoảng 1,18 giây so với 15,7 giây. |
| RQ2 `sop-main` test | `hybrid` 0,9571 / 0,85; `hybrid-rerank-modal` 1,0 / 0,9726 (70 câu); không có số cũ cùng bộ để so. |
| Test | `test_rerank_remote.py` 8 test; ai-service unit 566 passed, 15 xfailed; `eval` pytest 120 passed ruff xanh; `check-docs.ps1` xanh. |
| VRAM (bổ sung) | Khi vLLM báo `healthy`: `nvidia-smi` **21 180 / 23 028 MiB** (92 %). Tiến trình reranker (torch): allocated 2,12 GiB, reserved 2,13 GiB. vLLM chiếm phần còn lại (0,85 × 22,5 GiB ≈ 19,1 GiB cho trọng số 10,3 GiB, KV cache và đồ thị CUDA). |
| Cache FlashInfer | Volume `sopilot-flashinfer-cache` gắn vào `/root/.cache/flashinfer`, commit sau khi vLLM sẵn sàng. Hai lần khởi động lạnh liên tiếp sau deploy: lần 1 (build rồi lưu) **321 s**, lần 2 (nạp từ volume) **159 s**, so với 264 s trước đó (V2-10 mốc 5 A). Log: vLLM `healthy` sau 133 s kể từ hook `enter`. |
| Chi phí GPU | `modal billing report` ngày 2026-11-09: app `sopilot-vllm` hiện tại $0,11 (20h) + $1,00 (21h) + $0,58 (22h) = **khoảng $1,69** cho đo baseline, deploy, parity, RQ2/RQ2b và các lần khởi động lạnh; tải trọng số reranker $0,007; spike CPU $0,00004. Các giờ sau 22h chưa có trong báo cáo (Modal chỉ báo khoảng trọn giờ), gồm hai lượt khởi động lạnh và kiểm tra cache FlashInfer. |

**Phát hiện khi chạy:** (1) container ngủ sau 60 giây nhàn rỗi, nên harness dựng chỉ mục xong thì lần gọi rerank đầu gặp khởi động lạnh (~260 giây): `timeout_s` của config modal đặt 600 giây. (2) Modal trả `303` kèm URL kết quả khi một request kéo dài hơn khoảng 150 giây; `RemoteRerankProvider` bật `follow_redirects` (có test). (3) Chunk của `sop-main`/`sop-main-v2` đã gửi lên Modal như ticket cho phép.

**Nghiệm thu (owner, 2026-11-09):** `done`. Rerank `bge-reranker-v2-m3` chạy trên GPU A10 chung container với vLLM: khớp điểm CPU–GPU (chênh tối đa 2,7e-6, top 5 trùng 24/24), RQ2 và RQ2b trên `sop-main-v2` trùng số cũ, rerank nóng p50 khoảng 1,0–1,4 s so với 15,7–18,1 s trên CPU, chat không tệ hơn, VRAM 21 180 / 23 028 MiB, khởi động lạnh 264 s → 159 s nhờ cache FlashInfer. Owner chấp nhận chính sách (a) khi rerank lỗi (dừng với `RerankError`, không hạ xuống hybrid). Chấp nhận còn thiếu: chi phí GPU từ giờ 23h chưa có trong báo cáo Modal (đã ghi khoảng $1,69 đến hết 22h); chưa chạy test tích hợp Docker vì không đổi SQL. Việc chọn chế độ truy xuất mặc định và hiệu chỉnh `thresholds.hybrid_rerank` vẫn thuộc `V2-10`/`V2-18`.

---

## 6. Lệnh Kiểm tra Nhanh
```powershell
./scripts/validate-build.ps1 -Scope ai
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/check-docs.ps1
```

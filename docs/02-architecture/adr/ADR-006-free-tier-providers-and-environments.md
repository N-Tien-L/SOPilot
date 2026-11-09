---
id: ADR-006
title: "V2: nhà cung cấp AI/hạ tầng miễn phí; môi trường eval local và các phương án deploy"
status: approved
created: 2026-10-17
updated: 2026-11-01
author: "Owner"
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
deciders: ["Owner"]
amends: [ADR-004]
supersedes: []
superseded_by: ""
---

# ADR-006: Nhà cung cấp miễn phí; eval trên máy local và các phương án deploy

> **Trạng thái:** `approved` (2026-10-20) | **Ngày đề xuất:** `2026-10-17` | **Người quyết định:** `Owner`
>
> ADR này bổ sung ADR-004 ở hai điểm: lựa chọn embedding, LLM, reranker và storage; và cách chạy ở từng môi trường. Bằng chứng và phân tích nằm ở [AUDIT-v2-baseline-analysis](../../04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md).
>
> **Mọi con số free tier dưới đây được đọc vào ngày 2026-10-17 và thay đổi rất nhanh.** Phải kiểm tra lại theo danh sách ở §6 trước khi deploy.

---

## 1. Bối cảnh & vấn đề cần quyết định
- PRD-V2 đặt mục tiêu 0 USD/tháng. Dự án có hai đầu ra khác nhau:
  1. **Báo cáo nghiên cứu:** cần chạy eval nhiều lần, tái lập được, không bị quota chặn.
  2. **CV:** cần một bản deploy công khai để người khác tự đăng nhập và dùng thử.
- Hai đầu ra này cần hai môi trường khác nhau. Nếu dùng chung một cấu hình thì hoặc eval bị quota chặn, hoặc bản deploy không chạy nổi trên free tier.
- Các lựa chọn cũ không còn dùng được (AUDIT §4, §6):
  - Jina: quota cấp một lần.
  - Groq: phần lớn model đang dùng đã bị tắt.
  - MinIO community: đã bị archive.
  - Hugging Face Spaces: phải trả phí mới tạo được Space chạy compute.
  - Oracle: owner không muốn dùng.

## 2. Tiêu chí đánh giá
1. Chi phí 0 USD, ưu tiên quota **nạp lại theo ngày hoặc tháng** hơn quota cấp một lần.
2. Kết quả eval tái lập được: model và phiên bản phải ghim được.
3. Đổi provider chỉ bằng biến môi trường, không phải sửa code.
4. Thời gian thiết lập thấp và ít rủi ro "tốn công mà không chạy được".
5. Hỗ trợ đa ngôn ngữ (tối thiểu VI và EN, gồm cross-lingual).
6. **Khả thi trên máy owner (CPU, không GPU)**: ưu tiên cấu hình chạy được và đo được hơn cấu hình tốt nhất lý thuyết. Mỗi lựa chọn nặng phải có phương án rút gọn (tập con, model nhỏ hơn) và chi phí đo được ghi vào báo cáo.

## 3. Các phương án xem xét (tóm tắt)

| Hạng mục | Phương án | Kết luận |
|---|---|---|
| Embedding | Jina API | Loại: quota cấp một lần, chỉ dùng phi thương mại |
| | Voyage API | Loại: quota cũng cấp một lần |
| | Gemini embedding API | Chỉ để dự phòng: dữ liệu gửi qua free tier có thể được Google dùng để cải thiện sản phẩm |
| | **bge-m3, chạy local + gọi qua Cloudflare Workers AI** | **Chọn:** MIT, đa ngôn ngữ, cùng một model ở cả hai môi trường |
| | Qwen3-Embedding-0.6B, multilingual-e5-large-instruct | Đưa vào eval để so sánh (RQ5) |
| Rerank | `bge-reranker-v2-m3` chạy local | **Chọn cho eval** |
| | Workers AI `bge-reranker-base` | Loại: yếu với tiếng Việt (chưa đo trên corpus của dự án) |
| LLM | Groq (model Llama cũ) | Loại: đã bị tắt |
| | **Gemini Flash-Lite 3.x + Groq `gpt-oss-*`** | **Chọn cho deploy** |
| | LLM chạy local (Ollama hoặc llama.cpp) | **Tùy chọn cho eval**, nếu máy có đủ GPU/RAM |
| Host model trên Hugging Face Space | — | Loại: cần gói PRO; Space không nối được Postgres |
| Host trên Oracle Always Free | — | Loại theo quyết định của owner |
| Object storage | **Cloudflare R2** (dự phòng **Backblaze B2**) | Chọn cho deploy |
| | MinIO đã ghim phiên bản, hoặc SeaweedFS | Chọn cho local |

## 4. Quyết định

### 4.1 Nguyên tắc chung (áp dụng cho mọi môi trường)
1. **Mọi provider đều nằm sau interface.** ai-service có `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`), `RerankProvider` (`local` | `none`) và `LLMProvider` (dùng API kiểu OpenAI: Gemini, Groq hoặc server local). Chọn provider bằng biến môi trường.
2. **Chỉ có một file cấu hình model** (`ai-service/config/models.yaml` hoặc tương đương). Mỗi việc (`guard`, `generate`, `small_task`, `judge`) khai báo provider, model ID và danh sách model dự phòng. Không gán cứng model ID trong code. Khi khởi động, service gọi `/models` của provider và cảnh báo nếu model đã bị gỡ.
3. **Ghi rõ nguồn gốc embedding.** Mỗi chunk lưu `embedding_provider`, `embedding_model`, `embedding_dim` và `embedding_revision`. Không trộn vector từ hai nguồn khác nhau trong cùng một index. Cache có khóa là `(model, revision, sha256(chunk))`.
4. **Object storage chỉ dùng API S3 chuẩn.** Endpoint, bucket và key cấu hình qua biến môi trường.

### 4.2 Môi trường A: eval cho báo cáo nghiên cứu (chạy trên máy local)

**Mục tiêu:** chạy được nhiều lần, không phụ thuộc quota, kết quả tái lập được.

| Thành phần | Lựa chọn | Ghi chú |
|---|---|---|
| Hạ tầng | `docker compose` có Postgres 16 + pgvector và MinIO đã ghim phiên bản (hoặc SeaweedFS) | Không mở port nào ra Internet |
| Embedding | `BAAI/bge-m3` chạy local qua container Text Embeddings Inference CPU, hoặc sentence-transformers | Ghim commit hash của model trên Hugging Face |
| Model so sánh | `Qwen/Qwen3-Embedding-0.6B`, `intfloat/multilingual-e5-large-instruct` | multilingual-e5 chỉ đọc được 512 token, chunk phải phù hợp |
| Rerank | `BAAI/bge-reranker-v2-m3` chạy local | Bật hoặc tắt theo cấu hình thí nghiệm |
| LLM sinh câu trả lời | Model nhỏ mã nguồn mở tự triển khai trên Modal (vLLM), chọn ở §4.4 | Ghi lại model kèm revision, nhiệt độ (`temperature=0`), seed, loại GPU và chi phí |
| LLM làm giám khảo (faithfulness) | Một model cố định, khác họ model sinh, cho mọi lần chạy (§4.4) | Tốn ngân sách Modal, nên chỉ chạy trên tập con có kích thước cố định |

**Thiết kế thí nghiệm:**
- **Tách hai lớp đo:**
  - Đo truy xuất (Recall@k, nDCG@10, MRR, độ trễ p50/p95): không cần LLM, nên chạy bao nhiêu lần tùy ý.
  - Đo câu trả lời (độ chính xác trích dẫn, faithfulness, tỉ lệ từ chối đúng): cần LLM, nên chạy ít lần hơn.
- **Ma trận cấu hình:**

  | RQ | Biến thay đổi | Các mức |
  |---|---|---|
  | RQ1 | Cách truy xuất | dense, BM25, hybrid (RRF) |
  | RQ2 | Rerank | tắt, `bge-reranker-v2-m3`; số chunk vào prompt k ∈ {5, 10} |
  | RQ3 | Ngưỡng từ chối | quét ngưỡng, vẽ đường cân bằng giữa trả lời sai và từ chối nhầm |
  | RQ4 | Lọc tenant | chỉ lọc ở ứng dụng, lọc ở ứng dụng + RLS (đo độ trễ) |
  | RQ5 (đề xuất) | Model embedding | bge-m3, Qwen3-Embedding-0.6B, multilingual-e5-large-instruct |
- **Bộ dữ liệu:**
  - Tài liệu SOP và văn bản công khai bằng tiếng Việt và tiếng Anh, ghi rõ nguồn và giấy phép. Mỗi câu hỏi có nhãn ngôn ngữ (`lang`); câu cross-lingual (câu hỏi và tài liệu khác ngôn ngữ) được gắn cờ riêng để báo cáo tách.
  - Câu hỏi có nhãn tài liệu và trang kỳ vọng, cờ `answerable`, và một phần câu hỏi không trả lời được.
  - Câu hỏi có thể dùng LLM để sinh nháp, nhưng **người phải duyệt lại**. Ghi rõ quy trình này trong báo cáo.
- **Tái lập:**
  - Mỗi lần chạy xuất `run.json` gồm commit git, hash cấu hình, model kèm revision, kích thước tập dữ liệu, thời gian và phần cứng.
  - Embed corpus một lần rồi dùng lại cho mọi cấu hình truy xuất.
  - Kết quả lưu ở `eval/results/<run_id>/`. Báo cáo tổng hợp lưu ở `docs/04-reports/`.
- **Phần cứng:** chưa đo trên máy của owner. Lần chạy đầu tiên phải ghi lại CPU/GPU/RAM và thời gian embed toàn bộ corpus để đưa vào báo cáo.

### 4.3 Môi trường B: deploy công khai cho CV

**Mục tiêu:** người tuyển dụng hoặc người chấm tự đăng nhập Google và hỏi đáp trên tài liệu demo, với chi phí 0 USD.

#### Phương án B1 (đề xuất): ghép các dịch vụ miễn phí, không cần VM

| Thành phần | Dịch vụ | Free tier (2026-10) | Lưu ý |
|---|---|---|---|
| Frontend | Vercel hoặc Cloudflare Pages | — | Rewrite `/api/**` → core-api, `/ai/**` → ai-service để trình duyệt chỉ thấy một origin |
| core-api | Render Free (Docker) | 512 MB RAM, 0.1 vCPU, ngủ sau 15 phút | JVM chật: dùng `-Xmx300m -XX:+UseSerialGC`, hoặc build native bằng GraalVM |
| ai-service | Render Free (Docker) | Như trên | **Không chạy model trong service này** |
| Postgres + pgvector | Neon Free | 0.5 GB, 100 CU-giờ mỗi project, tắt sau 5 phút không dùng | Một vector 1024 chiều tốn khoảng 4 KB, nên chứa được vài chục nghìn chunk |
| Object storage | Cloudflare R2 (dự phòng Backblaze B2) | 10 GB | R2 có thể đòi thẻ hoặc PayPal để kích hoạt |
| Embedding | Cloudflare Workers AI `@cf/baai/bge-m3` | 10 nghìn neurons/ngày (khoảng 9 triệu token, tự tính), nạp lại lúc 00:00 UTC | Hết quota thì trả lỗi, không tự tính tiền. **Không chạy LLM trên Workers AI** vì dùng chung quota neurons |
| Rerank | Tắt | — | Bật lại khi eval chứng minh lợi ích và có chỗ chạy |
| LLM sinh câu trả lời | Gemini Flash-Lite 3.x | Khoảng 500–1.500 request/ngày tùy nguồn | Dữ liệu free tier có thể bị dùng để cải thiện sản phẩm; free tier không phục vụ người dùng ở EU, EEA, Anh, Thụy Sĩ |
| LLM dự phòng và việc nhỏ | Groq `openai/gpt-oss-120b` / `gpt-oss-20b` | Khoảng 1 nghìn request và 200 nghìn token mỗi ngày (bảng của gói Developer) | — |
| Guard | Groq `meta-llama/llama-prompt-guard-2-86m` | 14.4 nghìn request/ngày | Bị loại cho V2 sau bài test 2026-10-20 (§4.4); dòng này chỉ còn giá trị lịch sử cho phương án deploy |
| CI | GitHub Actions | Miễn phí với repo public | Chạy test FR-19 |

> **Sửa 2026-11-01:** hai hàng LLM của B1 (Gemini, Groq `gpt-oss-120b`) là bản gốc 2026-10-17 và không còn là lựa chọn cho sinh câu trả lời; xem §4.4. Phương án deploy dùng model trên Modal sẽ phải tính cả khởi động lạnh và hạn mức $30/tháng; chưa kiểm cho trường hợp phục vụ công khai.

### 4.4 Phân vai LLM cho V2 (owner chốt 2026-10-19; sửa 2026-11-01)

> **Sửa 2026-11-01 (owner, V2-02):** bản 2026-10-19 dùng Gemini và Groq `gpt-oss-120b` cho sinh câu trả lời và giám khảo, theo hạn mức free tier. Owner đổi sang **model mã nguồn mở nhỏ tự triển khai trên Modal** để chứng minh hệ thống không phụ thuộc model thương mại cỡ lớn. Các hàng guard, gợi ý metadata, embedding, rerank giữ nguyên. Lịch sử hạn mức và kết quả gọi thử ở AUDIT-v2 §4.1.

**Hạ tầng cho hai việc cần LLM mạnh (sinh câu trả lời, giám khảo):** Modal gói Starter, hai tài khoản, mỗi tài khoản $30 compute mỗi tháng (đọc ở `modal.com/pricing` ngày 2026-11-01; **chưa kiểm điều khoản về nhiều tài khoản**). Giá theo giây, quy đổi theo giờ: T4 $0,59, L4 $0,80, A10 $1,10, L40S $1,95, A100 40 GB $2,10; CPU $0,047/core-giờ, RAM $0,008/GiB-giờ, cộng thêm khoảng $0,22/giờ cho container GPU 2 core 16 GiB (ước tính). Tránh ghim region (×1,15–1,75) và chế độ non-preemptible (×3). Không dùng endpoint dùng chung của Modal (tính theo token, không nằm trong $30). Chạy bằng server tương thích OpenAI (vLLM) sau `LLMProvider`, thu về 0 khi không dùng (scale-to-zero), cache trọng số trong Volume. Chạy 24/7 không khả thi (một L4 khoảng $576/tháng), nên dùng cho eval theo lô và demo có làm nóng trước.

| Việc | Model chính | Dự phòng | Lý do |
|---|---|---|---|
| Sinh câu trả lời | **Qwen 3.5 9B**, lượng tử hóa Q4 hoặc FP8, trên A10 hoặc L4 (24 GB) | **Qwen 3.5 4B** trên L4 hoặc T4 nếu 9B không đạt độ trễ hoặc ngân sách | Họ Qwen được khuyến nghị nhiều nhất cho tiếng Việt ở cỡ này; ngữ cảnh 256K dư cho prompt RAG 3–5K token; 9B vừa 24 GB. **Chưa đo trên bộ SOP của dự án** (xem tiêu chí chọn bên dưới) |
| Guard injection/jailbreak | Bốn lớp không gọi LLM (PRD FR-13): luật đầu vào hai mức, ghép prompt có thẻ dữ liệu, canary token kiểm đầu ra, log | — | Llama Prompt Guard 2 86M bị loại sau bài test V2-02 (2026-10-20): chặn đúng 4/20 tấn công tiếng Việt, chặn nhầm 2/10 câu tiếng Anh dễ nhầm và 1/10 chunk tài liệu. Quyền đọc đã được thực thi trong SQL nên guard chỉ là lớp phụ |
| Gợi ý metadata | Groq `openai/gpt-oss-20b` (30 RPM, 1K RPD, 8K TPM), giữ theo owner | Chỉ kết quả luật | Prompt ngắn. Đây là phụ thuộc Groq còn lại duy nhất; nếu bỏ nốt thì đổi sang model sinh ở trên hoặc chỉ dùng luật |
| Giám khảo faithfulness | **Gemma 4** (khác họ với Qwen để không tự chấm): bản MoE cỡ 26B trên L40S (48 GB) cho lượt chạy cuối; bản E4B trên A10 cho lượt chạy thử khi phát triển | Giảm kích thước tập con được chấm, và người chấm tay mẫu cố định | Khác họ với model sinh. Model giám khảo nhỏ yếu hơn `gpt-oss-120b`, nên báo cáo phải nêu rõ và thêm chấm tay 30–50 câu để đối chiếu. Tên và kích thước bản Gemma 4 chưa kiểm trên Ollama/Hugging Face (nguồn mâu thuẫn), phải xác nhận tag trước khi kéo |
| Embedding, rerank | Local (`bge-m3`, `bge-reranker-v2-m3`) | — | Không phụ thuộc quota |

**Chốt model sinh câu trả lời và ứng viên thay thế (owner chốt 2026-11-04, V2-10):** owner bỏ bake-off đầy đủ bên dưới; chọn **Qwen3.5-9B, FP8, vLLM trên L4** (A10 nếu L4 quá chậm). Chỉ chạy một lần kiểm nhanh trước khi cam kết: khoảng 20 câu từ `sop-main` (có câu âm), `temperature=0`, đọc bằng mắt xem đáp đúng ngôn ngữ của câu hỏi và có `[n]` đúng nguồn, đo TTFT một lần lạnh và một lần nóng, đếm token đầu ra so với độ dài câu hiển thị để biết `enable_thinking=false` có thực sự hết sinh suy luận. Chi phí dự kiến $1–3.

Dữ kiện đã kiểm ngày 2026-11-04 (nguồn thứ cấp, chưa đọc model card chính thức; mở Hugging Face để xác nhận trước khi kéo): Qwen3.5-9B là model dày 9B, Apache 2.0, ngữ cảnh khoảng 262K, BF16 khoảng 19,3 GB (nên dùng FP8 trên L4 24 GB); vLLM có recipe chính thức; chạy bằng `--default-chat-template-kwargs '{"enable_thinking": false}'`, riêng việc cờ này có ngừng sinh suy luận hay chỉ ẩn token thì nguồn mâu thuẫn. **Chưa có số đo so sánh tiếng Việt giữa các ứng viên**; chọn Qwen3.5-9B là giả thuyết hợp lý chứ không phải kết quả đo.

Ứng viên thay thế, theo thứ tự nên thử khi gặp vấn đề (đổi chỉ qua `models.yaml`/biến môi trường của `LLMProvider`, không sửa pipeline):

| Triệu chứng khi chạy thật | Đổi sang | GPU Modal | Ghi chú và điều chưa kiểm |
|---|---|---|---|
| Qwen3.5 lỗi với vLLM, vẫn sinh suy luận dù tắt thinking, hoặc hành vi lạ của kiến trúc mới | **Qwen3-8B** | L4 | Thế hệ trước cùng họ, trưởng thành hơn; Apache 2.0. Ngữ cảnh các nguồn lệch (32K–128K, đều đủ cho prompt 3–5K token). Cùng họ nên không tránh được điểm yếu tiếng Việt nếu có |
| Quá chậm hoặc vượt ngân sách | **Qwen3.5-4B** (dự phòng gốc của ADR) | L4 hoặc T4 | Rẻ nhất; chất lượng trích dẫn/tuân thủ prompt thường giảm, cần đọc lại mẫu |
| Chất lượng tiếng Việt của họ Qwen kém | **Gemma 4 E4B** (khoảng 8B tổng, 4,5B hiệu dụng) | A10 | Khác họ. Nguồn thứ cấp nêu Apache 2.0 và 140+ ngôn ngữ; **tiếng Việt không được nêu riêng**. Tag Hugging Face nêu: `google/gemma-4-E4B-it` |
| Cần model lớn hơn mà vẫn rẻ | **Gemma 4 26B A4B** (MoE, 3,8B hoạt động trên 25,2B tổng) | L40S | Trọng số FP8 khoảng 26 GB nên không vừa L4/A10; đắt hơn nhiều ($1,95/giờ). Tag nêu: `google/gemma-4-26B-A4B-it` |

**Ràng buộc giám khảo:** bảng trên đặt Gemma 4 làm giám khảo faithfulness vì khác họ với model sinh. Nếu đổi model sinh sang Gemma 4 thì giám khảo phải đổi sang họ khác (ví dụ Qwen3.5-9B hoặc Qwen3-8B) để không tự chấm; cập nhật hàng giám khảo cùng lúc.

Đã xem xét nhưng không đề xuất: Phi-4 14B (MIT theo hầu hết nguồn, nhưng không có bằng chứng tiếng Việt), Granite 3.1 8B (Apache 2.0, 128K nhưng danh sách ngôn ngữ chính thức theo trí nhớ không có tiếng Việt, chưa kiểm), Llama (giấy phép các bản mới mâu thuẫn giữa các nguồn), Mistral 7B v0.3 (cũ, ngữ cảnh 32K).

**Tiêu chí chọn và kiểm model (bake-off đầy đủ; owner đã bỏ ngày 2026-11-04, chỉ giữ lần kiểm nhanh ở trên; các mục sau còn là cách đo nếu muốn so sánh nghiêm túc sau này):**
1. Chạy Qwen 3.5 9B và 4B trên khoảng 20 câu VI/EN lấy từ bộ eval (có câu không trả lời được), `temperature=0`, ghi model kèm revision.
2. Đo thời gian đến token đầu (TTFT) p50/p95 gồm cả khởi động lạnh, token/giây, chi phí Modal mỗi lần chạy và mỗi câu.
3. Đo mức tuân thủ quy tắc prompt: `[n]` đúng nguồn, câu mở đầu cố định khi thiếu thông tin, đáp bằng ngôn ngữ của câu hỏi, không để lộ canary.
4. Chọn model **nhỏ nhất** đạt cả bốn: tuân thủ quy tắc không kém rõ rệt so với model lớn hơn, TTFT chấp nhận được cho eval, và tổng chi phí còn trong ngân sách. Không đạt thì dùng bản dự phòng và ghi lại.
5. Giám khảo: đối chiếu với chấm tay 30–50 câu; ghi độ đồng thuận. Báo cáo ghi giới hạn của giám khảo nhỏ.
6. Mỗi lần chạy ghi `run.json` với loại GPU, thời lượng và chi phí; đặt cảnh báo ngân sách (workspace budget) trên cả hai tài khoản, đặt idle timeout ngắn (30–60 giây) và dừng app sau mỗi phiên.

**Ước tính ngân sách (chưa đo, ước lượng sơ bộ ngày 2026-11-01):** bake-off khoảng $3; phát triển với model thật khoảng $11; khoảng 10 lượt chạy đánh giá câu trả lời khoảng $7; khoảng 10 lượt giám khảo trên L40S khoảng $11; bộ kiểm tiếng Việt và đo độ trễ khoảng $3; dự phòng 50%. Tổng khoảng $50, vừa trong $60 của hai tài khoản trong một tháng nếu chạy theo lô, tắt container khi rảnh và phát triển bằng stub hoặc model 4B cục bộ. Thay số bằng số đo thật sau bake-off.

Không dùng: Gemini (mọi đời) và Groq `gpt-oss-120b` cho hai việc trên, Groq `gpt-oss-safeguard-20b` (3 RPM). Không có node LLM phân loại ý định: chào hỏi được trả lời bằng luật và semantic router dùng embedding câu hỏi, không gọi LLM (owner chốt 2026-10-20, V2-27; phương án LLM classifier cho vùng xám bị loại), câu dưới ngưỡng bằng chứng bị từ chối mà không gọi LLM sinh (PRD FR-12, FR-13). Dữ liệu gửi tới Modal (model tự triển khai) và Groq (gợi ý metadata) rời khỏi máy owner; README phải cảnh báo không đưa tài liệu nội bộ thật khi chạy demo.

**Các ràng buộc thiết kế mà B1 đặt ra:**
1. **Mỗi câu hỏi chỉ gọi LLM 2 lần:**
   - Guard không gọi LLM (bốn lớp luật, xem §4.4); nội dung độc hại dựa vào luật và model sinh.
   - Lần gọi chính: sinh câu trả lời, mang tối đa 5–6 chunk.
   - Việc viết lại câu hỏi chỉ chạy khi có lịch sử hội thoại (lần gọi thứ hai và duy nhất còn lại). Với model tự triển khai, giới hạn này là mục tiêu độ trễ và chi phí, không còn là giới hạn quota. Tiêu đề hội thoại sinh bằng luật đơn giản.
2. **Hạn mức** (FR-09): số câu hỏi mỗi user mỗi ngày, cộng một hạn mức chung toàn hệ thống để bảo vệ quota.
3. **Service ngủ thì không chạy job.** Outbox của core-api phải *đẩy* HTTP sang ai-service để đánh thức nó, không chỉ dựa vào scheduler. Worker của ai-service quét job còn tồn mỗi khi khởi động.
4. **Không dùng cron để giữ service luôn thức.** Render cho 750 giờ/tháng dùng chung cho mọi service, giữ hai service thức 24/7 sẽ hết quota. Trước buổi demo thì gọi trước một lần để đánh thức.
5. **Workspace demo:** có một workspace công khai chứa bộ SOP mẫu. User mới tạo bằng JIT được thêm vào với role `MEMBER` (chỉ đọc), bật bằng cờ cấu hình. Người thử hỏi được ngay mà không phải upload. Đây là một thay đổi nhỏ trong ADR-005, cần owner duyệt.
6. **Google OAuth** phải chuyển consent screen sang *In production* để người ngoài danh sách test đăng nhập được.
7. Ghi rõ trên trang demo: thời gian khởi động lại, hạn mức, và dữ liệu là demo.

#### Phương án B2: một VM chạy docker compose (nếu có VM)
- Dùng khi có VM đủ RAM, ví dụ credit cho sinh viên (GitHub Student Developer Pack, Azure for Students). **Chưa kiểm tra điều kiện của các gói này năm 2026.**
- Chạy cùng compose như môi trường A, cộng reverse proxy có HTTPS. Có thể bật bge-m3 và reranker chạy local.
- Code không đổi, chỉ đổi biến môi trường.

#### Phương án B3 (dự phòng chắc chắn): chạy trên máy local và mở tạm ra Internet
- Chạy compose trên máy của owner, mở ra ngoài bằng Cloudflare Tunnel (`cloudflared`, miễn phí) khi phỏng vấn hoặc khi demo trực tiếp.
- Kèm một video demo và báo cáo eval trong README cho trường hợp người xem tự xem lúc không có ai bật máy.
- Không phải bản deploy thường trực, nhưng chi phí 0 và rủi ro thấp nhất.

**Thứ tự triển khai đề xuất:** làm A trước, vì đây là phần phục vụ nghiên cứu và chạy trên cùng compose. Sau đó B3 (gần như miễn phí công sức), rồi B1 khi tính năng đã ổn định.

## 5. Tác động & hệ quả
- **Tích cực:**
  - Eval không phụ thuộc quota và tái lập được.
  - Bản deploy không cần VM và không phải vận hành model.
  - Đổi provider chỉ bằng cấu hình, nên khi model bị gỡ thì không phải sửa code.
- **Đánh đổi:**
  - Bản deploy (B1) tắt rerank, nên chất lượng thấp hơn cấu hình tốt nhất trong eval. Báo cáo phải ghi rõ sự khác biệt này.
  - Vector từ Workers AI và từ bge-m3 chạy local có thể lệch nhẹ. Chỉ số eval đo trên bge-m3 local; bản deploy dùng index riêng.
  - Cold start khoảng 30–60 giây (Render + Neon).
  - Quota LLM giới hạn khoảng vài trăm câu hỏi mỗi ngày trên toàn hệ thống.
  - Phụ thuộc nhiều tài khoản miễn phí, nên phải có checklist kiểm tra lại (§6).
  - Dữ liệu gửi qua Gemini free tier có thể bị dùng để cải thiện sản phẩm. Bản deploy chỉ chứa tài liệu demo.
- **Hành động tiếp theo:**
  - Đưa §4.1–§4.3 vào TECH-V2-ai-service (interface provider, file cấu hình model, pipeline 2 lần gọi LLM, schema điểm truy xuất) và TECH-V2-core-api (outbox đẩy để đánh thức, workspace demo).
  - Tạo thư mục `eval/` cùng định dạng bộ dữ liệu (FR-18).

## 6. Checklist kiểm tra lại trước khi deploy
- [ ] Groq: gọi `/models` bằng key thật; xem trang Deprecations và giới hạn ở `console.groq.com/settings/limits`.
- [ ] Gemini: xem model Flash-Lite hiện hành, trang Deprecations, giới hạn free trong AI Studio, và điều khoản dùng dữ liệu.
- [ ] Cloudflare: giá neurons của `bge-m3` và hạn mức free của Workers AI; điều kiện kích hoạt R2.
- [ ] Render, Neon: RAM, giờ chạy, thời gian ngủ của free tier.
- [ ] Google OAuth: trạng thái publish và yêu cầu verification với scope `openid email profile`.
- [ ] Kiểm tra độ lệch cosine giữa vector từ Workers AI và từ bge-m3 local trên khoảng 100 chunk mẫu.

## 7. Nguồn tham khảo (đọc ngày 2026-10-16 → 2026-10-17)
- [Cloudflare Workers AI – Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [Models](https://developers.cloudflare.com/workers-ai/models/)
- [Cloudflare R2](https://www.cloudflare.com/products/r2/), [R2 free tier – r2drop](https://r2drop.com/blog/cloudflare-r2-free-tier-guide)
- [Backblaze B2 review – cloudwards](https://www.cloudwards.net/backblaze-b2-review/)
- [Groq – Models](https://console.groq.com/docs/models), [Deprecations](https://console.groq.com/docs/deprecations), [Rate limits](https://console.groq.com/docs/rate-limits)
- [Gemini API – Deprecations](https://ai.google.dev/gemini-api/docs/deprecations), [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Free tier (10/2026) – klymentiev](https://klymentiev.com/blog/gemini-api-free-tier)
- [Hugging Face Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview)
- [Hosting free tiers (09/2026) – flaviocopes](https://flaviocopes.com/hosting-free-tiers/), [Hosting free tier comparison – agentdeals](https://agentdeals.dev/hosting-free-tier-comparison-2026)
- [Neon pricing](https://neon.com/pricing), [Neon free plan limits](https://neon.com/faqs/free-plan-limits-and-quotas)
- [VN-MTEB](https://arxiv.org/pdf/2507.21500), [Qwen3 Embeddings MTEB – Zilliz](https://zilliz.com/ai-faq/qwen3-embeddings-vs-alternatives-mteb-ranking)
- [TEI Intel CPU container](https://huggingface.co/docs/text-embeddings-inference/intel_container)
- [Oracle free tier changes 2026 – terminalbytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)
- [MinIO archived – pinggy.io](https://pinggy.io/blog/minio_archived_self_hosted_s3_alternatives/)

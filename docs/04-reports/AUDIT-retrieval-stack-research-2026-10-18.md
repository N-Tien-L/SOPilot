---
id: AUDIT-retrieval-stack-research-2026-10-18
title: "Nghiên cứu lựa chọn embedding, hybrid retrieval và reranker cho SOPilot"
status: final
type: research
scope: retrieval
verdict: conditional-recommendation
created: 2026-10-18
updated: 2026-10-18
refs:
  - docs/02-architecture/adr/ADR-006-free-tier-providers-and-environments.md
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
---

# Kết luận nghiên cứu retrieval stack

Ngày đối chiếu nguồn: **18/10/2026**. Đây là khuyến nghị nghiên cứu, không phải phê duyệt ADR/PRD, nghiệm thu hiệu năng hay yêu cầu triển khai. Không chạy model, tải trọng số, gọi API có key hoặc đọc `.env` trong lần nghiên cứu này.

## 1. Kết luận lựa chọn

**BGE-M3 vẫn đáng dùng, nhưng không còn đủ cơ sở để mặc định là lựa chọn tốt nhất.** Giữ `BAAI/bge-m3` làm baseline có thể tái lập; đưa `Qwen/Qwen3-Embedding-0.6B` lên thành challenger ưu tiên cao nhất. Cả hai hiện có đường deploy Cloudflare Workers AI với cùng đơn giá công bố. Không cần ghép embedding và reranker cùng họ model.

| Môi trường | Stack đề nghị | Điều kiện |
|---|---|---|
| Nghiên cứu CPU | BGE-M3 dense + BM25 + RRF; BGE reranker v2 M3 bật/tắt; Qwen3-Embedding-0.6B và E5 instruct làm đối chứng | Ghim revision, đúng instruction, đo CPU/RAM/thời gian; rerank có thể chạy tập con cố định |
| Demo miễn phí ít lượt | Cloudflare BGE-M3 tạm làm baseline deploy + pgvector + BM25/RRF + Pinecone `bge-reranker-v2-m3` → top 5 | Tối đa 500 lượt rerank/tháng toàn hệ thống theo Starter; kiểm tra p95 trước khi tuyên bố đạt NFR |
| Lựa chọn embedding sau eval | Chuyển sang Cloudflare Qwen3-Embedding-0.6B nếu thắng trên SOP VI/EN và cross-lingual với chi phí CPU chấp nhận được | Tạo index mới, embed lại toàn corpus, đo lại ngưỡng từ chối; không trộn vector dù cùng 1024 chiều |
| Nhiều hơn quota demo | Managed rerank trả phí, hoặc BGE reranker trên GPU serverless Modal | Có ngân sách hoặc chấp nhận credit/cold start; chưa thể cam kết 0 USD và mọi lượt luôn thành công |

Nếu bắt buộc **rerank thành công ở mọi lượt**, 0 USD/tháng chỉ khả thi trong hạn mức: hết quota phải chặn lượt mới hoặc đợi kỳ reset. Nếu ưu tiên liên tục trả lời, cho phép dùng thứ tự hybrid khi lỗi nhưng phải ghi nhận trạng thái degraded; không gọi lượt đó là đã rerank. Không có bằng chứng cho một API miễn phí không giới hạn, luôn sẵn sàng, bảo đảm p95 dưới một giây.

## 2. Ràng buộc thực của project

[PRD-V2](../01-requirements/PRD-V2-sopilot-mvp.md) yêu cầu VI/EN và cross-lingual, CPU owner không GPU cho eval, mục tiêu 0 USD/tháng và warm TTFT p95 < 3 giây. FR-10 hiện ghi rerank tùy chọn và mặc định tắt khi deploy miễn phí. Mong muốn mới luôn có rerank cần được phản ánh vào PRD/ADR/TECH khi triển khai; báo cáo này chưa tự thay đổi hợp đồng đó.

[ADR-006](../02-architecture/adr/ADR-006-free-tier-providers-and-environments.md) vẫn `draft`. Lý do chọn BGE ban đầu là đa ngôn ngữ, tự host, eval độc lập quota và có Cloudflare deploy. Đây là tính khả thi và khả năng tái lập, chưa phải chứng minh tốt nhất trên dữ liệu SOP.

[Eval config](../../eval/configs/rq1-rq3-bge-m3.yaml) có BGE-M3 và BGE reranker v2 M3 nhưng chưa ghim revision. [Embedders](../../eval/sopilot_eval/embedders.py) giới hạn mọi SentenceTransformer ở 512 tokens; [retrievers](../../eval/sopilot_eval/retrievers.py) dùng pool mặc định 25 và cross-encoder max_length 512. Chunk size 800 trong YAML không đồng nghĩa 800 model tokens. Vì thế không thể dùng context tối đa trên model card để mô tả độ dài thực đã eval. Trong `eval/configs/` hiện chỉ thấy smoke và RQ1–RQ3; chưa thấy cấu hình RQ5 Qwen/E5 đã hoàn thiện.

Stack trên là **đích đề xuất**, không phải runtime đã tích hợp. Một sai khác quan trọng: [runtime `bm25_search`](../../services/ai-qa-service/src/db/repositories/chunk_repo.py) thực hiện PostgreSQL `ts_rank` và `plainto_tsquery('simple', ...)`, còn eval dùng BM25 tự cài với unigrams+bigrams. Tên hàm không chứng minh runtime là BM25; phải thống nhất lexical scorer hoặc báo cáo hai biến thể riêng trước khi lấy kết quả eval đại diện deploy.

## 3. Đánh giá các model

### Embedding

| Model | Nguồn chính xác | Đánh giá cho SOPilot |
|---|---|---|
| `BAAI/bge-m3` | MIT; >100 ngôn ngữ; dense 1024 chiều; model context 8192; có dense/sparse/multi-vector; query không bắt buộc instruction. [Model card BAAI](https://huggingface.co/BAAI/bge-m3) | Baseline hợp lý, đường chạy local/cloud rõ. Hybrid hiện tại dùng BM25 riêng; không nên lấy khả năng sparse/ColBERT của model làm lợi ích đã được khai thác |
| `Qwen/Qwen3-Embedding-0.6B` | Apache-2.0; 0.6B, >100 ngôn ngữ, model context 32K, output 32–1024 chiều; query instruction ảnh hưởng chất lượng. [Model card Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Challenger ưu tiên: đủ nhỏ để đưa vào phép thử CPU và cũng có Cloudflare; 0.6B không phải bằng chứng inference CPU nhanh hơn BGE |
| `intfloat/multilingual-e5-large-instruct` | MIT; 1024 chiều; khoảng 0.6B; tối đa 512 tokens; query cần task instruction, documents không cần. [Model card E5](https://huggingface.co/intfloat/multilingual-e5-large-instruct) | Đối chứng tốt cho RQ5, chưa có lý do thay baseline deploy ngay; kiểm soát truncation/instruction để phép so sánh công bằng |

Qwen công bố bảng MTEB multilingual với retrieval: Qwen3-0.6B **64.64**, E5 instruct **57.12**, BGE-M3 **54.60**; bảng dùng snapshot leaderboard **24/05/2025**. Đây là bằng chứng tác giả cho challenger, không phải ranking mới nhất, CPU benchmark hay kết quả SOP tiếng Việt. [Bảng của Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B#evaluation)

[VN-MTEB v1](https://arxiv.org/html/2507.21500v1) ghi retrieval BGE-M3 **39.84**, E5 instruct **40.88**; bộ benchmark có nhiều dữ liệu dịch và không có Qwen3 trong bảng được đối chiếu. Không suy ra E5 chắc thắng trên SOP/cross-lingual, cũng không dùng VN-MTEB để khẳng định Qwen3 tốt hơn khi chưa có phép đo đó.

### Reranker

`BAAI/bge-reranker-v2-m3` dùng Apache-2.0, là cross-encoder đa ngôn ngữ, chấm từng cặp query–passage; khác embedding ở cả vai trò lẫn license. BAAI khuyến nghị trong nhóm lựa chọn đa ngôn ngữ/hiệu quả, nhưng các từ “lightweight/fast” trên model card không phải cam kết 25 pairs p95 < 800 ms trên CPU owner. [Model card reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3)

**Giữ model này cho RQ2 và demo managed là hợp lý.** Không đặt nó làm inference local CPU trên service miễn phí RAM thấp trước khi đo. Không cần chuyển sang Qwen3-Reranker chỉ vì embedding chuyển sang Qwen: hai bước độc lập, thay reranker còn làm thay phân bố điểm và yêu cầu hiệu chỉnh refusal.

BAAI ghi `bge-reranker-base` nhắm Chinese/English, trong khi v2 M3 đa ngôn ngữ. Điều đó là lý do không ưu tiên base cho VI; câu ADR “yếu tiếng Việt” vẫn là giả thuyết chưa được đo, không phải kết quả SOP đã xác minh. [Danh sách BAAI](https://huggingface.co/BAAI/bge-reranker-v2-m3#model-list)

## 4. Cloudflare và sai khác nguồn cần giải quyết

Workers AI có **10.000 neurons/ngày**, reset **00:00 UTC = 07:00 Bangkok/Vietnam**. Free plan hết hạn mức trả lỗi, vượt free trên Paid phát sinh phí. Bảng giá hiện ghi BGE-M3 và Qwen3-Embedding-0.6B cùng **1075 neurons/triệu input tokens**; suy ra lý thuyết khoảng **9,3 triệu tokens/ngày** nếu quota chỉ dùng embedding, không phải quota tokens cố định hoặc số lượt hỏi được bảo đảm. [Pricing chính thức](https://developers.cloudflare.com/workers-ai/platform/pricing/)

Qwen hosted model dùng ID `@cf/qwen/qwen3-embedding-0.6b`, serving context **8192** thay vì 32K trên model card gốc. API có trường query/documents và instruction; phải kiểm tra parity local/cloud trên mẫu trước khi dùng kết quả local đại diện deploy. [Cloudflare Qwen](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/)

**Xung đột nguồn:** trang Cloudflare `@cf/baai/bge-m3` đang ghi **60.000 tokens**, ví dụ dùng `text` nhưng schema hiển thị `contexts/query`; BAAI mô tả model 8192. Không chốt 60K hoặc suy đoán body thật từ trang đang mâu thuẫn. Giữ chunks ngắn, kiểm tra API contract thực, dimensions, normalization và chất lượng local/cloud riêng. [Cloudflare BGE](https://developers.cloudflare.com/workers-ai/models/bge-m3/), [BAAI gốc](https://huggingface.co/BAAI/bge-m3)

## 5. Managed rerank và quota lặp lại

| Phương án | Đã xác minh từ nguồn chính thức | Kết luận |
|---|---|---|
| Pinecone Starter | BGE reranker v2 M3 **500 requests/tháng**, model reranking duy nhất trong Starter; tài liệu có `inference.rerank()` độc lập. [Pricing](https://www.pinecone.io/pricing/), [model/API](https://docs.pinecone.io/models/bge-reranker-v2-m3) | Khớp model nghiên cứu và quota monthly. Giữ Postgres/pgvector, không phải chuyển vector DB. Chưa đo độ trễ từ backend region |
| Cohere evaluation | **1000 API calls/tháng** dùng chung; rerank **10 requests/phút**. Production dùng paid key. [Limits](https://docs.cohere.com/v2/docs/rate-limits), [going live](https://docs.cohere.com/v2/docs/going-live) | Tốt cho đánh giá, không coi trial là phương án production miễn phí mặc định |
| Cohere `rerank-v4.0-fast` | Đa ngôn ngữ, có VI; tên fast không đảm bảo latency project. [Rerank overview](https://docs.cohere.com/v2/docs/rerank-overview) | Challenger API nếu chấp nhận chi phí/production key sau eval |
| Modal Starter | **$30 compute credit/tháng**, tự host CPU/GPU. [Pricing](https://modal.com/pricing) | Tự chủ model, nhưng compute credit không đổi trực tiếp thành số lượt; GPU luôn ấm tốn credit, scale-to-zero có cold start |

Modal có workspace usage budget trước credits và spend limit cho khoản thanh toán sau credits; tài liệu ghi dừng workloads gây thêm charge khi chạm spend limit. Không coi budget mặc định là bảo đảm miễn phí: ví dụ usage $100 và credits $30 tạo default spend $70. Kiểm tra giá trị dashboard trước deploy. [Modal budgets](https://modal.com/docs/guide/budgets)

500 lượt/tháng chỉ tương đương **khoảng 16 lượt/ngày** nếu chia đều 30 ngày, toàn hệ thống. FR-09 cho mỗi user 50 câu/ngày có thể làm hết quota một tháng trong 10 ngày chỉ bởi một user. Cần hạn mức chung tháng, đồng thời hạn mức ngày và chống lạm dụng; không cộng quota nhiều trial key để né giới hạn.

Voyage/Jina quota ban đầu đã thảo luận không phải cơ sở cho vận hành miễn phí lặp lại. Báo cáo này ưu tiên quota Pinecone tháng và Cloudflare ngày thay vì dùng quà đăng ký làm giả định lâu dài.

## 6. Phép đo quyết định cuối

Không dùng các khoảng CPU “3–15 giây” từng trao đổi làm benchmark: chưa có số đo trên máy owner, corpus thực, batch/thread/runtime cụ thể. Tương tự **p95 ≤800 ms** là ngân sách đề nghị cho riêng bước rerank, không phải tốc độ đã chứng minh hay chuẩn bắt buộc từ tài liệu; PRD chỉ có warm TTFT p95 <3 s.

1. **Chốt dữ liệu:** câu VI→VI, EN→EN, VI→EN, EN→VI và unanswerable; nhãn relevance do người duyệt, tách validation/test, cùng corpus/chunks cho ba embedding.
2. **Embedding:** BGE-M3, Qwen3-0.6B, E5 instruct theo đúng query instruction; ghim commit, tokenizer, pooling/normalization, max length, runtime. Ghi mức truncation, CPU model, threads, peak RAM, thời gian embed corpus và query p50/p95. Cấu hình 512-token chung là kiểm soát đầu tiên; long-context là phép thử riêng.
3. **Retrieval:** dense, BM25, hybrid RRF. Đo recall@5/@25, nDCG@10, MRR và tách bốn hướng ngôn ngữ. Không lấy mean toàn bộ che mất cross-lingual yếu.
4. **Rerank:** cùng candidates cố định, BGE local vs Pinecone BGE trên tập con cố định; pool 10/15/25, top 5, với/vắng rerank. Đo toàn thời gian request gồm tokenization/HTTP/queue, cold và warm riêng; tải đồng thời 1 rồi mức demo dự kiến. Chỉ thêm Cohere nếu quota/điều kiện cho phép.
5. **Ra quyết định:** ưu tiên đáp ứng recall/citation/refusal của PRD và warm TTFT p95; chọn model từ frontier chất lượng–độ trễ–RAM–quota. Nếu Qwen tốt hơn ở VI/cross-lingual và đạt vận hành, chuyển index; nếu lợi ích nhỏ hoặc CPU quá chậm, giữ BGE. Ghi bất định do sample nhỏ, không tuyên bố thắng tuyệt đối.
6. **Chốt vận hành:** timeout rerank và quota policy rõ; retry có giới hạn để không nhân quota. Metadata riêng `retrieval_score`, `rerank_score`, `rerank_status`, provider/model/version; không dùng lại cùng threshold cho dense/RRF/cross-encoder/API scores. Eval deploy end-to-end riêng, không đồng nhất local score với hosted score.

Các gate mở demo có rerank: hosted contract hoạt động; lexical parity đã kiểm tra hoặc khác biệt được ghi; corpus/index có provenance riêng; quota toàn hệ thống bảo vệ 500/tháng; timeout/degraded hay strict được quyết định; warm end-to-end TTFT đạt mục tiêu trên tải demo; citation/refusal/tenant isolation có evidence. Nếu chưa đạt gate nào, ghi rõ gate đó chưa xác minh, không biến kết luận nghiên cứu thành nghiệm thu.

## 7. Phạm vi xác minh và việc chưa làm

Đã đọc PRD/ADR/eval code/config và các trang tác giả/provider dẫn tại từng luận điểm. Chỉ tạo báo cáo này; không sửa code, schema, PRD, ADR hoặc tiến độ ticket; không khởi động stack, không model inference và không benchmark. Các phép đo và hợp đồng hosted API ở §6 vẫn là acceptance gates trước triển khai. `status: final` có nghĩa kết thúc đợt nghiên cứu nguồn, không có nghĩa hệ thống đạt chất lượng/latency hay đã được owner phê duyệt.

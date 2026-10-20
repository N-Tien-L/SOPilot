---
id: HANDOFF-research-03-methods-and-models
title: "Nhóm 03: Phương pháp, model và ma trận thí nghiệm tối thiểu"
status: final
type: handoff
scope: research
created: 2026-10-19
updated: 2026-10-19
refs:
  - docs/README.md
  - docs/04-reports/HANDOFF-research-01-scope-and-rqs.md
  - docs/04-reports/AUDIT-retrieval-stack-research-2026-10-18.md
---

# Phương pháp nghiên cứu và lựa chọn model

## 1. Quyết định phương pháp và giới hạn bàn giao

Chốt shortlist nghiên cứu gồm **hai dense embedding: `BAAI/bge-m3` và `Qwen/Qwen3-Embedding-0.6B`; một reranker: `BAAI/bge-reranker-v2-m3`**. BM25 là nhánh lexical độc lập. Chạy năm cấu hình retrieval trên toàn tập; chỉ rerank và sinh output trên một tập con cố định có người duyệt. RQ3 tái dùng output của pipeline có rerank, không gọi generator lại theo từng ngưỡng.

Phạm vi owner đã chốt được kế thừa từ nhóm 01 và yêu cầu hiện tại: corpus EN gốc, query EN/VI, hai hướng EN→EN và VI→EN; không dịch corpus. RQ1–3 là lõi; RQ5 bắt đầu bằng hai embedding; RQ4 ngoài lõi. RQ2–3 phải có output thật được người duyệt. Máy RAM tổng 32 GB, CPU không GPU; dùng một generator API miễn phí cố định, ưu tiên hoàn thành nhanh.

Đây là thiết kế để khóa trước test, **chưa có kết quả thực nghiệm hoặc model thắng**. `final` nghĩa đã hoàn tất bàn giao phương pháp; không thay trạng thái PRD/ADR/PLAN/ticket hoặc nghiệm thu hệ thống. Không chờ đầu ra nhóm 02/04: các đầu vào chưa có được ghi thành hợp đồng bàn giao ở §10. Quy mô dữ liệu, quota generator và CPU cụ thể chưa được xác minh.

Đã kiểm tra Git trước khi đọc: nhánh `fix/auth-google-roster-admission`, có nhiều thay đổi staged/unstaged/untracked sẵn, gồm `eval/` và các report đầu vào. File nhóm 03 chưa tồn tại lúc kiểm tra; không có nội dung cũ để ghi đè. Session này chỉ tạo file này, không đọc `.env`, cài/tải model, chạy benchmark, gọi API có key, sửa code hoặc tài liệu tiến độ.

## 2. Harness trên đĩa: khả năng thật và khoảng trống

Các nhận xét dưới đây từ đọc mã ngày 19/10/2026, không phải kết quả chạy. Đường dẫn tính từ gốc repo.

| Thành phần | Đã có thật | Hệ quả / phần cần nhóm 04 hoàn thiện |
|---|---|---|
| `eval/configs/rq1-rq3-bge-m3.yaml` | Dense/BM25/hybrid, hybrid trọng số 0.7/0.3, hybrid-rerank; `k=5`, chunk `800/100`; chưa ghim revision | Không dùng nguyên YAML làm ma trận cuối. Bỏ điều kiện legacy-weight khỏi lõi; thêm Qwen dense/hybrid và manifest đã khóa |
| `embedders.py` | SentenceTransformer, L2 normalization, dot product ở index; query prefix tùy config; mọi model bị cap tối đa 512 tokens | Có đường dense local, chưa chứng minh Qwen đúng pooling/instruction/tokenizer/runtime. `build_embedder` chưa truyền batch tùy config; chưa có log truncation |
| Cache | Corpus cache theo tên model/revision và hash text; query không cache; tên chưa chứa đầy đủ preprocessing/runtime | Cần fingerprint đầy đủ và query cache riêng; không tái dùng cache qua pooling/token limit/dtype khác nhau |
| `retrievers.py` | Dense exact scan trong RAM; BM25 tự cài (`k1=1.5,b=0.75`), NFC/lowercase/unigram+bigrams, query term được lấy unique | Đây là biến thể BM25 cụ thể, không gọi là default BM25 chung. Không có stemming, query translation hoặc sparse learned retrieval |
| Pool/RRF | `retrieve(..., pool=25)`; hybrid lấy 50 từ mỗi nhánh, RRF hằng số 60, weights mặc định 1/1, giữ 25; rerank toàn 25 | `run.py` không truyền pool từ config: thêm trường YAML hiện chưa làm nó có hiệu lực. `k` không đổi pool, không làm model chỉ rerank 5 |
| Lexical score bằng 0 | `_rank` vẫn trả chunk theo thứ tự ổn định, kể cả không khớp từ nào | Cần loại score BM25 ≤0 trước tạo lexical ranking cho cả BM25 và hybrid. Tránh coi thứ tự file tùy ý là bằng chứng lexical, đặc biệt VI→EN |
| Reranker | SentenceTransformers CrossEncoder nhận revision, `max_length=512` cho tổng query–passage | Chưa log activation/logit, pair truncation hoặc token hiển thị. Phải xác minh raw logit và sigmoid đúng một lần nếu cần |
| `corpus.py` | Chỉ `.md/.txt/.pdf`, mỗi trang PDF/`\f` chia riêng; splitter dùng `len()` ký tự | `800/100` là ký tự, không phải model tokens. Splitter không bảo đảm trần 800: có thể giữ đoạn gần 1600 ký tự. DOCX chưa được load |
| `metrics.py` | Recall trên target `{doc,pages?}`, hit, MRR tới depth thực trả về; nDCG@10 | `is_hit` chỉ nhận target khớp đầu tiên; document/page không đủ chứng minh đúng span. nDCG cộng gain nhiều chunk cùng target nhưng IDCG theo số target, nên có thể >1. Không dùng nDCG hiện tại để kết luận |
| Refusal sweep | Sweep top score trên mọi câu trong file; BM25 score, hybrid dense cosine của chunk đứng đầu RRF, hoặc score reranker | Không có split dev/test, coverage, output quality; `false_answer` chỉ là proxy nhận câu unanswerable. Không dùng sweep này để chọn ngưỡng từ test |
| `run.py` và artifacts | `run.json`, `metrics.json`, `per_question.jsonl`, `report.md`; commit/config/count/machine, latency retrieval gộp | Chưa lưu ranked chunk IDs, từng loại score, candidate pool, contexts/output, peak RAM, stage timing, split/subset và corpus hash. Commit không mô tả đủ working tree đang dirty |
| Tài nguyên | Index chứa cả dense và BM25 kể cả cấu hình BM25; dictionary giữ nhiều index/model trong cùng process | Không lấy thời gian dựng index hiện tại làm chi phí cần thiết của BM25. Chạy từng embedding và reranker theo giai đoạn, giải phóng model; đo cache hit/miss riêng |
| `eval/tests/test_eval.py` | Các test smoke, page constraint, RRF và sweep đơn giản | Chưa đủ chứng minh many-evidence, nDCG không đếm lặp, instruction Qwen, split leakage hoặc answer-level đúng |

Đối chiếu thêm `services/ai-qa-service/src/db/repositories/chunk_repo.py`: hàm tên `bm25_search` dùng PostgreSQL `ts_rank`/`plainto_tsquery('simple', ...)`, khác scorer eval. Kết quả đề xuất ở đây mô tả **offline harness**; chưa đại diện stack deploy hoặc warm TTFT của sản phẩm. Đã đọc `AGENTS.md`, `docs/README.md`, hai report yêu cầu và index `.agent/context/README.md`; không thay hợp đồng service.

## 3. Shortlist dựa trên nguồn chính thức

Nguồn được kiểm tra ngày **19/10/2026**. Cột thông số là fact từ tác giả; cột lựa chọn là suy luận cho thí nghiệm SOPilot, không phải benchmark CPU hay kết quả chất lượng dự án.

| Vai trò | Model và fact từ nguồn | Lý do giữ / giới hạn suy luận |
|---|---|---|
| E0: dense baseline | `BAAI/bge-m3`: MIT, 1024 chiều, hỗ trợ >100 ngôn ngữ, context kiến trúc 8192. [Model card BAAI](https://huggingface.co/BAAI/bge-m3), [paper BGE-M3](https://arxiv.org/abs/2402.03216) | Đối chứng multilingual đã có trong harness, không cần instruction query. Chỉ lấy dense; không tính khả năng sparse/ColBERT thành lợi ích của phép thử này |
| E1: dense challenger | `Qwen/Qwen3-Embedding-0.6B`: Apache-2.0, 0.6B, >100 ngôn ngữ, context 32K, output tối đa 1024 chiều. [Model card Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [paper Qwen3 Embedding](https://arxiv.org/abs/2506.05176) | Challenger khác họ, có retrieval cross-lingual và query instruction. Chọn bản 0.6B để giới hạn chi phí; số tham số/context/leaderboard không chứng minh nhanh hơn hoặc tốt hơn E0 trên SOP VI→EN |
| R: reranker duy nhất | `BAAI/bge-reranker-v2-m3`: Apache-2.0, multilingual cross-encoder chấm query–passage; ví dụ chính thức dùng pair max_length=512. [Model card reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Phù hợp bật/tắt rerank cho cả query EN và VI trên passage EN; đã có đường gọi local. Không ghép thêm reranker theo họ embedding, không mở so managed provider |

Không thêm E5/model thứ ba trong vòng lõi. Hai embedding đều chỉ xuất **một vector dense** trên mỗi chunk; BM25 dùng cùng corpus riêng. Không có phép thử long-context, Matryoshka, sparse BGE, ColBERT, fine-tune hoặc quantization trong ma trận này. Giấy phép model không thay giấy phép corpus.

### 3.1. Instruction, pooling và score phải ghi vào manifest

- **E0:** query/document không prefix; CLS dense pooling và L2 normalization. Khóa đúng dense-only; nếu dùng FlagEmbedding thì `return_dense=True`, `return_sparse=False`, `return_colbert_vecs=False`. Đối chiếu [implementation chính thức BGE-M3](https://github.com/FlagOpen/FlagEmbedding/blob/master/FlagEmbedding/inference/embedder/encoder_only/m3.py); không thay bằng mean pooling chung cho mọi model.
- **E1:** last non-padding token pooling, L2 normalization, 1024 chiều. Query đúng template `Instruct: {task}\nQuery:{query}` theo [usage Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B). Task EN cố định cho cả query EN/VI: `Given a question in English or Vietnamese, retrieve English passages that contain evidence to answer the question.` Document không instruction. Dùng adapter của model đúng phiên bản; kiểm tra dependency tương thích (card nêu Transformers ≥4.51.0), không mặc định dependency tối thiểu trong `pyproject.toml` đã đủ.
- **R:** input là query nguyên văn và passage EN, không thêm instruction embedding. Xếp hạng bằng raw logit; lưu tên activation thực tế. Nếu gate dùng sigmoid(logit), thực hiện đúng một lần; đây chỉ là biến đổi đơn điệu, **không phải xác suất answerable/đúng/đủ bằng chứng**. Khóa cùng revision và tokenization giữa score dev/test. [Usage reranker BAAI](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- Dense retrieval dùng cosine qua dot product hai vector đã L2-normalize; không trộn index dù hai model cùng 1024 chiều. Ghim model/tokenizer commit SHA thực khi chuẩn bị chạy; báo cáo này không bịa revision chưa kiểm tra.

## 4. Dữ liệu, split và tập con answer-level

Ký hiệu **N** = số query variants đã duyệt; **G** = số nhóm câu hỏi độc lập tương đối, gộp EN/VI cùng nghĩa, paraphrase và câu hỏi liên quan chặt cùng nội dung. N không phải G. Corpus/chunks cố định được dùng cho mọi query; chỉ chia **questions**, không chia mất bằng chứng corpus của test.

1. Nhóm 02 giữ định hướng dự kiến ≥100 query từ nhóm 01/đề cương; đây chưa phải số dữ liệu hiện có hoặc bảo đảm power. Không gọi smoke 3 tài liệu/9 câu là dataset nghiên cứu.
2. Split theo nhóm G, seed `20261019`, mục tiêu khoảng **30% dev / 70% test** theo query count. Gộp nhóm nguồn mục/chính sách gần trùng trước chia; cặp EN/VI không rơi sang hai split. Báo số G và N thực, sai lệch tỷ lệ do nhóm nguyên vẹn và phân bố nguồn.
3. Cả dev/test có EN→EN và VI→EN, answerable/unanswerable gần chủ đề; cố gắng có câu một bằng chứng và nhóm nhỏ nhiều bằng chứng. Không tạo query translation ở retrieval. Nếu dataset có paired EN/VI, giữ pair ID và phân tích paired; không bắt buộc mọi query có bản dịch.
4. Định nghĩa **S_dev, S_test** trước xem ranking/output: lấy phân tầng ngẫu nhiên từ từng split, mục tiêu `|S_dev|≈min(N_dev,20)`, `|S_test|≈min(N_test,40)`. Giữ cả nhóm EN/VI/paraphrase, làm tròn xuống ngân sách nếu cần. Mục tiêu bốn ô language × answerability cân bằng: khoảng 5/ô ở dev, 10/ô ở test nếu dữ liệu cho phép. Trong answerable, hướng tới khoảng 20% câu cần nhiều bằng chứng. Đây là quota thiết kế, không phải số lượng đã có.
5. Nếu ô thiếu mẫu, lấy mọi mẫu hợp lệ của ô đó, ghi thiếu và số thực; không nhân bản query để đủ quota, không lựa câu theo score/model thắng. Báo G của subset; nhóm quá ít thì kết luận exploratory. Lưu subset IDs/seed/hash trước khi chạy điều kiện so sánh.
6. Nhãn output của S_dev dùng hiệu chỉnh; **S_test không dùng chọn prompt, model, chunking hoặc threshold**. Khóa gold và thiết kế trước mở kết quả test. Người vận hành có thể truy xuất test để thu artifacts sau khóa nhưng không dùng nó quay lại tune.

S = S_dev ∪ S_test, thường nhắm tối đa khoảng 60 query variants, không cam kết con số khi nhóm 02 chưa xác minh. Subset được làm giàu lớp để duyệt nhanh, nên coverage/risk trên S chỉ mô tả phân bố S. Nếu có xác suất lấy mẫu rõ có thể thêm ước lượng trọng số theo test gốc; không gọi coverage cân bằng 50/50 là tỷ lệ triển khai thực.

## 5. Relevance và metric

### 5.1. Bằng chứng thay cho khớp tên file

Gold mỗi câu answerable gồm một hoặc nhiều **tập bằng chứng đủ**. Trong mỗi tập, các đơn vị bằng chứng là yêu cầu bắt buộc (AND); một đơn vị có thể có nhiều span thay thế tương đương (OR). Hai tập đủ khác nhau cũng là OR. Ví dụ cần cả điều kiện được nghỉ và thời hạn thông báo: tìm được nhiều chunk nói lại điều kiện vẫn chưa đủ hai đơn vị.

Mỗi span có document/version/hash, trang hoặc heading và offsets/quote; map sang chunk IDs **sau** khóa chunking. Chỉ hit khi phần văn bản hệ thống thực thấy chứa đủ nội dung yêu cầu, không chỉ cùng trang. Một chunk có thể thỏa nhiều đơn vị; nhiều chunk cùng thỏa một đơn vị chỉ tính một lần. Nếu một bằng chứng bị chia, gold phải chỉ rõ tổ hợp chunk/span đủ, không tự cho từng nửa một hit đầy đủ.

Với câu q, tập đủ j có m_j đơn vị, C_j(k) là số đơn vị được top-k đáp ứng:

- `EvidenceRecall@k(q) = max_j C_j(k)/m_j`.
- `AllEvidence@k(q) = 1` khi tồn tại tập j được đáp ứng toàn bộ; `AnyEvidenceHit@k(q) = 1` khi tìm ít nhất một đơn vị.
- Dùng max trên **một tập đủ**, không cộng các mảnh không tương thích từ nhiều cách trả lời. Với một tập duy nhất, đây là recall trên đơn vị bằng chứng.

Gold phải được người duyệt kiểm tra độc lập với cấu hình thắng; lưu bất đồng/adjudication. Unanswerable cần được rà toàn corpus hợp lệ, không chỉ vài top chunks. Nếu dùng pooling để tìm thêm evidence: hợp nhất top-25 của cả năm cấu hình retrieval và kết quả rerank trong S, ẩn tên hệ thống, bổ sung kiểm tra nguồn; qrels dựa pool chưa đầy đủ phải được ghi rõ. Chỉnh gold sau thấy test chỉ sửa lỗi nhãn có nhật ký rồi tính lại **mọi** cấu hình; không tune hệ thống theo gold đã sửa.

### 5.2. Metric chính và phụ theo RQ

| RQ | Metric chính / population | Metric phụ và giới hạn |
|---|---|---|
| RQ1 | Macro **EvidenceRecall@5** trên answerable test, hybrid–dense và hybrid–BM25 | AllEvidence@5, AnyEvidenceHit@5, EvidenceRecall@10/@25, MRR@25 của bằng chứng đầu tiên; báo riêng hai hướng và số mẫu. MRR không chứng minh tìm đủ nhiều bằng chứng |
| RQ1b | Cùng chênh lệch Recall@5 tách EN→EN, VI→EN | Nếu có cặp nghĩa: chênh lệch tác động hybrid giữa query VI/EN; không giả định BM25 VI luôn bằng 0 |
| RQ2 | **Grounded answer success** rerank-on trừ off, trên answerable S_test, gate tắt | Recall@5/AllEvidence@5 trên S_test; correctness, faithfulness, citation precision/completeness, tự từ chối, thời gian rerank. Ranking gain và answer gain phải kết luận riêng |
| RQ3 | **Selective risk của output** cùng coverage tại τ đã khóa trên toàn S_test | False refusal, false acceptance, wrong-accepted rate toàn tập, utility/correct-answer yield, kết quả từng lớp/ngôn ngữ và confusion counts; không thay output bằng score proxy |
| RQ5 | Chênh lệch Recall@5 E1–E0 ở **dense** và **hybrid**, answerable test | AllEvidence@5, tài nguyên và tương tác `Δ_hybrid−Δ_dense`; không tuyên bố embedding tốt nhất từ riêng dense hoặc riêng leaderboard |

Recall chỉ average trên answerable; unanswerable có zero gold không được gán recall=0 rồi trộn mean. Macro theo query, báo riêng N/G; kết quả theo semantic group là sensitivity bổ sung. Top-k chứa ít hơn k candidates vẫn dùng số thực, không pad chunk không khớp.

Không lấy `ndcg@10` hiện tại làm metric lõi. Chỉ thêm **nDCG@10 chuẩn** như phân tích phụ khi nhóm 02/04 có chunk qrels độc nhất, định nghĩa relevance/gain và IDCG cùng đơn vị, test miền [0,1], xử lý overlap và độ sâu; không âm thầm gọi metric gain mới theo evidence là nDCG chuẩn. Không cần sửa nDCG để chặn toàn nghiên cứu nếu EvidenceRecall/AllEvidence/MRR đã được kiểm chứng.

### 5.3. Rubric output thật cho RQ2–3

Người duyệt thấy query, gold spans/reference, context **đã cấp cho generator**, output và citations; ẩn config/model và đảo thứ tự điều kiện. Duyệt cả output không rerank và có rerank trên cùng S, kể cả unanswerable. Reference là hướng dẫn kiểm tra, không ép trùng chuỗi hoặc ngôn từ.

- **Correctness/completeness:** đáp ứng đủ yêu cầu và điều kiện/số liệu quan trọng; ghi correct / partial / incorrect. Partial tính chưa thành công ở metric nhị phân chính.
- **Faithfulness:** tách atomic factual claims; đánh dấu supported / contradicted / unsupported theo context được cấp. Claim đúng ngoài corpus nhưng không có căn cứ vẫn không faithful. Báo tỷ lệ supported và tỷ lệ câu có claim sai/không hỗ trợ.
- **Citation precision:** tỷ lệ cặp claim–citation trỏ đúng vị trí và nguồn thực hỗ trợ claim; **citation completeness:** tỷ lệ claim cần dẫn có ít nhất một citation hỗ trợ. URL/document đúng nhưng span không hỗ trợ là lỗi. Báo macro theo câu và raw counts; mẫu số rỗng báo N/A, không tự cho 100%.
- **Grounded answer success = 1** khi thực trả lời, correctness đầy đủ, mọi factual claim quan trọng được context hỗ trợ và có citation hỗ trợ; ngược lại 0. Đây là metric dự án đã định nghĩa, không lấy tự động judge hoặc tên ALCE làm bảo chứng. Tự từ chối câu answerable tính 0.
- **Wrong answer = 1** cho output thực trả lời mà incorrect/partial hoặc có claim không được hỗ trợ. Lỗi citation thuần túy được báo riêng; không đánh đồng thiếu citation với mọi loại sai nội dung. Thêm tỷ lệ không đạt grounded success trong các output đã trả lời để bao gồm lỗi citation.

Thiết kế tách correctness và citation kế thừa [ALCE (Gao et al., EMNLP 2023)](https://aclanthology.org/2023.emnlp-main.398/); rubric EN/VI ở đây do người duyệt áp dụng, không giả định automatic evaluator của paper đã được xác thực trên SOPilot. Dùng ít nhất một reviewer biết VI/EN; nếu có người thứ hai, ưu tiên rà toàn bộ ca bất đồng/sai/refusal và tối thiểu 20% output lấy ngẫu nhiên, báo agreement trước adjudication. Nếu chỉ một người duyệt, công bố hạn chế và không bịa inter-rater agreement.

## 6. Các biến kiểm soát và ngân sách truy xuất

| Biến | Khóa cho vòng lõi | Vì sao / ghi nhận |
|---|---|---|
| Corpus | Một snapshot EN, extraction và quyền truy cập cố định, checksum cả nguồn và text | Không dịch corpus; không đổi tài liệu giữa cấu hình |
| Chunking | Khởi đầu paragraph/page-aware `size=800, overlap=100` **ký tự** để kế thừa harness; thêm kiểm tra trần token chung trước freeze | Nếu đoạn dài vượt trần, chia tiếp ở sentence boundary một lần cho mọi model; không chunk theo model riêng, không sweep nhiều size |
| Trần chunk chung | Mỗi chunk ≤384 tokens dưới **mỗi** tokenizer của E0/E1/R; metadata tiêu đề nếu đưa vào cũng nằm trong budget | Chọn ranh giới văn bản chung thỏa mọi tokenizer. 384 là budget thiết kế để pair ngắn, không phải claim giới hạn kiến trúc |
| Query | Nguyên văn, không rewrite/translate; query embedding ≤128 tokens gồm instruction/special tokens, query reranker raw ≤96 tokens | Query quá dài được người soạn rút gọn trước freeze, không cắt âm thầm đổi nghĩa; log độ dài theo từng tokenizer |
| Encode/pair | Embedding cap 512; reranker **tổng pair** cap 512, bảo toàn query, passage cắt sau nếu bắt buộc | Assert độ dài pair thực gồm special tokens. Mục tiêu vòng lõi không có evidence bị cắt; lỗi phải sửa chunk/scope trước test. Lưu visible text và tỷ lệ truncation, không chỉ max length |
| Dense | Exact cosine, L2 query/document, dimension=1024 cho cả E0/E1 | Không thêm ANN recall/quantization làm biến nhiễu |
| Lexical | BM25 implementation eval: NFC/lowercase, unigrams+bigrams, k1=1.5,b=0.75, không stemming, giữ dấu | Không tune theo ngôn ngữ; loại score≤0. Ghi rõ biến thể lexical và runtime parity chưa đạt |
| Branch depth | Dense top-50, BM25 top-50 positive-score; giới hạn bởi số chunk C thực | Đây là đầu vào fusion, khác rerank candidate pool |
| Fusion | `RRF(d)=Σ_b 1/(60+rank_b(d))`, rank bắt đầu 1, weights 1/1; chunk không có trong nhánh đóng góp 0 | Giữ hằng số 60, không sweep trọng số. Đây là baseline từ [paper RRF gốc](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), không phải tối ưu đã đo trên SOP |
| Candidate pool P | Top-25 sau dense/BM25 hoặc fusion; hybrid union ≤100 rồi giữ 25 | Rerank chỉ đổi thứ tự **cùng** P, không lấy thêm ứng viên; lưu chunk IDs, rank/score từng nhánh, RRF, rerank logit |
| Context/output k | Top-5 sau sắp hạng, cùng budget context 2560 generator tokens và output tối đa 512 tokens | Nếu không vừa budget, dùng một quy tắc packing cố định theo rank và ghi evidence thực thấy; không để provider cắt prompt ngầm. Khóa quy tắc trước test |
| Ties/dedup | Stable chunk ID làm tie-break; cùng chunk ID chỉ xuất hiện một lần | Không dùng ngẫu nhiên thứ tự file; không cho chunks overlap tăng recall cùng evidence |
| Runtime | CPU FP32, inference/eval mode, model load tuần tự; batch khởi đầu 4, query batch 1, cố định threads theo pilot dev | Không copy GPU FP16/FlashAttention từ ví dụ. Có thể giảm batch theo RAM trong pilot rồi khóa; báo riêng thông số mỗi model |

Hằng số 50/25/5 giữ gần harness để giảm công thay đổi. Đo **candidate EvidenceRecall@25/AllEvidence@25** trước rerank và Recall@5 sau rerank: reranker không cứu được bằng chứng đã bị loại khỏi P. Nếu P=25 quá chậm, ghi pilot dev và có thể chốt P=15 cho **toàn bộ** H0/H0R liên quan trước test, cập nhật manifest; không chọn P riêng theo query hoặc sau xem test. Nếu không chạy nổi model, báo RQ tương ứng thiếu evidence thay vì thay model thứ ba âm thầm.

Đo tài nguyên gồm load/cold start, corpus embedding một lần/model, query embedding, BM25/dense/fusion, rerank, context packing và API generation; peak process RAM, wall time, CPU/threads, p50/p95 kèm n. Cache phục vụ giảm công nhưng benchmark query phải phân biệt cached/uncached; không đưa cache lookup vào thay query encoding rồi gọi là latency thực. Không cộng thời gian API biến động vào suy luận tốc độ embedding. Không bảo đảm TTFT/NFR từ phép đo offline này.

## 7. Generator cố định và thiết kế refusal

### 7.1. Một generator API cho mọi điều kiện answer-level

Chọn **một model ID/version API có free quota khả dụng** khi thực hiện; chưa cần chọn provider để khóa phương pháp. Không giả định có free tier vô hạn hoặc quota cụ thể. Khóa model/version, system/user prompt hash, context template/citation IDs, temperature=0 nếu hỗ trợ, top_p, seed nếu hỗ trợ, context/output limits, retry policy và response metadata. Cùng generator trả lời theo ngôn ngữ query, dùng context EN. Temperature 0 không bảo đảm hoàn toàn deterministic.

Prompt chung: chỉ trả lời dựa trên context, không thêm kiến thức bên ngoài; nêu đủ điều kiện quan trọng, dẫn `[chunk_id]` cho từng factual claim; nếu thiếu bằng chứng thì tự từ chối rõ. **Không đổi prompt giữa rerank off/on hoặc giữa các τ.** Bản prompt cuối và 2–4 ví dụ kiểm tra định dạng từ dev được khóa trước test; không đưa gold test vào request. Reviewers xem context thật, không chỉ top-k IDs.

Sinh raw output **một lần cho mỗi query × hai context điều kiện H0/H0R** trong S; cache request/response nguyên vẹn. Số generation hữu ích dự kiến `2|S_dev|+2|S_test|`, khoảng 120 nếu đủ quota subset mục tiêu, không nhân theo số thresholds hoặc hai embedding. Pilot dev có thể tái dùng nếu cùng prompt cuối; mọi output từ prompt cũ phải thay đồng bộ. Retry chỉ transport/rate-limit có giới hạn, không retry vì câu trả lời xấu. API error/timeout là missing, không gán refusal đúng; báo n mất cặp, không phân tích một phía như paired. Khi provider không còn model/quota: checkpoint và đợi, hoặc version nghiên cứu mới chạy lại **mọi điều kiện so sánh bị ảnh hưởng**; không trộn generator khác.

### 7.2. Pipeline và ngưỡng cho RQ3

Khóa RQ3 trên **H0R = BGE-M3 hybrid + reranker R**, không chọn pipeline thắng sau xem test. RQ3 không đồng thời thay embedding, retriever, reranker hoặc generator. Gate score `s(q)=max raw reranker logit` trong pool P, tức score của top-1 sau rerank; pool rỗng thì bắt buộc refuse. Gate nhận nếu `s≥τ`, từ chối nếu `s<τ`. Không dùng RRF làm confidence; không chuyển τ sang cosine, sigmoid hoặc model khác mà không hiệu chỉnh lại.

Baseline `τ=−∞` là **gate-off / nhận mọi query có pool**, không bảo đảm generator luôn phát ra answer: generator vẫn có thể tự từ chối theo cùng prompt. Ghi nhãn riêng gate-refusal và generator-refusal. Không gọi baseline này là “luôn trả lời” nếu output thực tế có refusal; ép generator trả lời bằng prompt khác sẽ gây nhiễu nên nằm ngoài lõi.

Cho mỗi output raw được người duyệt, lưu `a` (gold answerable), `r_gen` (generator thực tự từ chối), `w` (trả lời sai/không hỗ trợ), `g` (grounded success). Với ngưỡng τ, đặt `cτ=1` khi gate nhận **và** output thực là câu trả lời; các ca còn lại là final refusal. Replay offline chỉ thay output bị gate chặn bằng thông báo refusal cố định, không sửa câu trả lời còn giữ.

Với n=|S|, A/U là tập gold answerable/unanswerable, n_A/n_U là số phần tử tương ứng, báo raw numerator/denominator:

| Chỉ số output cuối | Công thức / cách đọc |
|---|---|
| Coverage | `Σcτ/n`; thêm gate acceptance `Σ1[s≥τ]/n` để thấy tự refusal của generator |
| False refusal | `Σ_{q∈A}(1−cτ)/n_A`, gồm gate và generator; đồng thời phân rã hai nguyên nhân |
| False acceptance | `Σ_{q∈U}cτ/n_U`; thêm gate-only acceptance trên U, không gọi đây là đo correctness của mọi câu answerable |
| Selective risk | `Σ cτ·w / Σcτ`: lỗi nội dung/faithfulness trong các output thực trả lời, gồm cả lỗi trên A |
| Wrong-accepted rate | `Σ cτ·w/n`: số query bị nhận trả lời sai trên toàn subset |
| Correct-answer yield | `Σ cτ·1[correct và faithful]/n`; thêm grounded-success yield để thấy lỗi citation |
| Unanswerable refusal | `Σ_{q∈U}(1−cτ)/n_U`; cần đọc cùng false refusal và coverage |

Output trả lời nội dung trên unanswerable được tính `w=1` theo corpus đã khóa; câu trả lời rỗng/lẩn tránh phải reviewer phân loại rõ. Mẫu số 0 báo N/A. Bảng confusion answerability không thay bảng chất lượng output. Risk–coverage là cách mô tả từ [selective classification](https://arxiv.org/abs/1705.08500); score gate ở đây chưa được hiệu chuẩn xác suất hay bảo đảm thống kê kiểu paper.

### 7.3. Chọn τ trên dev, khóa trước test

1. Chỉ dùng H0R scores và **output labels trên S_dev**. Tập candidate thresholds là midpoint giữa các score dev phân biệt, cộng −∞/+∞; dùng precision đầy đủ, không làm tròn trước quyết định. Đây là sweep rẻ trên output cache.
2. Quy tắc thiết kế đề xuất: trong các τ có **coverage thực ≥0.50** và **false refusal ≤0.20** trên S_dev, chọn τ có wrong-accepted rate nhỏ nhất. Nếu hòa, chọn coverage cao hơn; nếu còn hòa, τ thấp hơn. Hai ràng buộc là operating goals do nhóm 03 đề xuất để tránh từ chối gần hết, chưa phải chuẩn được chứng minh hoặc phê duyệt sản phẩm.
3. Nếu không có τ khả thi, giữ baseline gate-off làm đối chứng, báo **chưa có operating point đáp ứng ràng buộc**. Không nới ràng buộc trên test. Nếu có τ nhưng cải thiện dev quá nhỏ/CI rộng, vẫn báo đánh đổi và độ bất định; không mặc định H3 đúng.
4. Ghi manifest gồm τ*, định nghĩa score/activation, revision, hash dev/subset/prompt, constraints, thời điểm freeze; sau đó chạy/evaluate S_test một lần với τ* và gate-off. Báo achieved coverage/false refusal/false acceptance/risk trên test dù xấu hơn dev.
5. Có thể vẽ test risk–coverage toàn đường sau khi khóa như phân tích mô tả, đánh dấu τ* đã chọn; không chọn operating point mới từ đường test. Một τ chung cho cả EN/VI để giảm tuning; báo riêng các hướng, không tạo ngưỡng ngôn ngữ sau thấy kết quả.

Replay dùng output thật trên S trả lời câu hỏi chất lượng khi selective answering; nó không đo số API call/latency tiết kiệm ngoài hệ thống thực. Gate triển khai trước generation có thể tránh gọi API, nhưng cần kiểm tra call path riêng. Score top-1 không biết chắc đủ nhiều bằng chứng; đây là giới hạn cần ghi nếu gate nhận câu chỉ đủ một phần.

## 8. So sánh paired, bất định và quy tắc quyết định

### 8.1. Phân tích khóa trước test

- Đối chiếu cùng query IDs/context budget, dùng per-query delta và win/tie/loss. Resample **nhóm G** (giữ EN/VI/paraphrase cùng nhau) trong paired cluster bootstrap 5000 lần, seed cố định, lấy CI 95% cho delta và các rate/risk/yield. Không resample claim hoặc hai bản dịch như độc lập. Báo N, G, số discordant groups; nếu ít nhóm, CI bất ổn và không đủ power thì ghi rõ.
- Với subset: bootstrap lại nhóm của S, giữ cùng cặp output. Với RQ3 test, giữ τ* cố định trong mọi resample; không tune lại bằng test bootstrap. CI này có điều kiện trên dev threshold và dataset; không bao gồm mọi bất định do chọn nguồn, dịch câu hỏi hoặc annotation. Bootstrap dev chọn lại τ có thể thêm như sensitivity, không là điều kiện chạy nhanh.
- Nếu cần p-value cho kết luận xác nhận, dùng paired randomization/sign-flip theo **group**, cùng định nghĩa metric; tránh t-test độc lập trên query variants. Có thể bỏ p-value nếu chỉ báo effect+CI và mô tả thận trọng. [Dror et al., ACL 2018](https://aclanthology.org/P18-1128/) là cơ sở cần chọn phép kiểm phù hợp thiết kế, không bảo chứng riêng bộ dữ liệu này.
- Tách family hai contrast RQ1 (H0−D0, H0−M), hai contrast RQ5 (D1−D0,H1−H0); nếu đưa ra tuyên bố theo p-value thì Holm trong từng family. RQ2 primary output và RQ3 operating point là hai câu hỏi khác, không chọn chỉ metric thuận lợi. Ngôn ngữ/metric phụ là exploratory; không dùng nhiều lát cắt để tuyên bố thắng tổng thể.
- Ghi CI paired delta theo **điểm phần trăm tuyệt đối**, không nhầm relative percent. Thiếu ý nghĩa thống kê không chứng minh tương đương. Không có claim power từ N dự kiến; một thay đổi binary trên test subset nhỏ có thể đã là nhiều điểm phần trăm.

### 8.2. Mức cải thiện thực tiễn và chọn cấu hình

Các mức sau là **quy tắc quyết định thiết kế trước test**, không phải kết quả, chuẩn từ paper hoặc mục tiêu PRD đã được owner duyệt:

| Quyết định | Mức đáng quan tâm và quy tắc |
|---|---|
| Hybrid RQ1 | Recall@5 tăng ≥0.03 tuyệt đối so baseline đang so; CI delta nằm trên 0 mới gọi có bằng chứng hướng cải thiện. Muốn nói hybrid hơn cả hai phải đáp ứng cho cả D0 và M; thắng riêng BM25 không đủ |
| Rerank RQ2 | Grounded answer success trên A của S_test tăng ≥0.05 tuyệt đối; CI delta trên 0 mới hỗ trợ cải thiện output. Chỉ ranking tăng thì kết luận ranking-only. Báo thời gian/peak RAM bổ sung; nếu hiệu quả mờ và chậm hơn, chọn off cho cấu hình nhanh |
| Refusal RQ3 | Ưu tiên giảm wrong-accepted rate ≥0.05 tuyệt đối so gate-off, CI delta lỗi dưới 0, cùng coverage ≥0.50 và false refusal ≤0.20 trên test |
| Embedding RQ5 | E1 đáng chuyển nếu hybrid Recall@5 tăng ≥0.03, CI trên 0, VI→EN không có suy giảm thực tiễn ≥0.03, và tài nguyên nằm trong budget pilot đã khóa; dense riêng dùng để giải thích chứ không thay hybrid contrast |

Nếu sample quá nhỏ để phân biệt các mức này, báo chưa đủ bằng chứng thay vì tăng effect bằng chọn câu dễ. Báo cả point estimate và CI có chứa mức thực tiễn không; trường hợp point estimate vượt mức nhưng CI rộng vẫn chưa xác nhận. Mức 0.03/0.05 không được đổi sau xem test.

Quy tắc vận hành: chốt cấu hình đề xuất **bằng dev**; test chỉ kiểm chứng, không dùng để mò cấu hình mới. Thứ tự mặc định E0 hybrid; nếu dev không cho thấy lợi ích thực tiễn so dense thì có thể đề xuất dense cho demo, nhưng RQ1/2/3 vẫn giữ các contrast định trước. Chọn E1 chỉ nếu dev đáp ứng quy tắc chất lượng/tài nguyên; khi bất định lớn giữ E0 như baseline có sẵn, không gọi E0 thắng. Nếu không cần rerank để cải thiện output, đề xuất off; RQ3 trên H0R vẫn là kết quả nghiên cứu độc lập, không tự chuyển ngưỡng sang cấu hình demo khác.

Pilot dev đo RAM trống/thời gian để khóa budget thực, không hỏi lại owner phần cứng/deadline. Chỉ load một model nặng, không gây swap kéo dài; nếu không đạt, checkpoint và báo tính khả thi có điều kiện. Dùng Pareto chất lượng–thời gian–RAM: với lợi ích chưa rõ ưu tiên cấu hình ít chi phí đã có. Không gán ngân sách mili-giây giả như đã đo; p95 từ vài chục query phải báo n và không coi đạt NFR public.

Kết luận hợp lệ gồm: hỗ trợ giả thuyết trong phạm vi mẫu; kết quả âm/ngược; hoặc chưa đủ evidence do CI/gate dữ liệu/công cụ. Refusal giảm lỗi nhưng coverage sụt hoặc từ chối nhầm cao là đánh đổi không đạt operating goal; không tô thành thành công. Mục tiêu draft Recall@5≥0.80/citation precision≥0.85/từ chối đúng U≥0.80 từ nhóm 01 được báo riêng, không thay thế contrast hoặc hợp thức hóa hệ thống từ chối mọi câu.

## 9. Trình tự chạy tối thiểu sau bàn giao

1. Nhóm 02 bàn giao corpus EN snapshot, question groups/split và span gold; nhóm 04 kiểm chứng metric, positive-score lexical, adapter/instruction, provenance và output export. Chưa đủ thì dừng phần kết luận bị ảnh hưởng, không lấy smoke thay dữ liệu.
2. Pilot dev ngắn 4 query gồm hai hướng và A/U để kiểm tra token visibility, pooling, score, RAM/batch/threads và prompt/citation format. Không dùng pilot để thử nhiều model. Khóa manifest/chunks/split/subset/metric/budget; chưa đọc kết quả test để chọn.
3. Encode corpus một lần E0, cache query vectors và full rankings; chạy D0/M/H0. Encode E1 trong process/giai đoạn khác, chạy D1/H1; không embed lại BM25. Có thể dùng query vectors/rank caches để không tính lặp chi phí giữa configs.
4. Trên S, lấy **đúng P của H0**, lưu rồi chạy R một lần/pair; H0R đổi thứ tự P. Số pairs `Σ_{q∈S}|P_q|≤25|S|`; không rerank mọi N để tiết kiệm CPU. Tầng RQ2 retrieval cũng chỉ đại diện S, không nói đã đo toàn test.
5. Sinh hai raw outputs/query trên S, người duyệt theo §5; dùng S_dev chọn τ, khóa trước mở labels/output quality S_test. RQ2 gate-off; RQ3 replay H0R cùng output đã duyệt. Không phát sinh calls theo từng τ hoặc E1.
6. Tính paired test deltas/CI, theo ngôn ngữ và lỗi multi-evidence/truncation/candidate miss/generation/citation/refusal; báo chi phí thực. Dữ liệu thiếu, API lỗi hoặc RQ chưa chạy phải được để trống có lý do, không bịa kết quả.

Chi phí thiết kế: hai lần corpus embedding trên C chunks, tối đa 2N query embeddings (cache dùng chung dense/hybrid), năm retrieval rankings/query, ≤25|S| reranker pairs, khoảng 2|S| generation hữu ích và output reviews. RQ3 không nhân chi phí generation. Không cam kết phút/giờ khi chưa đo CPU và C/N.

## 10. Hợp đồng bàn giao không phụ thuộc việc chờ nhóm khác

### 10.1. Cho nhóm 02 — dữ liệu

- Cung cấp corpus EN gốc có quyền dùng, snapshot/version/license/URLs/hash, text extraction và ranh giới chủ đề; C/N/G thực. Không yêu cầu dịch corpus; query VI/reference VI cần duyệt nội dung theo bằng chứng EN.
- Group IDs gộp semantic pairs/paraphrase/nguồn mục gần trùng; split dev/test và subset IDs bằng seed/strata đã nêu. Bàn giao counts theo language×answerability×single/multi-evidence và số nhóm độc lập, thiếu ô nào ghi rõ.
- Gold sufficient evidence sets/alternatives, spans ổn định theo source, answerability toàn corpus/quyền, reference/key facts; map chunk sau freeze, kiểm tra visible spans sau tokenization/context packing. Không dùng `{doc,pages}` làm đủ gold cuối.
- Chuẩn bị near-topic unanswerable (thiếu quy định, thiếu điều kiện/số liệu, premise sai), không chỉ câu ngoài chủ đề. Kiểm tra khả năng trả lời qua toàn corpus, giữ người duyệt và lịch sử bất đồng.
- Đủ bằng chứng để đọc paired EN/VI mà không coi hai câu là hai quan sát độc lập; không bịa số lượng/đã duyệt khi chưa có artifacts. Nếu thiết kế dữ liệu khác tỷ lệ đề xuất, phản hồi số thực và lý do trước test; không tự giảm scope answer-level xuống retrieval-only.

### 10.2. Cho nhóm 04 — công cụ

- Làm hữu hiệu branch depth/pool/k, weights/RRF constant, lexical positive-score filtering; lưu candidate IDs/hash trước/sau rerank. Test cùng P on/off, case BM25 zero-match, ties và candidate miss.
- Adapter E0/E1 đúng pooling/prefix/L2/dimension, pin revisions/runtime; enforce chung chunks/token caps và visible text, kiểm thử instruction chỉ query, pooling Qwen last non-padding. Không tải/chạy model chỉ để hoàn tất tài liệu nhóm 03.
- Evidence metrics hỗ trợ AND/OR alternatives, một chunk nhiều evidence và nhiều chunks cùng evidence, split span tổ hợp; test bounds/duplicate invariance/MRR depth/empty-gold N/A. Sửa hoặc bỏ nDCG lỗi khỏi kết luận; không chỉ đổi tên cột.
- Split/subset manifest và guard không tune test; tách gate score khỏi dense/RRF/rerank scores. Sweep có endpoint ±∞, tie policy, coverage/confusion/raw denominators, τ freeze; proxy retrieval phải ghi nhãn proxy.
- Thêm answer request/context/output/citation export, reviewer labels, replay gate, API missing/error log. Lưu generator ID/version/prompt hash/decoding/usage/time; không lưu secrets. Kiểm tra một model và prompt cho mọi điều kiện so sánh.
- Provenance gồm code commit **và dirty diff/file hashes**, corpus/chunk/qrels/split/subset/config hashes, revision/tokenizer/pooling/length/dtype/threads/batch/packages, score activation và cache fingerprint. Các file untracked hiện tại không được phản ánh chỉ bằng HEAD.
- Instrument stage timing/peak RAM/cold-warm/cache; tránh giữ cả hai embedding và reranker đồng thời. BM25 không phải load/embed dense để được báo chi phí lexical độc lập. Kiểm tra offline/runtime lexical parity riêng nếu báo kết quả deploy.

Đây là yêu cầu công cụ cho nhóm 04, không phải khẳng định đã sửa. Không mở ticket hoặc cập nhật PLAN trong session này. Nhóm 05/06 có thể dùng §9 và rubric để thực thi/kiểm chứng sau khi các gate dữ liệu/công cụ đạt; không cần nhóm 03 chờ chúng mới chốt shortlist/phương pháp.

## 11. Shortlist cuối, ma trận cuối và quyết định còn đối chiếu

**Shortlist cuối:** E0 `BAAI/bge-m3` dense; E1 `Qwen/Qwen3-Embedding-0.6B` dense; R `BAAI/bge-reranker-v2-m3`; một generator API miễn phí cố định chưa cần chọn provider. Không model thứ ba, không reranker thứ hai, không full factorial embedding×retriever×reranker×gate×generator.

| ID / so sánh | Cấu hình | Retrieval chạy ở đâu | Output người duyệt | RQ được trả lời |
|---|---|---|---|---|
| D0 | E0 dense, rerank off | Toàn N, báo dev/test riêng | Không | RQ1 baseline; RQ5 dense baseline |
| M | BM25, không cần dense inference | Toàn N, dùng chung một kết quả lexical | Không | RQ1 lexical baseline |
| H0 | E0 dense + BM25, RRF 1/1, rerank off | Toàn N; lưu P cho S | Một output/query trên S, paired với H0R | RQ1 hybrid; RQ2 off; RQ5 hybrid baseline |
| D1 / H1 | E1 dense / E1+BM25 RRF, rerank off (**hai** cấu hình) | Toàn N, reuse BM25 | Không | RQ5: D1−D0 và H1−H0 |
| H0R | H0 + R trên cùng P, gate off | Chỉ S_dev/S_test | Một output/query trên S, paired với H0 | RQ2 on−off: retrieval và answer-level |
| H0R(τ*) vs H0R(−∞) | Cùng retrieval/rerank/generator; chỉ bật gate | Replay scores/output trên S; τ từ S_dev, khóa trước S_test | Tái dùng output H0R đã duyệt, không generation mới | RQ3: output risk, coverage, từ chối nhầm và nhận trả lời sai |

Như vậy có **5 cấu hình retrieval toàn tập + 1 cấu hình rerank trên subset + 1 phép replay gate**; số hàng bảng không đồng nghĩa số model/index/API runs. RQ1/RQ5 không có kết luận answer-level trong ma trận tối thiểu; RQ2/RQ3 chỉ khái quát trong subset đã duyệt.

| Điểm còn cần đối chiếu khi thực hiện | Mặc định/đích bàn giao | Ai cung cấp evidence |
|---|---|---|
| Nguồn corpus và số mẫu/split/group thực | Corpus EN; N/G/C chưa xác minh; công thức §4 | Nhóm 02, theo ranh giới nguồn owner chọn; không hỏi lại deadline/hardware/đề cương |
| Span gold và khả năng duyệt subset | Evidence sets AND/OR, S_dev≈20/S_test≈40 có hai hướng/A-U | Nhóm 02/06; nếu thiếu thì ghi giới hạn, không bỏ output review |
| Revision/tokenizer/pooling, truncation và score activation | Đúng source §3, caps §6; freeze trước test | Nhóm 04/05; không lấy revision mặc định unpinned làm tái lập |
| Tool gates có đủ trước số đo không | Candidate export, positive lexical, evidence metrics, dev/test guard và replay | Nhóm 04; current harness chưa đáp ứng hết |
| Generator/model version và quota free thực | Một model/prompt cho mọi answer conditions, khoảng hai calls hữu ích/query trong S | Nhóm chạy chọn lúc thực hiện; hết quota checkpoint, không đổi generator giữa điều kiện |
| CPU/batch/threads và budget thời gian/RAM thực | Pilot dev ngắn, model load tuần tự, P=25 mặc định | Nhóm 05; nếu cần P=15 phải khóa toàn so sánh trước test |
| Operating goals/effect size | §7–8 là quy tắc đề xuất đã cụ thể, không là mục tiêu sản phẩm được chứng minh | Khóa trong run manifest trước test; thay đổi phải version hóa, không tune theo test |

Các điểm đối chiếu trên là đầu vào thực thi và giới hạn bằng chứng, không mở lại các lựa chọn owner đã chốt. Tài liệu hoàn tất nhóm 03 ở mức phương pháp; chưa có run, nhãn output hoặc kết quả để kết luận H1/H2/H3/H5.

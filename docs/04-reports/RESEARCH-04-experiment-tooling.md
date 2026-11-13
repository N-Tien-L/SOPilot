---
id: RESEARCH-04-experiment-tooling
title: "Nhóm 04: Công cụ thí nghiệm, khoảng trống và đặc tả sửa tối thiểu"
status: final
type: research
scope: research
created: 2026-10-19
updated: 2026-10-19
author: "Owner"
refs:
  - docs/04-reports/RESEARCH-01-scope-and-rqs.md
  - docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
---

# Bàn giao công cụ nghiên cứu nhóm 04

## 1. Kết luận và giới hạn khảo sát

**Có thể tận dụng `eval/`, nhưng chưa đủ điều kiện chạy thí nghiệm chính thức.** Lỗi nDCG vượt 1 đã được tái hiện bằng hàm hiện có. Harness chưa lưu ranking/context, chưa có answer-level runner/checkpoint, chưa khóa đầy đủ embedding provenance. Runtime khác offline về lexical scorer, score gate, chunking và cách nối reranker; chưa thể suy kết quả eval thành chất lượng hệ thống.

Đường ngắn nhất là hoàn thiện harness offline độc lập, thêm một đường generation API có checkpoint cho subset đã định và duyệt output; kiểm chứng runtime là luồng riêng. Không cần đưa PostgreSQL, ingestion, gateway hay full stack vào điều kiện bắt đầu nghiên cứu retrieval.

Phạm vi kế thừa owner: corpus EN gốc; query EN/VI (EN→EN, VI→EN), không dịch corpus; dense/BM25/hybrid; hai embedding; một reranker bật/tắt; refusal và subset answer-level có người duyệt; RAM tổng 32 GB, CPU, generator qua API miễn phí khi chạy thực tế. Chưa xác minh quota, tốc độ hay model nào chạy phù hợp. Không chọn corpus, shortlist, số mẫu, k, pool hoặc threshold thay nhóm 02–03.

`final` chỉ hoàn tất khảo sát/đặc tả này, không chứng nhận công cụ đã sửa, nghiên cứu đã chạy hoặc PRD/ADR/PLAN được duyệt. Nhóm 02–03 đang làm song song; tài liệu dùng hợp đồng tham số hóa ở §5 và ghi điểm đối chiếu, không chờ hoặc sửa đầu ra của họ.

Đã kiểm tra Git trước mọi thao tác: nhánh `fix/auth-google-roster-admission`, nhiều thay đổi staged/unstaged/untracked, gồm cả `eval/` untracked. File đích chưa có nên không có nội dung cũ để hợp nhất. Session chỉ thêm file này, không đổi nhánh/commit, không đọc `.env`, không tải model, không gọi API, không chạy stack. Bằng chứng là snapshot working tree ngày 19/10/2026; commit HEAD riêng lẻ không đại diện mã đang khảo sát.

Đã đọc `AGENTS.md`, `docs/README.md`, handoff nhóm 01/tổng và ngữ cảnh `.agent/context/README.md`, `architecture/system-overview.md`, `database/schema.md`, `database/tables/{knowledge,conversation}.md`, `authorization/dual-strategy.md`, phần ownership/retrieval trong `service-boundaries/responsibilities.md`. Có drift trong context: mô tả rerank/schema và ví dụ `to_tsvector('english', ...)` không chứng minh runtime. DDL `infrastructure/init-db/003_knowledge.sql:126` dùng `simple`; trạng thái DB đang chạy chưa kiểm tra. Áp dụng skill `.agent/skills/analyze-quality/SKILL.md` để phân loại bằng chứng; giữ tên/path HANDOFF theo yêu cầu owner.

## 2. Trace mã thực tế

Các đường dẫn và dòng dưới đây tính từ gốc repo, theo snapshot đọc trong session. Đây là bằng chứng static; chỉ các phép kiểm tra ở §4.2 đã thực thi.

### 2.1. Offline eval

| Điểm gọi | Bằng chứng file:dòng | Hành vi đã nối / hệ quả |
|---|---|---|
| CLI → run | `eval/sopilot_eval/run.py:160–170`, `45–49` | Parse dataset/config/out; đọc mọi câu trong `questions.jsonl`, load corpus. Không chọn split dev/test, không validate schema hoặc lọc subset |
| Corpus → chunks | `eval/sopilot_eval/corpus.py:21–27,30–56` | PDF lấy text theo trang; MD/TXT dùng form feed, thường cả file là trang 1. Chỉ đọc file ngay trong thư mục, không recursive, không DOCX. Chunk theo ký tự/paragraph, không theo tokenizer; chỉ có doc/page/text, chưa có section/span/chunk ID bền vững |
| Config → index | `run.py:60–71`; `embedders.py:110–120`; `retrievers.py:41–52` | Mọi config, kể cả BM25, tạo matrix embedding và BM25. Corpus cache có; query embedding được tính lại. BM25 chưa chạy độc lập khỏi transformer; dùng hash provider chỉ có thể là cách tránh tải model tạm thời, không phải dense nghiên cứu |
| Query → dense/lexical | `retrievers.py:12–38,48–56,77–90` | Dense là dot product sau normalize ở các adapter hiện có; BM25 tự cài k1=1.5/b=0.75, NFC/lowercase, unigram+bigrams. Không phải BGE sparse. Tie theo thứ tự chunk ổn định |
| Fusion → rerank | `retrievers.py:59–74,77–95` | Pool mặc định 25, hybrid lấy 50 mỗi nhánh rồi union/fuse còn 25; RRF có weights và rrf_k. Rerank local CE pair query/chunk, max_length=512; trả toàn pool đã sắp hạng |
| Ranking → metrics | `run.py:72,79–107`; `metrics.py:6–42` | `k` chỉ thêm recall cutoff, **không** cắt ranking/context. `pool` trong YAML không được truyền ở call dòng 81. Metrics chỉ answerable; refusal proxy dùng top score của cả hai lớp |
| Output | `run.py:91–94,110–130,134–155` | Chỉ ghi ID/config/top_score/metrics từng câu; không ranking, candidate IDs, context, prompt/output/citation. Write cuối toàn lượt; exception giữa vòng lặp mất phần kết quả còn trong RAM. `reference_answer` không được sử dụng |

`run.json` có config, HEAD, số chunk/câu và Python/platform/processor (`run.py:115–123`), chưa có hash nội dung, dirty source identity, dependency/runtime versions, revision resolved, RAM, step timings. `corpus_embed_s` đo cả build embedder/index (load model, cache/BM25), không phải riêng thời gian inference; bị dùng lại giữa config cùng embedder (`run.py:61–66,106`).

Hai lưu ý CPU: index dict giữ các embedder/model/matrix tới hết run (`run.py:57–66`), nên thêm hai embedding không tự thành chạy tuần tự giải phóng RAM. `rerankers.setdefault(rk, CrossEncoder(...))` đánh giá constructor trước khi gọi setdefault (`run.py:70`), có thể load lại model khi key đã có. Đây là hành vi mã, chưa đo peak RAM hoặc latency.

### 2.2. Runtime Q&A và ingestion

Gốc đường chat: `services/ai-qa-service/src/main.py:67` include chat router; `src/api/routes/chat.py:21,42,91–112,156–179` khởi tạo singleton `PipelineOrchestrator()` rồi gọi `process` hoặc `process_stream`.

Trong bảng dưới, tiền tố **AI** = `services/ai-qa-service/src/`, **ING** = `services/ingestion-service/src/`.

| Chặng | Bằng chứng | Điều đã xác minh |
|---|---|---|
| Trước retrieval | AI `services/pipeline/pipeline_orchestrator.py:164–213,349–420` | Toxic filter → intent; SIMPLE đi responder riêng. COMPLEX gọi query refiner, dùng query đã refine để search; có history. Khác offline dùng query gốc, một lượt |
| Query embedding | AI `services/retrieval/hybrid_search.py:17–41,63` | HTTP `/v1/embeddings`, model từ settings, input query nguyên dạng; không instruction/revision trong payload. Server tokenizer/max length chưa xác minh |
| Dense DB | AI `db/repositories/chunk_repo.py:47–88` | Cosine distance pgvector + department boost, ACL/latest/published/expiry. Có JOIN sang metadata (drift với guardrail cấm cross-schema joins); không xem đây là thiết kế nên sao chép |
| Lexical DB | AI `db/repositories/chunk_repo.py:95–183` | Tên `bm25_search` nhưng SQL là `ts_rank`, weighted content/title/section, `plainto_tsquery('simple',...)`, boost department, normalize theo max của kết quả. Không có BM25 IDF/k1/b như eval |
| Fusion/filter | AI `services/retrieval/hybrid_search.py:65–107,119–136` | Lấy `limit*2` mỗi nhánh; RRF k=60, weights 0.7/0.3 hardcoded; sắp theo fused score nhưng trả đối tượng giữ similarity gốc. Cùng ID ưu tiên đối tượng vector, lexical-only giữ score normalized lexical. Filter similarity trước rerank |
| Injection reranker | AI `services/pipeline/pipeline_orchestrator.py:40–80,234–238,439–442`; AI `api/routes/chat.py:42` | Constructor nhận reranker optional, gán trực tiếp `self.reranker_service = reranker_service`, không fallback singleton. Chat không inject nên `None`: `use_reranker=True` riêng lẻ không bật được đường này |
| Reranker thực thể | AI `services/retrieval/reranker.py:11–61` | Singleton có `/rerank` HTTP, truncate true; overwrite `similarity_score` bằng score CE. Timeout/non-200/exception trả ranking cũ. Chưa có record phân biệt rerank thành công với fallback trong artifact |
| Gap/refusal | AI `services/knowledge_gap.py:32–62`; AI `services/pipeline/pipeline_orchestrator.py:240–265,310–320,444–488,531–540` | Gap so cùng threshold trên `similarity_score`; đánh dấu/publish unanswered. Không có nhánh dừng generation khi gap=true: prompt vẫn được gửi. Không đồng nhất flag gap với từ chối thực sự |
| Prompt → SDK | AI `services/generation/prompt_builder.py:4–14,21–55`; AI `services/generation/llm_client.py:19–48,50–104,139–182` | Prompt yêu cầu grounded, trả theo ngôn ngữ query, dẫn title; dùng tối đa 10 chunk, mỗi chunk cắt 2500 ký tự. LLMClient resolve profile rồi gọi `AsyncOpenAI.chat.completions.create` trực tiếp; không qua `ModelRegistry.generate` |
| Profile/fallback | AI `services/generation/model_registry.py:21–80,100–105`; AI `services/generation/llm_client.py:19–46,105–137,187–219` | Registry cung cấp profile/model_name/base_url; client có preemptive fallback và fallback khi local lỗi. Tên profile/model trong code không chứng minh provider đang khả dụng hoặc free |
| Ingestion → vector | ING `services/pipeline.py:194–214,235–253,309–312`; ING `services/embedding_service.py:46–93,124–160` | ParentChildChunker → embed_batch_cached → persist. Cắt bằng cl100k_base 512 tokens, lỗi thì 2000 ký tự; payload model=settings nhưng cache/persist ghi cố định BGE_M3/1024. Cache tra bằng text hash + nhãn model cố định; không đủ phân biệt model thực/revision/preprocess |

Settings là default trên đĩa, không phải cấu hình triển khai: AI `config/settings.py:30–31,65–68` có embedding `jina-embeddings-v3`, retrieval_limit=25, rerank_limit=10, similarity_threshold=0.15, use_reranker=true. Không đọc `.env` để suy override.

**Lỗi static bổ sung cần chặn kiểm chứng hệ thống:** AI `services/pipeline/pipeline_orchestrator.py:275–276,449–450` import `build_sources` từ `src.api.routes.chat`, nhưng toàn bộ `chat.py:1–180` không định nghĩa/import symbol này. Khi đi nhánh có chunks tới đây sẽ lỗi import trên snapshot này; chưa chạy HTTP để xác nhận toàn endpoint. Nonstream gọi generation trước điểm lỗi, stream dựng nguồn trước generation. Không sửa trong session này.

## 3. Những nghi vấn handoff đã được giải quyết

| Nghi vấn | Kết luận có bằng chứng | Giới hạn / sửa tối thiểu đề nghị |
|---|---|---|
| ts_rank vs BM25 | Xác nhận khác thuật toán, tokenizer/features, score scale và filter; §2 | Dùng offline BM25 cho nghiên cứu, đặt tên rõ. Runtime parity là gate riêng trước tuyên bố hệ thống dùng cấu hình thắng; không bắt buộc cài BM25 DB trước nghiên cứu |
| Cap 512 | Eval ST ép `min(max_seq_length or 512,512)` (`embedders.py:44–56`); CE ép 512 (`retrievers.py:71`); ING cắt 512 cl100k (`embedding_service.py:54–68`) | Ba cap không cùng tokenizer. Không suy model chỉ hỗ trợ 512 hoặc bị mất bằng chứng bao nhiêu. Tham số hóa max_length, lưu tokenizer/truncation counts; nhóm 03 chọn policy, nhóm 05 đo tail truncation |
| Instruction | Eval ST chỉ có query_prefix; API adapter bỏ qua is_query (`embedders.py:53–78,115–117`); runtime payload không instruction | Cần role query/document và rendered input/template theo model; không tự áp một prefix cho mọi shortlist. build_embedder chưa forward batch_size dù constructor có tham số |
| Revision | Eval nhận revision nhưng config nghiên cứu không có (`configs/rq1-rq3-bge-m3.yaml:5–13`); name ghi unpinned khi thiếu | Resolve/pin immutable revision trước chạy chính thức; tokenizer và reranker cũng cần revision. `run.json` không tự khám phá revision dù comment YAML gợi ý xem run.json |
| Cache | Eval namespace ST gồm model@revision, file text hash; không gồm effective max_length/tokenizer/code/precision/normalization; API namespace chỉ model (`embedders.py:51,66,81–107`) | Query hiện không cache; query_prefix chưa làm stale corpus ở hiện trạng vì chỉ áp query. Tuy nhiên provenance query thiếu và thay document preprocessing/cap có thể reuse sai. Cache mới phải theo fingerprint input+adapter đầy đủ |
| Reranker injection | Xác nhận chat default không inject; eval có CE thật khi conf rerank và adapter được tạo | Offline không phụ thuộc runtime injection. Trước tích hợp, inject singleton có chủ đích, test cả on/off/error; không gọi fallback là rerank-on thành công |
| Score separation | Eval hybrid xếp theo RRF nhưng tuple chứa dense score tại chunk được chọn đầu; rerank overwrite tuple bằng CE (`retrievers.py:88–94`). Runtime score trộn dense/lexical rồi overwrite CE | Lưu riêng raw scores/ranks, fused score, CE score, gate feature/value/stage. Không coi dense score tại fused top là max dense; không dùng ngưỡng chung qua scorer/model |

## 4. Kiểm định metrics và độ sâu ranking

### 4.1. Đọc mã

`metrics.py:6–11` chỉ so doc/pages, trả **target đầu tiên** trúng; mọi chunk cùng trang/tài liệu đều được tính hit, dù không chứa span đáp án. Với MD trang 1, document-level label đặc biệt thô. `14–26` tính recall trên tập target được phủ, MRR trên toàn ranking được truyền, DCG lại cộng **mọi chunk trúng**; IDCG dựa số target. Hai đơn vị relevance không nhất quán.

Pool 25 hiện đủ cấp tối đa 10 vị trí cho nDCG@10 nếu corpus có đủ ứng viên; **không có bằng chứng nDCG luôn thiếu depth 10 mặc định**. Tuy nhiên MRR mang tên không cutoff thực tế là MRR@25 (hoặc ít hơn nếu corpus nhỏ); kết quả không phản ánh first hit ngoài pool. `k>25` vẫn có thể xuất recall@k từ list 25; không cảnh báo. Đây là sai nhãn/validation depth, tách khỏi lỗi DCG. Rerank chỉ đổi thứ tự trong pool, không phục hồi evidence ngoài pool.

`run.py:47,79–107` không split/tune/freeze; sweep trên dataset được truyền, có thể là test. Hàm sweep là mô tả proxy, bản thân chưa chọn threshold; nếu chọn operating point từ đó trên test sẽ leak. Không có answer-level correctness trong `false_answer`.

### 4.2. Bằng chứng thực thi nhỏ, không model/API

Đã dùng Python 3.12 có sẵn, `python -B -` từ repo root, `importlib.util.spec_from_file_location` nạp **chỉ** `eval/sopilot_eval/metrics.py`; dùng `SimpleNamespace(doc=...,page=1)`. Không import service/settings, không ghi fixture/test/cache. Các kết quả dưới là kiểm chứng công cụ, không phải số đo nghiên cứu.

| Input / thao tác có thể tái lập | Kết quả thực | Phân loại |
|---|---|---|
| `retrieval_metrics([a,a],[{'doc':'a'}])`, a là chunk doc=a/page=1 | recall@10=1; **ndcg@10=1.6309297535714575** | Lỗi chứng minh: DCG/IDCG không cùng đơn vị, vượt [0,1] |
| Một a; expected gồm doc=a và doc=a/pages=[1] | recall=0.5; nDCG=0.6131471927654584 | Xác nhận first-match che target khác. Có là lỗi nhãn hay scorer phụ thuộc hợp đồng overlap nhóm 02–03, chưa tự quyết |
| 25 chunk x không trúng; so cùng list thêm a ở hạng 26 | MRR từ 0 thành 1/26=0.038461538461538464 khi đủ ranking | Chứng minh MRR phụ thuộc depth đầu vào; code retrieval hiện chỉ trả pool25 |
| `retrieval_metrics([],[])` | `ZeroDivisionError` | Lỗi robustness chứng minh. run hiện chỉ gọi metrics cho answerable; cần reject answerable thiếu gold từ preflight, không phải unanswerable nào cũng crash |
| `refusal_sweep([0.5],[0.5],steps=2)` | Ba dòng cùng threshold=.5, false_refusal=0, false_answer=1 | Sweep không có điểm refuse-all, không phân giải tie; cần sentinel hai đầu và score boundary |
| `refusal_sweep([0.5],[],steps=2)` | false_answer=0 dù không có câu unanswerable | Mẫu số rỗng bị trình bày như 0 lỗi; cần null/N/A + counts |

Lệnh tái hiện lỗi chính, không cần dependencies ngoài Python (từ root):

```powershell
@'
import importlib.util
from types import SimpleNamespace
s = importlib.util.spec_from_file_location('metrics', 'eval/sopilot_eval/metrics.py')
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
a = SimpleNamespace(doc='a', page=1)
assert m.retrieval_metrics([a, a], [{'doc': 'a'}])['ndcg@10'] > 1
'@ | python -B -
```

Đây là assertion xác nhận **lỗi hiện tại**, không phải acceptance test sau sửa. Sau sửa cần kỳ vọng nDCG đúng định nghĩa đã khóa.

### 4.3. Đặc tả sửa metric tối thiểu

1. Nhóm 02–03 khóa đơn vị: evidence target có ID bền vững, span/section và các chunk chấp nhận được; phân biệt nhiều target đều cần với nhiều vị trí thay thế cho cùng một target. Scorer ánh xạ ranking thành tập target; không dùng doc/page tùy tiện làm gold cuối.
2. Nếu chọn **target coverage có gain nhị phân**, chỉ cấp gain lần đầu target xuất hiện; lặp chunk trúng cùng target không tăng gain. Với mapping một target/chunk, DCG và ideal cùng target duy nhất; `IDCG@k=sum(1/log2(r+1), r=1..min(k,n_targets))`. Tên phải ghi `target_nDCG@k`, tránh gọi là chunk nDCG chuẩn khi chưa có qrels chunk. Không chữa bằng clamp nDCG về 1.
3. Nếu một chunk hợp lệ phủ nhiều target, công thức gain/ideal bên trên không được áp nguyên xi (gain có thể >1). Cần nhóm 02–03 chốt disjoint mapping hoặc metric coverage có ideal phù hợp; fixture overlap phải reject/được chấm theo policy rõ ràng. Nếu chọn chunk-level nDCG, xây qrels chunk và IDCG từ chính qrels, không từ số evidence target. Không tự thay lựa chọn khoa học bằng tiện cài đặt.
4. Recall tính unique target coverage; bổ sung all-targets-found theo hợp đồng nhiều evidence. MRR ghi rõ `MRR@D`, phân biệt candidate recall@pool và metric context@k. Preflight yêu cầu depth >= max cutoff cần báo; corpus nhỏ thì ghi effective depth, không bịa thêm kết quả. Ties có quy tắc deterministic và được ghi lại.
5. Threshold sweep dùng dev, score type/stage cố định, có always-answer/refuse-all, ties, empty candidate => explicit refuse và missing score; không sentinel 0 thay missing (CE có thể có score âm). Freeze threshold trước test, lưu numerator/denominator/coverage; chia EN/VI và answerability, không chỉ aggregate.

Test cần có: duplicate chunk/target; distinct targets; irrelevant ở đầu; hit ngoài cutoff; ideal/all irrelevant/empty ranking; invalid empty expected; overlap/alternatives; ranking <k; tie và missing score; metric domain [0,1]; đổi thứ tự target không làm đổi điểm khi policy cho phép. `eval/tests/test_eval.py:11–35` hiện chỉ có first hit/page constraint/RRF/proxy extremes/smoke files; chưa bảo vệ các trường hợp này. Chưa chạy toàn suite trong session khảo sát.

## 5. Hợp đồng tham số hóa với nhóm 02–03

Đây là schema đề nghị để triển khai, không phải dataset/shortlist đã duyệt. Chỗ chưa có giá trị phải fail preflight cho run chính thức, không âm thầm lấy default nghiên cứu.

| Phần | Trường tối thiểu | Cần đối chiếu sau |
|---|---|---|
| Corpus/chunks | corpus_version; doc_id/source_url/license/source_revision/raw_hash/extracted_hash/lang=en; chunk_id/doc_version/section/page/span/text_hash; extraction/chunking implementation+params | Nhóm 02: nguồn, quyền chia sẻ, span và chunk-evidence map. Giữ một chunk manifest chung cho hai embedding |
| Query/gold | query_id/group_id/split/question/lang/en→en hoặc vi→en/answerable; target IDs và alternative/required groups; reference_answer; gold_version/reviewer/status; answer_subset flag | Nhóm 02: split theo group/near duplicates, nhãn người duyệt, subset và negatives. Không chia cặp cùng nghĩa qua dev/test |
| Retrieval | retriever enum; embedding profile E_A/E_B; lexical tokenizer/version/k1/b; dense_pool/lexical_pool/fused_pool; weights/rrf_k; metric_depth/context_k; tie_policy | Nhóm 03: hai model cụ thể, pool/k và điều kiện so sánh. BM25 độc lập chạy một lần nếu cùng corpus/config; không nhân bản thành hai quan sát chỉ vì embedding khác |
| Model adapter | provider/model/resolved_revision/tokenizer_revision; role-specific instruction/template; effective max lengths/truncation side; pooling/normalize/dim/dtype/device=cpu/batch/threads | Nhóm 03: policy riêng từng model; không mặc định mọi model hỗ trợ cùng instruction. Client/server adapter phải có cùng effective contract nếu dùng API embedding |
| Rerank/gate | reranker profile R + revision; pair template/max length/batch; enabled; input candidate IDs; gate feature/stage/aggregation/threshold/dev_hash/freeze time | Nhóm 03: cùng pool khi on/off; gate so sánh có kiểm soát. Không để bật rerank đồng thời đổi từ cosine sang CE mà không khai báo thành điều kiện riêng |
| Answer | subset hash; generator G/model requested/actual/provider version; prompt version; context_k/token budget/output cap; temperature/top_p/seed nếu hỗ trợ; history=[]; fallback policy; review rubric version | Nhóm 02–03: subset/rubric và điều kiện sinh. Một generator cố định; khả dụng API/quota kiểm tra khi thực hiện, không chọn provider ở đây |

Result per candidate phải có `{query_id, chunk_id, dense_rank, dense_score, lexical_rank, lexical_score, fused_rank, fused_score, rerank_rank, rerank_score, selected_for_context}`; null khi không có nhánh, không overwrite trường. Gate record riêng `{feature, stage, value, threshold, accepted, reason}`. Hybrid top chunk có thể chỉ nằm lexical pool; nếu gate yêu cầu dense score của nó, phải xác định/calculate feature đó trước, không lấy score lexical thay thế.

## 6. Answer-level: phần phải bổ sung

Harness hiện tại là retrieval-only dù có reference_answer. Runtime có output/model/sources trong conversation nhưng không thay được artifact QA: prompt chưa được snapshot, context bị cắt, nguồn chủ yếu title; flag has_sources chỉ dựa có chunks (`pipeline_orchestrator.py:271–276`), không chứng minh output đã trích đúng.

Đường ngắn nhất đề nghị: thêm `eval/sopilot_eval/answer_run.py`, adapter `generation.py` và `review.py`/schema tương đương, đọc ranking artifacts đã khóa; chạy một lượt độc lập, không DB/history/refiner/intent/title generation. Nếu tái dùng prompt formatter, chuyển thành hàm thuần hoặc adapter; không import service singleton kéo settings/API dependencies. Đây là đường nghiên cứu QA được công bố riêng, chưa được gọi parity với `/chat`.

Mỗi đơn vị `query × config × replicate` cần lưu:

- Context thực gửi: ordered chunk IDs, text snapshot, source version/span, phần bị cắt, token counts/budget và citation alias ổn định như `[S1]` ánh xạ chunk. Giữ cả pre-context candidates để phân biệt retrieval miss và context loss.
- Messages system/user nguyên văn, prompt/template hash, query gốc và effective query, model requested/actual/version, tham số sinh thực gửi, response ID, usage/finish_reason và output thô + output đã parse. Không chỉ lưu title hoặc output đã loại tags.
- Gate accepted/refused tách `observed_llm_refusal`; câu bị gate từ chối có status quyết định và thông điệp, không tạo giả output LLM. Luôn trả lời là baseline rõ ràng. Nếu tái dùng output always-answer để mô phỏng các threshold, phải giữ nguyên context/prompt/generator và gate chỉ chặn trước sinh; khai báo đó là replay quyết định, latency generation thực và latency policy mô phỏng tách riêng.
- Citation mention/claim spans → alias → chunk/span, invalid/unresolved citations; nhãn reviewer về correctness/completeness theo reference, faithfulness theo context thực, citation precision và completeness theo claim, refusal đúng/sai. Không suy citation correctness từ alias tồn tại. Rubric hỗ trợ N/A với denominator=0, không thưởng câu từ chối bằng điểm correctness/citation mặc định.
- Review record: output_hash, rubric_version, reviewer_id, reviewed_at, per-claim labels, overall labels/reason, disagreement/adjudication/status. Người duyệt được ẩn tên config khi khả thi. Một người duyệt phải ghi đúng giới hạn; LLM judge tùy chọn không thay gold người duyệt.

RQ2 chỉ có kết luận answer khi paired on/off trên cùng subset/generator/prompt/budget được duyệt. RQ3 phải có false refusal, false acceptance, coverage và lỗi output thực trong các câu được trả lời, cả answerable trả lời sai; không đổi tên `false_answer` retrieval proxy thành hallucination rate. Báo riêng query EN/VI, số mẫu thiếu/lỗi và không coi timeout/API quota là refusal.

## 7. Run artifacts và tiếp tục sau hết quota

Đề nghị một run directory bất biến, ID có UUID/hash thay timestamp giây đơn lẻ (`run.py:51–53` có thể dùng chung folder trong cùng giây). Manifest được tạo **trước** inference; mọi output có schema version, run/config/query keys và checksum.

| Artifact đề nghị | Nội dung / khóa tái lập |
|---|---|
| `manifest.json`, `resolved_config.json` | SHA-256 corpus raw + extracted manifest, ordered chunks manifest, query/gold/subset/split; config canonical JSON hash; metric/rubric/prompt versions; HEAD + dirty flag + hashes đúng các source/lock file dùng trong run. Repo hiện dirty/untracked nên HEAD không đủ; lưu snapshot mã được chọn trong repo, loại `.env`/secrets và file session khác |
| `environment.json` | Python/OS/package versions, `uv.lock` hash, model/tokenizer resolved revision hoặc server deployment/version/fingerprint; CPU model/physical/logical cores, RAM tổng/khả dụng/peak RSS, device, thread counts, batch, dtype/backend/quantization, cache cold/warm, seed và thời điểm/timezone. Không lấy RAM 32 GB tổng làm peak/available |
| `corpus_manifest.jsonl`, `chunks.jsonl`, `queries.jsonl` hoặc bản tham chiếu có hash | URL/giấy phép/source snapshot, IDs/span/text/hash, query groups/splits/gold version. Đủ tái dựng mapping; hash không thay thế bản dữ liệu được phép lưu/chia sẻ |
| `embeddings/`, cache manifest | Key SHA-256 của effective model+immutable revision+tokenizer+adapter/code+role+rendered input hash+max_length/truncation+pooling+normalize+dtype/dim/backend; batching/threads cũng ghi trong provenance. Query cache riêng role=query; document cache role=document. Validate shape/finite/dimension/checksum trước reuse; write tạm rồi atomic rename |
| `rankings.jsonl`, `timings.jsonl` | Scores/ranks mọi chặng, pool/depth/context selection và gate. Tách load model, extract/chunk, corpus embedding/index build, query embedding, dense, lexical, fusion, rerank, context/prompt, API wait/TTFT/completion, parse/persist và total; unit ms, monotonic clock, cache hit/miss, warm/cold và số mẫu. Retry/backoff tính riêng lẫn wall total; không trộn cache hit vào inference throughput |
| `answers.jsonl`, `reviews.jsonl` | Bản ghi §6, join theo query/config/replicate/output hash. Response model/version thiếu thì ghi unavailable, không bịa revision. API chỉ có alias mutable thì khóa cửa sổ chạy, lưu raw response metadata và công bố giới hạn tái lập; giữ output để chấm lại không gọi API |
| `tasks.jsonl`/checkpoint và `attempts.jsonl` | Stage/task key, trạng thái pending/running/succeeded/retryable_failed/permanent_failed/unknown, attempt ID, request hash/response ID, HTTP status/error code đã redacted, timeout, retry-after, backoff, timestamp/duration, checksum output. Không lưu auth headers, token/API key hoặc config có key |
| `metrics.json`, `report.md` | Tạo lại từ rankings/answers/reviews, không gọi model; counts/denominators/missing và cohort EN/VI/answerability; paired query/group IDs cho phân tích nhóm 05. Phân biệt proxy, human reviewed và system validation |

Checkpoint không chỉ ở cuối run. Khóa task generation = hash(run inputs + query + candidate/context order/text + prompt + model/version + generation params + replicate); chỉ skip khi succeeded và output checksum khớp. Flush từng query/stage thành công bằng atomic per-task file hoặc journal có record hoàn tất; sau crash bỏ dòng JSONL cuối chưa đủ, không đánh dấu output cắt cụt là thành công. Persist ranking trước API để quota hết không cần embed/rerank lại.

Retry policy: limit số lần/thời gian, exponential backoff có jitter, tuân `Retry-After` khi có; 429/quota thì checkpoint và pause scheduling, 5xx/network/timeout có giới hạn, auth/schema error fail rõ. Timeout sau khi server nhận request là trạng thái không chắc đã hoàn thành; ghi unknown/attempt riêng, không giả bảo đảm exactly-once. Dùng idempotency/request ID nếu provider hỗ trợ; nếu không, tránh retry vô hạn và giữ cả attempts để audit.

Không tự fallback sang model khác khi hết quota. Đổi generator/version tạo condition/run mới và chạy lại đủ các paired cells bị ảnh hưởng, không trộn với lượt cũ; chỉ rerun generation cần đổi, reuse retrieval qua checksum. Model stochastic/API mutable không bảo đảm output bit-for-bit; artifacts cho phép tái phân tích chính xác output đã lưu và rerun có provenance. Kiểm thử crash/resume/checkpoint dùng fake API, không tiêu quota thật.

## 8. Thứ tự sửa tối thiểu và acceptance criteria

Đây là thứ tự kỹ thuật đề nghị, **không phải PLAN/ticket**, không cập nhật nguồn tiến độ. A chặn thực nghiệm tương ứng; B chặn tuyên bố hệ thống; C có thể hoãn.

| Thứ tự | File/phạm vi dự kiến | Phụ thuộc | Kiểm thử và acceptance criterion |
|---|---|---|---|
| A1 — metric/gold/depth | `eval/sopilot_eval/{metrics,corpus,run}.py`, `eval/tests/test_eval.py`; thêm schema/preflight nhỏ | Hợp đồng relevance/split từ 02–03; có thể dùng fixture synthetic ngay | Phản ví dụ §4 được kiểm thử; nDCG có định nghĩa/miền đúng, target duplicate/overlap xử lý rõ; reject input sai/không đủ depth; tên MRR@D đúng; không còn empty denominator giả 0 |
| A2 — adapter/config/cache | `eval/sopilot_eval/{embedders,retrievers}.py`, `eval/configs/`, `eval/pyproject.toml`/lock nếu cần | A1 schema; profile E_A/E_B/R được 03 điền trước run chính thức | Mock encoder/API: query/doc instruction đúng, max_length/batch/device forward thật; đổi revision/cap/preprocess invalidates cache; dimension/finite checks. BM25 không gọi embedder; không giữ cả hai model trong RAM; reranker mỗi key chỉ tạo một lần |
| A3 — scores/pool/run records | `eval/sopilot_eval/{retrievers,run}.py`; thêm `artifacts.py`/equivalent; tests | A1–A2 | Config pool thực có hiệu lực; candidate IDs on/off giống nhau; scores không overwrite; context_k tách metric depth; manifest/checkpoint ghi đầu run; exception vẫn giữ completed queries; metrics recompute không gọi model |
| A4 — dev gate | `eval/sopilot_eval/{metrics,run}.py`, config/schema gate | A3 + dev split/feature được khóa | Synthetic ties/negative/empty score/classes; có always-answer/refuse-all; threshold từ dev artifact hash; test runner chỉ nhận threshold frozen, không tune trên test; coverage/counts/N/A theo lớp/ngôn ngữ |
| A5 — QA subset + API checkpoint | Thêm `eval/sopilot_eval/{answer_run,generation,review}.py` và tests/schema/prompt | A3; subset/gold/rubric của 02–03; A4 để eval refusal; generator được xác minh khi chạy | Fake API test input context/prompt/citation map/output/review join; crash sau N câu rồi resume không gọi lại succeeded; 429/5xx/timeout/invalid citations/partial output; không silent fallback; sửa prompt/model tạo task key mới |
| A6 — pilot rồi freeze | `eval/README.md`, resolved configs/run artifacts trong đợt triển khai sau | A1–A5 + dataset/model hợp lệ | Smoke synthetic không download; pilot CPU model thật chỉ ở session chạy được phép, đo RSS/latency/truncation/cache; khóa data/config/threshold/subset trước test. Chạy E_A rồi giải phóng, E_B tiếp, reranker một model; không hứa 32 GB đủ khi chưa pilot |
| B1 — runtime nối đúng | AI `api/routes/chat.py`, `services/pipeline/pipeline_orchestrator.py`, `services/retrieval/reranker.py`, `services/generation/{prompt_builder,llm_client}.py`, tests | Có harness chuẩn; chưa cần trước A1–A6 | Inject reranker, sửa symbol build_sources; mock process/stream đi đủ retrieval→rerank→prompt→generation→sources/persist; assert bật/tắt/lỗi rõ; max_tokens thực khớp config (stream client hiện hardcode 2048 tại dòng 171 dù nhận arg); model thực/fallback minh bạch |
| B2 — parity + isolation | AI retrieval/chunk repo/models; ING embedding/cache/chunker; context tương ứng nếu sửa contract | Cấu hình nghiên cứu đã chọn, schema/ownership review theo AGENTS | Cùng corpus/chunks/model revision/instruction/scorer/gate; so candidate IDs và scores có tolerance được định trước. Kiểm tra tenant/ACL/latest/deleted/expiry và scope filters. Runtime chưa truyền workspace vào search ở §2, SQL JOIN metadata còn vi phạm guardrail; không tuyên bố isolation đạt chỉ từ đọc code. Migration nếu cần phải additive theo quy tắc repo, không tự tạo trong khảo sát |
| C — hoãn | Serving CPU riêng, BM25 DB extension, RQ4 overhead/RLS benchmark, deploy, UI, OCR/DOCX mở rộng, model thứ ba, judge tự động | Chỉ khi mục tiêu/nguồn lực cần | Không chặn nghiên cứu offline trên MD/TXT/PDF text đã xác thực; không bỏ isolation khi công bố hệ thống đa workspace |

Test gate cho triển khai sau: `eval` có suite riêng (`eval/pyproject.toml:12–14`); `scripts/run-tests.ps1:3`/`validate-build.ps1:14–15` chưa có scope eval. Dùng interpreter env đã cài và pytest từ thư mục eval, ví dụ `.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q`; chỉ sau khi kiểm tra dependencies, không dùng auto-sync có thể download trong session khảo sát. Nếu sửa runtime sau này chạy targeted unit tests và `validate-build.ps1 -Scope ai-qa`/`ingestion` theo phần chạm, cùng pre-commit gate. Không coi pre-commit tự bao phủ eval; session docs này không chạy full gates của các thay đổi người khác.

## 9. Bảng khoảng trống cuối và checklist bàn giao

| Khoảng trống | Bằng chứng chính | Mức ưu tiên / điều kiện đóng |
|---|---|---|
| nDCG >1; gold page/doc quá thô; overlap first-match | `metrics.py:6–26`, phản ví dụ §4.2 | **A1 chặn metric nghiên cứu**; relevance contract và regression tests pass |
| Pool/k/depth và gate chưa tách | `retrievers.py:77–95`; `run.py:72,81–107` | **A3–A4 chặn ablation/refusal đúng**; explicit pool/depth/score feature, dev freeze |
| Embedding cap/instruction/revision/cache chưa đủ | `embedders.py:44–56,63–78,84–117`; config `rq1-rq3-bge-m3.yaml:5–13` | **A2 chặn so hai embedding tái lập**; effective adapter/provenance + cache invalidation |
| Runtime lexical khác eval, mixed scores và prefilter | AI `chunk_repo.py:135–180`; `hybrid_search.py:95–107,119–136` | **B2 chặn parity**, không chặn offline BM25 nếu ghi rõ thuật toán và giới hạn |
| Reranker default chưa nối; build_sources thiếu | AI `chat.py:42`; orchestrator `80,235,275,439,449` | **B1 chặn system validation**; mock + smoke tích hợp khi được phép |
| QA/citation/refusal output chưa có trong eval | `run.py:91–130`; prompt runtime `4–14,45–53`; gap `32–62` | **A5 chặn RQ2–3 answer-level**; artifacts và human review, không dùng retrieval proxy thay QA |
| Metadata/checkpoint/step timings thiếu | `run.py:51–58,79–82,110–129`; `embedders.py:93–94` | **A3/A5 chặn run dài/API chịu quota**; resume/recompute kiểm thử bằng fake adapters |
| RAM/throughput/model/API thật chưa đo | `run.py:57–70`; machine fields `121–123` chỉ metadata thô | **A6 gate chạy chính thức**; pilot CPU/RSS/latency/quota ở lượt sau; không có kết luận model thắng |
| ACL/workspace/schema parity chưa kiểm chứng | AI `chunk_repo.py:51–67,142–156`; orchestrator `225–231` | **B2 trước tuyên bố hệ thống**; isolation tests, sửa đúng boundaries; RQ4 overhead vẫn hoãn |

**Thứ tự triển khai ngắn nhất:** khóa hợp đồng với 02–03 → sửa metrics/preflight → adapter/cache và BM25 độc lập → ranking/scores/manifest/checkpoint → dev gate → generation subset + review → pilot CPU/API rồi freeze → test chính thức. Làm runtime injection/sources/parity/isolation sau hoặc độc lập; cần hoàn tất trước tuyên bố tích hợp hệ thống, không kéo full stack vào harness offline.

Checklist sẵn sàng chạy thí nghiệm (trạng thái tại bàn giao):

- [x] Đã trace eval và runtime trên đĩa; xác minh các nghi vấn, ghi file/dòng; tái hiện lỗi metrics bằng Python thuần.
- [x] Tách lỗi chứng minh, hành vi static, hợp đồng còn mở và phép đo chưa làm; chỉ ghi file nhóm 04.
- [ ] Nhóm 02 bàn giao corpus EN snapshot hợp lệ, query EN/VI có nhóm/split/gold/reviewer và subset hash.
- [ ] Nhóm 03 điền E_A/E_B/R, instruction/tokenizer/caps, pool/k/metric/gate/rubric và quy tắc freeze; không còn default ngầm.
- [ ] A1–A4 sửa và tests synthetic pass; metric domain/depth đúng, BM25 độc lập, cache identity đủ và raw rankings lưu được.
- [ ] A5 có QA runner, citation map, nhãn người duyệt; fake API crash/quota/resume pass, secret redaction kiểm tra được.
- [ ] A6 pilot CPU RAM/latency/truncation, generator/quota xác minh khi chạy; môi trường/inputs/code/config có hash và revisions.
- [ ] Test split/config/threshold/subset được đóng băng; nhóm 05 tái tính metrics/review từ artifacts mà không gọi model/API.
- [ ] B1–B2 pass trước kết luận hệ thống; nếu chưa, báo cáo chỉ rõ kết quả offline/QA harness và giới hạn tích hợp.

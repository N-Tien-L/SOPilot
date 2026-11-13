---
id: AUDIT-EVAL-RQ1-RQ3-2026-11-04
title: "V2-07: RQ1/RQ1b/RQ2/RQ3/RQ5 truy xuất đa ngôn ngữ trên sop-main"
type: audit
status: final
created: 2026-11-04
updated: 2026-11-07
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [eval, ai-service]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-07-run-rq1-rq3-rq5.md
  - docs/architecture/components/ai-service.md
  - docs/04-reports/RESEARCH-04-experiment-tooling.md
  - eval/datasets/sop-main/README.md
---

# V2-07: Số liệu truy xuất RQ1–RQ3 và RQ5

> **Mã báo cáo:** `AUDIT-EVAL-RQ1-RQ3-2026-11-04` | **Ngày chạy:** 2026-11-04 | **Kết luận:** `PASSED_WITH_WARNINGS`. Đủ số liệu truy xuất; nhóm cross-lingual của tập test chỉ có 5 câu và ngưỡng RQ3 chọn trên 4 câu âm của dev, nên hai kết luận này chưa đủ chắc để đổi cấu hình. **Không có ngưỡng hay hệ số nào được ghi vào cấu hình ai-service**; mục 8 và 12 là đề xuất; owner chốt ngày 2026-11-07 như ghi ở [V2-07 §6](../execution/initiatives/v2-sopilot-mvp/tickets/V2-07-run-rq1-rq3-rq5.md), vẫn không đổi cấu hình ai-service.

## 1. Tóm tắt

- **RQ1 (test, 70 câu trả lời được, bge-m3):** hybrid RRF 1/1 đạt `span_recall@5` 0,938 so với dense 0,902 (chênh +0,036, CI 95% [−0,01; +0,09]); `full@5` (đủ mọi span bắt buộc trong 5 chunk đầu) 0,914 so với 0,857 (+0,057, CI [0,00; +0,13]). Ở nhóm cùng ngôn ngữ (65 câu) hybrid hơn dense rõ: +0,054 [+0,02; +0,11]. BM25 riêng 0,840; trọng số cũ 0,7/0,3 (0,895) không hơn dense.
- **Mục tiêu NFR recall@5 ≥ 0,80:** dense và hybrid đều vượt trên toàn tập test theo `span_recall@5`. Nhóm yếu nhất là câu tiếng Việt hỏi tài liệu tiếng Việt (dense 0,828, hybrid 0,906) và loại `multi_passage` (`full@5` 0,625 / 0,750).
- **RQ1b (cross-lingual):** hybrid **thua** dense ở nhóm cross-lingual cả dev (0,50 so với 1,00; 10 câu) lẫn test (0,80 so với 1,00; 5 câu). Hệ số `cross_lingual_bm25_factor` theo luật của ticket chọn được **0,3** trên dev (0,60, hơn 1 câu), nhưng trên test cho đúng kết quả như 1,0. Phân tích lỗi (mục 4.2) cho thấy hệ số này không chạm vào nguyên nhân: BM25 đẩy lên chunk **sai cùng ngôn ngữ với câu hỏi**, còn hệ số chỉ giảm chunk khác ngôn ngữ (tức chính chunk đúng).
- **RQ2 (rerank bge-reranker-v2-m3 trên pool 25 của hybrid):** `span_recall@5` 0,957 so với 0,938 (+0,019 [−0,02; +0,06], không rõ), nhưng `mrr_span` 0,943 so với 0,816 (+0,127 [+0,06; +0,19]) và nhóm cross-lingual 5/5 (dev 0,90 so với 0,50). Cái giá: p50 **17,7 s mỗi câu** trên CPU này (so với 0,15 s), peak RAM 5,1 GB khi giữ cả hai model. Điểm rerank tách câu âm tốt hơn hẳn cosine (mục 6).
- **RQ3:** cổng cosine tách kém câu trả lời được và câu âm (trung bình `dense_score` đầu 0,697 so với 0,597 trên test). Ngưỡng chọn trên dev bằng luật định trước (min FR+FA) là 0,619 cho dense, đo trên test: false refusal 0,086, false answer 0,455 (5/11 câu âm lọt). Cổng `rerank_score` tách tốt (0,959 so với 0,288; trên test có ngưỡng đạt FR 0,029 / FA 0), nhưng ngưỡng chọn trên dev (0,269) vẫn cho FA 0,455 vì 4 câu âm của dev dễ hơn hẳn câu âm của test. Dev quá ít câu âm để chọn ngưỡng.
- **RQ5:** bge-m3 tốt nhất cả về chất lượng lẫn tốc độ trên máy này. Qwen3-Embedding-0.6B kém hơn (dense 0,852) và chậm hơn khoảng 30%; multilingual-e5-large-instruct kém hơn (0,857) và chậm hơn khoảng 6 lần (embed corpus 33 phút so với 4 phút).
- **Tái lập:** chạy lại cùng cấu hình ở một process riêng cho 486/486 bảng xếp hạng top-25 trùng tuyệt đối; 3 lượt độ trễ trong mỗi run cũng trùng thứ hạng.

## 2. Điều kiện chạy

| Mục | Giá trị |
|---|---|
| Máy | AMD Ryzen 7 8845HS (8 nhân / 16 luồng), RAM 31,3 GB, Windows 11 Pro 10.0.26300, chỉ CPU (torch 2.14.1+cpu, 8 luồng torch) |
| Thư viện | Python 3.12.10, sentence-transformers 6.1.0, transformers 5.20.1 |
| Dữ liệu | `eval/datasets/sop-main`, `corpus_version=sop-main-2026-11-04-v2`, **frozen**, `test_sha256=f80c2e5d22a9d2f5454953135b61875630d55567ab9ec0f07e2feb8862102aaf`; 23 tài liệu (13 VI, 10 EN), 218 span. Validator `--require-reviewed` chạy đầu mỗi run (xanh) |
| Split | dev 24 câu (20 trả lời được, 4 âm; 10 cross-lingual), test 81 câu (70 trả lời được, 11 âm; 5 cross-lingual: 3 EN→VI, 2 VI→EN) |
| Chunk | `chunking: docproc` (`sopilot_ai.docproc`, `normalizer_version=2`, corpus dựng bằng docproc commit `26d1ed1`, code docproc tại HEAD không đổi so với commit đó); target 384 / max 512 token theo tokenizer của model đang đo; `title` = `doc_id`; `index_text` (tiêu đề › mục + nội dung) được embed và đánh chỉ mục BM25. bge-m3: 575 chunk, `chunks_sha256=cfe9d64b…c7895e6` |
| BM25 | Tokenizer cuối TECH-V2-ai-service §6.3 (`nfc-lower-w+-uni+bi+fold~-v2`): unigram + bigram, term bỏ dấu `~`, `lexical_len` chỉ đếm term gốc; k1 = 1,5, b = 0,75 |
| Hybrid | RRF `rrf_k = 60`, mỗi nhánh lấy 50 ứng viên, pool 25. Cổng: `dense_score` (cosine) của ứng viên đầu, luôn có giá trị vì index in-memory tính cosine cho mọi chunk; `bm25` không có cổng; có rerank thì cổng là `rerank_score` (sigmoid) |
| Model (HF revision) | bge-m3 `5617a9f6…`, bge-reranker-v2-m3 `953dc6f6…`, Qwen3-Embedding-0.6B `97b0c614…`, multilingual-e5-large-instruct `274baa43…` (chi tiết ở `eval/configs/`) |
| Mã harness | Các run chạy trên working tree dựa trên commit `f706308` cộng thay đổi V2-07 **chưa commit** (`run.json` ghi `dirty: true`). Khi commit, ghi hash vào ticket |

### Thước đo

- `span_recall@k`: với mỗi bộ bằng chứng OR, tỉ lệ span bắt buộc được top-k chunk phủ (một span tính là có khi các chunk phủ ≥ 50% ký tự của nó); lấy bộ tốt nhất. `full@k` = 1 khi một bộ được phủ đủ; `any@k` = 1 khi có ít nhất một span; `mrr_span` theo chunk đầu tiên chạm span gold. `hit@5` là proxy cũ cấp tài liệu/trang.
- CI là bootstrap 95% (lấy mẫu lại câu hỏi, 2000 lần, seed 0). So sánh giữa cấu hình là hiệu ghép cặp trên cùng câu.
- Độ trễ: thời gian truy xuất một câu (embed câu hỏi + chấm điểm in-memory + rerank nếu có), không gồm LLM; p50/p95 của mỗi lượt, trung bình 3 lượt, kèm độ lệch chuẩn giữa các lượt.

### Smoke khả thi (50 chunk docproc, 3 lượt, mỗi model một process)

| Model | Load | ms/chunk (warm, sd) | Peak RAM | Quyết định |
|---|---|---|---|---|
| bge-m3 | 8,9 s | 445 (0,1) | 2,3 GB | Vào ma trận (RQ1–RQ3, RQ5) |
| bge-reranker-v2-m3 | 10,7 s | 644 mỗi cặp (4,6) → ~16 s/câu với pool 25 | 3,5 GB | Vào ma trận nhưng chạy file cấu hình riêng (`rq2-rerank-bge-m3.yaml`), cả dev và test |
| Qwen3-Embedding-0.6B | 9,0 s | 582 (2,6) | 2,8 GB | Vào RQ5 |
| multilingual-e5-large-instruct | 10,4 s | 2.669 (9,2) | 2,1 GB | Vào RQ5 dù chậm (~26–33 phút cho corpus). Chậm gấp 6 lần bge-m3 dù cùng kiến trúc XLM-R large: **chưa rõ nguyên nhân, chưa điều tra** |

Lệnh: `python -m sopilot_eval.smoke_models --dataset datasets/sop-main --kind embed|rerank --model … --revision … --out results/smoke-models/<model>.json`.

## 3. RQ1: dense, BM25, hybrid (bge-m3)

Run: dev `eval/results/20261104-145508-23cb859c/`, test `eval/results/20261104-150006-3e20dc7c/` (phân tích: `…/analysis/analysis.md`), chạy lại để kiểm tái lập `eval/results/20261104-150255-1f9773d8/`.

### 3.1 Test, theo ngôn ngữ và cross-lingual (`span_recall@5` [CI 95%])

| Cấu hình | Tất cả (70) | VI→VI (32) | EN→EN (33) | Cross-lingual (5) | `full@5` tất cả | `mrr_span` | p50 / p95 ms (sd) |
|---|---|---|---|---|---|---|---|
| dense | 0,902 [0,84; 0,96] | 0,828 [0,70; 0,94] | 0,960 [0,91; 1,00] | 1,000 | 0,857 | 0,783 | 112 / 133 (0,9 / 1,7) |
| bm25 | 0,840 [0,76; 0,92] | 0,797 [0,67; 0,92] | 0,980 [0,94; 1,00] | 0,200 [0,00; 0,60] | 0,814 | 0,772 | 3 / 5 (0,2 / 0,5) |
| hybrid 1/1 | **0,938** [0,89; 0,99] | **0,906** [0,81; 0,98] | **0,990** [0,97; 1,00] | 0,800 [0,40; 1,00] | **0,914** | **0,816** | 116 / 142 (0,6 / 0,6) |
| hybrid 0,7/0,3 | 0,895 [0,83; 0,95] | 0,828 [0,70; 0,94] | 0,975 [0,93; 1,00] | 0,800 [0,40; 1,00] | 0,857 | 0,781 | 122 / 144 (4,5 / 5,6) |

Cross-lingual tách theo hướng (test): dense 3/3 EN→VI và 2/2 VI→EN; hybrid 2/3 EN→VI và 2/2 VI→EN; bm25 1/3 và 0/2.

Hiệu ghép cặp so với dense (test, `span_recall@5` / `full@5`):

| Cấu hình | Tất cả (70) | Cùng ngôn ngữ (65) | Cross-lingual (5) |
|---|---|---|---|
| bm25 | −0,062 [−0,14; +0,01] / −0,043 | −0,005 [−0,07; +0,06] / +0,015 | −0,800 [−1,00; −0,40] |
| hybrid 1/1 | +0,036 [−0,01; +0,09] / +0,057 [0,00; +0,13] | +0,054 [+0,02; +0,11] / +0,077 [+0,03; +0,15] | −0,200 [−0,60; 0,00] |
| hybrid 0,7/0,3 | −0,007 [−0,04; +0,02] / 0,000 | +0,008 [0,00; +0,02] / +0,015 | −0,200 [−0,60; 0,00] |

### 3.2 Dev (24 câu, 20 trả lời được; 4 tài liệu của pilot)

| Cấu hình | Tất cả | Cùng ngôn ngữ (10) | Cross-lingual (10) |
|---|---|---|---|
| dense | 1,000 | 1,000 | 1,000 |
| bm25 | 0,525 | 0,950 | 0,100 |
| hybrid 1/1 | 0,750 | 1,000 | 0,500 |
| hybrid 0,7/0,3 | 0,850 | 1,000 | 0,700 |

Dev nhỏ và có tỉ lệ cross-lingual cao (10/20, so với 5/70 ở test), nên thứ tự dense/hybrid ở dev ngược với test. Chỉ dùng dev để chọn tham số (RQ1b, RQ3), không dùng làm kết luận.

### 3.3 Test theo `query_types` (`span_recall@5` / `full@5`)

| Loại (n) | dense | bm25 | hybrid 1/1 | hybrid 0,7/0,3 |
|---|---|---|---|---|
| comparison (10) | 0,850 / 0,800 | 0,750 / 0,700 | 0,900 / 0,900 | 0,850 / 0,800 |
| condition_exception (27) | 0,907 / 0,889 | 0,870 / 0,852 | 1,000 / 1,000 | 0,907 / 0,889 |
| fact (24) | 0,917 / 0,875 | 0,812 / 0,792 | 0,896 / 0,875 | 0,875 / 0,833 |
| multi_passage (16) | 0,792 / 0,625 | 0,708 / 0,625 | 0,854 / 0,750 | 0,823 / 0,688 |
| number_deadline (26) | 0,910 / 0,846 | 0,859 / 0,808 | 0,929 / 0,885 | 0,910 / 0,846 |
| procedure (22) | 0,932 / 0,909 | 0,909 / 0,909 | 1,000 / 1,000 | 0,955 / 0,955 |
| responsibility (20) | 0,875 / 0,850 | 0,700 / 0,650 | 0,875 / 0,850 | 0,825 / 0,800 |

Một câu có nhiều loại nên tổng n lớn hơn 70. `multi_passage` là loại khó nhất cho mọi cấu hình: một chunk không chứa đủ bằng chứng, đúng điều ghép context §6.4a (V2-10) nhắm tới.

## 4. RQ1b: hybrid ở nhóm cross-lingual

### 4.1 Số liệu

Hybrid thua dense ở cross-lingual nên theo ticket chạy thêm `cross_lingual_bm25_factor` ∈ {0,3; 0}.

| Cấu hình | Dev cross (10) | Dev tất cả (20) | Test cross (5) | Test tất cả (70) |
|---|---|---|---|---|
| hybrid, hệ số 1,0 | 0,500 | 0,750 | 0,800 | 0,938 |
| hybrid, hệ số 0,3 | **0,600** | 0,800 | 0,800 | 0,938 |
| hybrid, hệ số 0 | 0,500 | 0,750 | 0,800 (EN→VI 3/3, VI→EN 1/2) | 0,938 |
| dense (tham chiếu) | 1,000 | 1,000 | 1,000 | 0,902 |

Luật chọn (định trước trong `analyze_v2_07.py`): cao nhất về dev cross `span_recall@5`, hòa thì xét dev tất cả. Kết quả: **0,3**, hơn 1,0 đúng **1 câu** trên dev; trên test không khác 1,0. Cùng ngôn ngữ không đổi (hệ số chỉ chạm chunk khác ngôn ngữ câu hỏi).

### 4.2 Vì sao hệ số không có tác dụng

Năm câu cross-lingual dev mà hybrid hệ số 0 vẫn trượt đều là câu tiếng Việt hỏi trang GitLab tiếng Anh. Dense xếp `gitlab-buddies`/`gitlab-meetings` ở 3 vị trí đầu; hybrid xếp `tb-qt05`, `tb-qt03`, `vn-qd1308`, `nb-qt03` (tài liệu tiếng Việt, sai) lên đầu. BM25 của câu tiếng Việt chỉ khớp được tài liệu tiếng Việt, và các chunk đó **cùng ngôn ngữ với câu hỏi** nên hệ số không giảm chúng; hệ số 0 còn xóa phần BM25 ít ỏi của chunk đúng. Thiết kế §6.4 giả định nhiễu nằm ở chunk khác ngôn ngữ, còn dữ liệu cho thấy nhiễu nằm ở chunk cùng ngôn ngữ nhưng sai tài liệu.

Hướng có thể xét (chưa đo, owner quyết): giảm trọng số BM25 chung (0,7/0,3 cải thiện dev cross lên 0,70 nhưng mất phần lợi cùng ngôn ngữ ở test); chỉ cộng nhánh BM25 khi điểm BM25 của ứng viên đủ cao; hoặc giữ nguyên và chấp nhận vì cross-lingual là thiểu số trong dùng thật. Cả ba cần thêm câu cross-lingual (test chỉ có 5) mới kết luận được.

## 5. RQ2: rerank

Run: dev `eval/results/20261104-160249-6f8cf9d6/`, test `eval/results/20261104-162508-69ca2844/`. Cùng pool 25 của hybrid 1/1; rerank chấm lại 25 ứng viên bằng `index_text`, `max_length=512`. Chạy cả tập dev và test (không cần tập con), 3 lượt.

| Test (70) | `span_recall@5` | `full@5` | `span_recall@10` | `full@10` | `mrr_span` | Cross (5) | VI→VI (32) | EN→EN (33) | p50 / p95 ms (sd) |
|---|---|---|---|---|---|---|---|---|---|
| hybrid (rerank tắt) | 0,938 | 0,914 | 0,971 | 0,957 | 0,816 | 0,800 | 0,906 | 0,990 | 151 / 182 (1,2 / 1,0) |
| hybrid + rerank | **0,957** | **0,929** | **0,979** | **0,971** | **0,943** | **1,000** | **0,922** | 0,985 | 17.697 / 20.082 (78 / 129) |

Hiệu ghép cặp rerank − hybrid (test): `span_recall@5` +0,019 [−0,02; +0,06]; `full@5` +0,014 [−0,04; +0,07]; `mrr_span` +0,127 [+0,06; +0,19]. Cùng ngôn ngữ (65): `mrr_span` +0,096 [+0,03; +0,16], recall không đổi. Cross-lingual (5): +0,200 [0,00; +0,60]. Dev: 0,750 → 0,950 (cross 0,50 → 0,90).

Theo `query_types` (test, `span_recall@5` / `full@5`): comparison 0,850 / 0,700; condition_exception 1,000 / 1,000; fact 0,917 / 0,875; multi_passage 0,875 / 0,750; number_deadline 0,962 / 0,923; procedure 1,000 / 1,000; responsibility 0,900 / 0,850.

Đọc kết quả: rerank ít khi đưa thêm bằng chứng vào top-5 (pool 25 của hybrid vốn đã chứa bằng chứng ở 97% câu), mà chủ yếu **đẩy nó lên hạng 1** (`mrr_span`) và sửa đúng điểm yếu cross-lingual của hybrid. Độ trễ 17,7 s mỗi câu trên CPU laptop là không dùng được cho chat; rerank chỉ khả thi nếu chạy trên GPU, trên pool nhỏ hơn hoặc model nhỏ hơn (chưa đo).

## 6. RQ3: cổng ngưỡng (false refusal / false answer)

Luật chọn định trước: trên dev, chọn ngưỡng nhỏ nhất làm cực tiểu `false_refusal + false_answer` (trọng số bằng nhau); áp nguyên lên test. "Ngưỡng tốt nhất trên test" chỉ để tham chiếu, không dùng để chọn. Đây là proxy cấp truy xuất (từ chối khi điểm cổng < ngưỡng), chưa phải từ chối ở câu trả lời của LLM.

| Cấu hình (điểm cổng) | Ngưỡng dev | Dev FR / FA | **Test FR / FA** | Ngưỡng tốt nhất trên test (FR / FA) | Test `gate` trung bình: trả lời được / âm |
|---|---|---|---|---|---|
| dense (cosine) | 0,6192 | 0,200 / 0,000 | **0,086 / 0,455** | 0,6669 (0,257 / 0,000) | 0,697 / 0,597 |
| hybrid 1/1 (cosine ứng viên đầu) | 0,4815 | 0,000 / 0,250 | **0,014 / 0,909** | 0,6605 (0,314 / 0,000) | 0,684 / 0,584 |
| hybrid 0,7/0,3 | 0,4862 | 0,000 / 0,250 | 0,014 / 0,909 | 0,6621 (0,271 / 0,000) | 0,689 / 0,590 |
| hybrid hệ số 0,3 | 0,5768 | 0,350 / 0,000 | 0,043 / 0,636 | 0,6605 (0,300 / 0,000) | 0,683 / 0,584 |
| hybrid + rerank (`rerank_score` sigmoid) | 0,2686 | 0,050 / 0,000 | **0,014 / 0,455** | 0,7087 (0,029 / 0,000) | 0,959 / 0,288 |
| bm25 | không có cổng | | | | |

Nhận xét:
- Dev có 4 câu âm, test 11. Một câu âm trên dev là 25 điểm phần trăm FA, nên ngưỡng nhảy theo từng câu: ở hybrid, luật chọn chấp nhận lọt 1/4 câu âm để không từ chối nhầm câu nào, và trên test để lọt 10/11.
- Ngay cả ngưỡng tốt nhất trên test (cosine ≈ 0,66–0,67) cũng phải từ chối nhầm 26–31% câu trả lời được để chặn hết câu âm. Cosine của bge-m3 trên corpus này không tách hai nhóm đủ rõ để một ngưỡng duy nhất vừa ít từ chối nhầm vừa chặn câu âm.
- Với rerank, 4 câu âm của dev có điểm 0,00–0,10 còn 11 câu âm của test trải từ 0,01 đến 0,68; ngưỡng dev nằm ngay trên câu âm cao nhất của dev nên để lọt 5/11 câu âm test. Nếu chọn trên test (chỉ để tham chiếu) thì 0,71 cho FR 0,029 / FA 0: cổng rerank có khả năng tách, nhưng dev hiện tại không đủ để chọn ngưỡng.
- Câu âm của sop-main được soạn để gần chủ đề corpus (xem `negative-audit.draft.jsonl`), nên đây là trường hợp khó; câu hỏi lạc đề hẳn sẽ có cosine thấp hơn nhiều.

## 7. RQ5: so model embedding

Run: dev `eval/results/20261104-151314-80d982a6/`, test `eval/results/20261104-155353-f9df1f69/`. Cùng target/max 384/512, đếm bằng tokenizer của từng model (Qwen3 cho 561 chunk, hai model XLM-R cho 575). Câu hỏi có tiền tố instruction theo model card (Qwen3, e5), tài liệu không.

| Model | Chế độ | Test tất cả (70) | VI→VI (32) | EN→EN (33) | Cross (5) | `full@5` | `mrr_span` | Dev tất cả / cross | Embed corpus | Truy xuất p50 ms (sd) |
|---|---|---|---|---|---|---|---|---|---|---|
| bge-m3 | dense | **0,902** | 0,828 | **0,960** | **1,000** | **0,857** | **0,783** | 1,000 / 1,000 | 239 s (575 chunk) | 139 (0,6) |
| bge-m3 | hybrid | **0,938** | **0,906** | **0,990** | 0,800 | **0,914** | **0,816** | 0,750 / 0,500 | | 146 (2,5) |
| Qwen3-Embedding-0.6B | dense | 0,852 | 0,797 | 0,914 | 0,800 | 0,814 | 0,688 | 0,850 / 0,850 | 278 s (561) | 142 (2,4) |
| Qwen3-Embedding-0.6B | hybrid | 0,890 | 0,859 | 0,965 | 0,600 | 0,857 | 0,771 | 0,625 / 0,250 | | 145 (0,6) |
| multilingual-e5-large-instruct | dense | 0,857 | 0,812 | 0,939 | 0,600 | 0,843 | 0,712 | 0,900 / 0,800 | 1.997 s (575) | 696 (10,0) |
| multilingual-e5-large-instruct | hybrid | 0,902 | 0,891 | 0,960 | 0,600 | 0,871 | 0,770 | 0,600 / 0,200 | | 699 (3,2) |

- Thời gian embed corpus đo ở lần chạy đầu (cache trống) của từng model; bge-m3 lấy từ run dev RQ1 vì run RQ5 dùng lại cache của nó. Process RQ5 giữ cả ba model, peak RAM 5,0 GB; độ trễ bge-m3 ở đây (139 ms) cao hơn run RQ1 (112 ms) do chạy chung process, nên chỉ so độ trễ giữa các model trong cùng bảng này.
- RQ3 theo model (cổng cosine dense, ngưỡng dev → test FR/FA): Qwen3 0,614 → 0,057 / 0,545; e5 0,860 → 0,029 / 0,727. Ở mọi model, cosine của câu âm sát cosine của câu trả lời được (e5: 0,886 so với 0,911).
- Kết luận RQ5: không có lý do đổi khỏi bge-m3 trên dữ liệu này.

## 8. Đề xuất cho owner (chốt 2026-11-07, không áp dụng vào cấu hình)

> Bảng này dựa trên `sop-main`. Kết luận về chế độ mặc định bị §12 (`sop-main-v2`) thay thế: dense hơn hybrid ở câu cross-lingual.

| Mục | Đề xuất | Bằng chứng / độ tin cậy |
|---|---|---|
| Chế độ truy xuất mặc định | Giữ hybrid RRF 1/1 trên bge-m3 | Hơn dense ở cùng ngôn ngữ, CI không chứa 0 (65 câu) |
| Trọng số 0,7/0,3 | Không dùng làm mặc định | Không hơn dense ở test |
| `retrieval.cross_lingual_bm25_factor` | Luật ticket chọn 0,3 trên dev. Đề xuất **giữ 1,0** cho tới khi có thêm câu cross-lingual: 0,3 chỉ hơn 1 câu dev, test không khác, và cơ chế (mục 4.2) cho thấy hệ số không nhắm đúng nguyên nhân | Yếu: 10 câu dev, 5 câu test |
| `retrieval.thresholds` | Ngưỡng theo luật dev: dense 0,619, hybrid 0,482, hybrid_rerank 0,269. Đề xuất **chưa ghi** vào ai-service: FA test 0,455 / 0,909 / 0,455. Cần thêm câu âm khó cho dev (hiện 4, dễ hơn test) rồi chọn lại, hoặc chấp nhận cổng cosine chỉ chặn câu lạc đề rõ và để LLM tự từ chối (D2) | Yếu |
| Rerank | Chưa bật mặc định trên CPU (17,7 s/câu). Nếu có GPU hoặc model rerank nhẹ hơn thì đáng đo lại: `mrr_span` +0,13, sửa cross-lingual, và điểm rerank là cổng tách câu âm tốt nhất | Trung bình (recall@5 không khác rõ; MRR khác rõ) |
| Model embedding | Giữ bge-m3 | Bằng hoặc hơn hai model kia ở mọi nhóm của test; embed nhanh nhất |
| Mục tiêu NFR recall@5 ≥ 0,80 | Không cần hạ: dense 0,902, hybrid 0,938 trên test | Trung bình |

Ghi chú: trong lúc chạy V2-07, một phiên làm V2-09 (nay đã commit ở `30f530b`, không thuộc báo cáo này) đã thêm `services/ai-service/config/models.yaml` với `retrieval.thresholds` giữ chỗ (dense 0,45, hybrid 0,45, hybrid_rerank 0,30) và `cross_lingual_bm25_factor: 1.0`, cùng `sopilot_ai.retrieval.lexical`. Báo cáo này **không sửa** file đó. Tokenizer của module đó cho cùng term với harness trên 105 câu hỏi và 3 tài liệu mẫu (kiểm 2026-11-04). Lưu ý giá trị giữ chỗ 0,45 dưới ngưỡng dev của dense (0,619) và hybrid (0,482), tức sẽ cho qua gần như mọi câu âm của test.

## 9. Giới hạn và những gì chưa kiểm

- **Quy mô nhỏ:** 23 tài liệu, 575 chunk; test 70 câu trả lời được, 11 câu âm, **5 câu cross-lingual**. CI ở nhóm cross-lingual rộng gần hết thang [0; 1].
- **Dev khác phân bố test:** dev dùng 4 tài liệu pilot, nửa số câu là cross-lingual; ngưỡng và hệ số chọn trên dev có thể không chuyển sang test (đã thấy ở RQ3).
- **Chỉ đo truy xuất:** V2-10 chưa xong, chưa có câu trả lời của LLM, faithfulness hay trích dẫn. RQ3 là proxy truy xuất.
- **BM25 tách từ đơn giản:** `\w+` + bigram + term bỏ dấu; không có tokenizer từ tiếng Việt hay stemming tiếng Anh.
- **Tiêu đề tài liệu là `doc_id`** (ví dụ `nb-qt02`) vì manifest không có tiêu đề người dùng đặt; service thật dùng tiêu đề khi upload, nên `index_text` của service sẽ khác.
- **Ngôn ngữ câu hỏi** lấy từ nhãn dataset, không phải bộ nhận diện ngôn ngữ của service (§7.1).
- **Chunk sát 512 token** có thể bị cắt 2 token cuối khi model thêm token đặc biệt (tokenizer docproc đếm không có token đặc biệt).
- **Chunk không dựng từ PDF gốc** mà từ extraction Docling đã cache (`results/extraction-clean/structured`) và 2 trang Markdown; mọi tài liệu được kiểm render lại khớp từng byte với corpus đã freeze trước khi chunk.
- Rerank chỉ đo một model và pool 25; không đo pool nhỏ hơn hay model rerank nhẹ hơn.
- **Chưa kiểm:** e5 chậm bất thường (chưa điều tra); RQ4 (độ trễ lọc quyền trên Postgres) ngoài phạm vi; độ trễ đo trên laptop có thể chịu ảnh hưởng tác vụ nền; không có GPU.
- **Mã chưa commit:** các run chạy trên working tree (`dirty: true`).

## 10. Tái lập

```powershell
cd eval
uv sync --extra local --extra dev          # gồm services/ai-service (path dependency)
$env:HF_HUB_OFFLINE = "1"
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split dev --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq5-models.yaml --split dev|test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq2-rerank-bge-m3.yaml --split dev|test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.analyze_v2_07 --dev results/<dev> --test results/<test> --out results/<test>/analysis
```

`eval/results/` và `eval/datasets/` bị gitignore: thư mục run và tập dữ liệu chỉ có trên máy owner.

## 11. Kiểm thử harness

- `.venv/Scripts/python.exe -m pytest -q` trong `eval/`: 90 passed (2026-11-04). Bộ test V2-07 ở `tests/test_v2_07_retrieval.py`: tokenizer `~`, cổng `dense_score` cho ứng viên chỉ có BM25, hệ số cross-lingual, BM25 không có cổng, metric span, luật chọn ngưỡng).

## 12. Bộ mở rộng `sop-main-v2` (đã freeze 2026-11-05)

Lý do: trên `sop-main`, 57–65/70 câu test đạt span_recall@5 = 1,0 ở mọi cấu hình; 36/81 câu nêu mã tài liệu; chỉ có 5 câu cross-lingual và 4 negative ở dev. Bộ này không đủ để phân biệt các cấu hình. `sop-main` giữ nguyên (hash `f80c2e5d…aaf`).

`eval/datasets/sop-main-v2` gồm toàn bộ câu v1 cộng 96 intent mới (`subset=v2`), xem `eval/datasets/sop-main-v2/README.md`:
- Câu mới không nêu mã tài liệu; mức trùng từ với quote giảm từ 0,52 (v1) xuống 0,40.
- Mỗi intent có hai câu: một cùng ngôn ngữ, một cross-lingual.
- Test có 200 câu trả lời được (70 cross-lingual) và 39 negative; dev có 40 câu trả lời được và 14 negative.
- CI dùng bootstrap theo cụm `intent_id`.

**Quy trình duyệt (ghi đúng như đã làm):**
- Claude soạn 188 câu mới.
- Một subagent Claude (Opus 5.5, context sạch) rà từng câu với corpus:
  - 168 câu đạt;
  - 16 câu có lỗi rõ và đã được sửa, phần lớn là span vàng ngắn hơn đáp án;
  - 2 câu chờ owner quyết;
  - 2 câu đề xuất loại.
- Owner quyết hai điểm:
  - Test được dẫn tài liệu dev khi nội dung trùng nguyên văn (nb-qt03/tb-qt03). Ghi ở README, mục 7.
  - Thay `v2d-buddy-pick`, vốn trùng intent v1, bằng `v2d-buddy-mentorship`.
- Owner **duyệt trên kết quả rà soát của Claude**, không tự đối chiếu từng câu với corpus.
  - Mỗi bản ghi trong `review.jsonl` có `reviewer_id=owner:tiên`, `drafted_by=Claude`, `ai_reviewer=claude-opus-5-5` và `review_basis=claude_review`.
  - Chi tiết rà soát nằm trong `REVIEW-claude.md` và `review-verdicts.claude.jsonl`.
- Freeze: `test_sha256 = a568bf74903ede0e153bb16883ba24cc4ca76c9ad30b5410b2b71e830df18059`.

**Số chính thức** (run RQ1/RQ3: `results/20261105-115341-b569765f` dev, `…115557-998681b7` test; RQ5: `…120446-accf98a6` dev, `…121034-50ef4f1c` test; phân tích trong `<test>/analysis/`; `--repeats 3`; `dataset_info.reviewed=true`). Bảng là span_recall@5 trên test [CI 95 %]:

| cấu hình | tất cả (200) | cùng ngôn ngữ (130) | cross-lingual (70) |
|---|---|---|---|
| dense bge-m3 | **0,873** [0,82; 0,92] | 0,886 | **0,850** [0,76; 0,93] |
| bm25 | 0,602 | 0,879 | 0,086 |
| hybrid 1/1 | 0,803 | **0,921** | 0,586 [0,47; 0,70] |
| hybrid 0,7/0,3 | 0,823 | 0,897 | 0,686 |
| hybrid xl0,3 / xl0 | 0,798 / 0,801 | 0,921 | 0,571 / 0,579 |
| dense Qwen3-0,6B (RQ5) | 0,868 | 0,871 | **0,864** |
| hybrid Qwen3-0,6B | 0,769 | 0,906 | 0,514 |
| dense e5-large-instruct | 0,695 | 0,862 | 0,386 |
| hybrid e5-large-instruct | 0,663 | 0,905 | 0,214 |

Hiệu số ghép cặp (span_recall@5, số câu thắng/thua):
- **Cross-lingual: dense hơn hybrid +0,264 [0,16; 0,37], thắng 19, thua 0.** Hybrid 0,7/0,3 giảm thiệt hại (hơn hybrid 1/1 +0,100, thắng 7, thua 0) nhưng vẫn thua dense.
- **Cùng ngôn ngữ: hybrid hơn dense +0,035 [−0,00; +0,08], thắng 8, thua 2.** Xu hướng có lợi cho hybrid, nhưng CI chạm 0. Trên mrr_span hiệu số là +0,051 [+0,01; +0,09].
- Toàn bộ: dense hơn hybrid +0,070 [+0,02; +0,12].
- `cross_lingual_bm25_factor` không có tác dụng.
  - xl0,3 so với hybrid: thắng 0, thua 1. xl0: thắng 3, thua 3.
  - RQ1b trên dev chọn `hybrid` (hệ số 1,0).
  - Cơ chế như §4: BM25 đẩy lên chunk *cùng ngôn ngữ với câu hỏi* nhưng sai tài liệu, còn hệ số chỉ giảm điểm chunk khác ngôn ngữ.
- RQ5:
  - Qwen3-0,6B dense ngang bge-m3 dense, cả toàn bộ (0,868 so với 0,873) lẫn cross-lingual (0,864 so với 0,850). CI chồng nhau.
  - e5-large-instruct yếu rõ ở cross-lingual (0,386).
  - Với mọi model, hybrid đều kéo cross-lingual xuống.

RQ3 (ngưỡng chọn trên dev, đo trên test, 200 câu trả lời được / 39 negative):

| cấu hình | ngưỡng dev | FR test | FA test | oracle test t (FR/FA) |
|---|---|---|---|---|
| dense bge-m3 | 0,6059 | 0,245 | 0,538 | 0,6430 (0,430/0,103) |
| hybrid bge-m3 | 0,6059 | 0,385 | 0,359 | 0,6359 (0,500/0,128) |
| dense Qwen3-0,6B | 0,6119 | 0,250 | 0,538 | 0,6568 (0,390/0,308) |
| dense e5 | 0,8593 | 0,280 | 0,615 | 0,8873 (0,435/0,256) |

Cổng cosine top-1 tách kém câu trả lời được với negative "suýt đúng". Ngay cả ngưỡng tối ưu đo trên chính test vẫn từ chối nhầm 39–50 % câu trả lời được. Không nên dựa vào một ngưỡng cosine duy nhất để từ chối trả lời.

**RQ2: rerank trên bộ v2.**
- Run: `results/20261105-145227-2f4fd6e7` (dev) và `…173421-90a5e580` (test); phân tích trong `<test>/analysis/`.
- `--repeats 1`. Độ trễ đã được đo 3 lượt trên `sop-main` (§5).
- Rerank bằng bge-reranker-v2-m3 trên pool 25 ứng viên của hybrid.

| cấu hình (test) | tất cả (200) | cùng ngôn ngữ (130) | cross-lingual (70) | mrr_span tất cả |
|---|---|---|---|---|
| hybrid | 0,803 | 0,921 | 0,586 | 0,650 |
| **hybrid + rerank** | **0,940** [0,91; 0,97] | **0,965** | **0,893** [0,81; 0,96] | **0,894** |
| dense (RQ1, để so) | 0,873 | 0,886 | 0,850 | 0,740 |

Hiệu số span_recall@5:
- **Rerank so với hybrid:** +0,137 [+0,09; +0,19] (thắng 31, thua 2).
  - Cross-lingual: +0,307 [+0,21; +0,41] (thắng 22, thua 0).
  - Cùng ngôn ngữ: +0,045 [+0,01; +0,08] (thắng 9, thua 2).
- **Rerank so với dense** (ghép cặp với run RQ1, bootstrap theo câu):
  - Tất cả: +0,067 [+0,02; +0,11] (thắng 20, thua 4).
  - Cùng ngôn ngữ: +0,079 [+0,04; +0,13].
  - Cross-lingual: +0,043 [−0,04; +0,13], không rõ.
- **Ý nghĩa:** rerank sửa gần hết thiệt hại cross-lingual mà BM25 gây ra cho hybrid. Đây là cấu hình tốt nhất trên mọi nhóm.
- **Dev:** 0,975 so với 0,675 của hybrid.
- **Cái giá:** p50 **18,1 s/câu**, p95 21,5 s, trên CPU này. Không rerank thì 0,15 s. Peak RAM 5,1 GB.
- **Thời gian chạy:** lượt test chạy liền mạch 72 phút vì máy được giữ thức. Hai lần trước bị dừng là do máy ngủ (Modern Standby/sleep, xem System Event Log), không phải thiếu RAM.

**RQ2b: rerank trên nguồn ứng viên nào?** (owner hỏi 2026-11-05)
- Run: `results/20261105-211945-9d7eabc7` (dev) và `…214840-ad128122` (test).
- Config `configs/rq2b-rerank-pools.yaml`, chạy `--repeats 1`.

| rerank top-25 của (test) | tất cả (200) | cùng ngôn ngữ (130) | cross-lingual (70) | mrr_span tất cả |
|---|---|---|---|---|
| dense | 0,940 | 0,958 | 0,907 | 0,895 |
| hybrid 1/1 (RQ2) | 0,940 | 0,965 | 0,893 | 0,894 |
| hybrid 0,7/0,3 | 0,945 | 0,965 | 0,907 | 0,898 |

- **Ba nguồn ứng viên cho kết quả như nhau.** Mọi hiệu số span_recall@5 giữa chúng nằm trong ±0,014, CI chứa 0, và khác biệt chỉ ở 1–2 câu.
  - Trước khi chạy, mình đã ước tính phần trần: tỉ lệ câu có đủ bằng chứng trong top 25 là 0,960 với dense, 0,965 với hybrid 1/1 và 0,975 với hybrid 0,7/0,3.
  - Vì trần gần như nhau, nguồn nào thì reranker cũng đạt gần trần.
- **Dense + rerank so với dense:** +0,067 [+0,03; +0,11] (thắng 19, thua 3); mrr_span +0,155.
- **Dev:** cả ba cấu hình rerank đạt 1,000. Dev không phân biệt được chúng.
- **Độ trễ:** p50 15,7 s/câu cho cả dense + rerank và hybrid 0,7/0,3 + rerank. Lượt hybrid + rerank ở RQ2 đo được 18,1 s, nhưng đó là lần chạy khác nên không so trực tiếp được. Peak RAM 5,1 GB.
- **RQ3:** dense + rerank và hybrid 0,7/0,3 + rerank cho cùng ngưỡng dev và cùng oracle test như hybrid + rerank.
- **Hệ quả:**
  - Khi có rerank, nhánh BM25 không đóng góp đo được trên bộ này.
  - **Dense + rerank là cấu hình đơn giản nhất mà vẫn đạt chất lượng tốt nhất**, không cần index BM25 hay fusion.
  - Khi không rerank, BM25 vẫn có ích cho câu cùng ngôn ngữ (§12 RQ1).

**RQ3 với cổng điểm rerank (sigmoid):**
- Ngưỡng chọn trên dev là 0,1076. Đo trên test: FR 0,140 / FA 0,564.
- Oracle trên test: t = 0,7059 cho FR 0,300 / FA 0,051. Cổng cosine của hybrid cho FR 0,500 / FA 0,128.
- Điểm rerank tách câu trả lời được với negative tốt hơn cosine, nhưng ngưỡng chọn trên dev chuyển sang test rất kém: FA từ 0,143 lên 0,564. Lý do là dev chỉ có 14 negative và 4 tài liệu.
- Chưa ghi ngưỡng này vào `retrieval.thresholds`.

**Hạn chế của chính bộ v2:**
- Dev quá dễ với dense: bge-m3 dense đạt 1,000 trên cả 40 câu dev.
  - Nguyên nhân: dev chỉ gồm 4 tài liệu.
  - Hệ quả: mọi lựa chọn "trên dev" ở RQ1b và RQ3 có độ phân giải thấp. Riêng RQ3 lệch giữa dev và test rõ: FA dev của dense là 0,071, còn FA test là 0,538.
- Câu hỏi vẫn do Claude soạn và owner chưa đối chiếu độc lập với corpus.
- Corpus chỉ có 23 tài liệu.

Đề xuất bổ sung cho §8 (owner chốt 2026-11-07: các lựa chọn cấu hình chuyển sang V2-10/V2-18, không áp dụng ở đây):
1. **Mặc định dense cho câu cross-lingual.** Có hai hướng:
   - (a) Phát hiện ngôn ngữ câu hỏi; nếu khác ngôn ngữ đa số của workspace thì tắt nhánh BM25. Với câu cùng ngôn ngữ thì giữ hybrid, vì hybrid có xu hướng hơn dense.
   - (b) Dịch câu hỏi trước khi chạy BM25.
   - Cả hai cần một vòng đo riêng trên `sop-main-v2`.
2. **Nếu phải chọn một cấu hình cố định:**
   - Có rerank: dense + rerank (hoặc hybrid + rerank, chất lượng như nhau) tốt nhất trên mọi nhóm, nhưng 16–18 s/câu trên CPU. Chỉ khả thi khi có GPU hoặc khi chấp nhận độ trễ. Dense + rerank đơn giản hơn vì không cần BM25.
   - Không rerank: dense bge-m3 tốt nhất về tổng thể. Trong các cấu hình hybrid, 0,7/0,3 ít hại hơn 1/1. Không ghi `cross_lingual_bm25_factor` khác 1,0.
3. **Qwen3-Embedding-0,6B là phương án thay thế ngang hàng.** Chưa có bằng chứng để đổi model.
4. **RQ3:** chưa ghi `retrieval.thresholds` từ số này. Cần thêm tín hiệu ngoài cosine (rerank sigmoid ở RQ2 hoặc kiểm chứng ở tầng LLM), và cần dev khó hơn trước khi chọn ngưỡng.

Chưa làm:
- Đo đề xuất 1(a) và 1(b).
- Các run preview trong `results/v2-preview/` đã bị thay thế, không trích dẫn nữa.

`eval/` pytest sau thay đổi: 95 passed (thêm `tests/test_extend_dataset.py`).

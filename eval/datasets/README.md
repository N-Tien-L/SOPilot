# Bộ nhãn truy xuất V2-06

Bộ chính từ 2026-11-01: [sop-main/README.md](sop-main/README.md) (23 tài liệu canonical docproc, 105 câu dev/test). Pilot nguồn thật ngày 2026-10-25 (nay là nguồn của tập dev): [sop-pilot/README.md](sop-pilot/README.md), [phiếu duyệt](sop-pilot/REVIEW.md). Có 4 tài liệu VI/EN, 24 câu dev/draft, chưa có nhãn owner duyệt hoặc test chính thức. Mẫu synthetic bên dưới vẫn giữ để kiểm công cụ.

`annotation-example/` là ví dụ **synthetic, draft**, gồm 1 tài liệu EN và 5 câu EN/VI. Không dùng số liệu của nó làm kết quả RQ. Corpus nghiên cứu và quy mô vẫn cần owner chốt/duyệt theo V2-06; thiết kế GitLab ở `docs/04-reports/HANDOFF-research-02-dataset-and-labeling.md` là tài liệu nguồn khi thu thập corpus thật.

## Schema v1

| File | Contract |
|---|---|
| `manifest.json` | `corpus_version`, `normalization_version`, `documents`: mỗi mục có `doc_id`, đường dẫn tương đối `path`, `lang`, SHA-256 text canonical `sha256`, `source`, `license` |
| `corpus/` | Chỉ canonical UTF-8/NFC/LF được index; không chứa gold, nhãn hay câu trả lời tham chiếu. SHA tính trên bytes canonical |
| `evidence.jsonl` | `span_id`, `doc_id`, `section_id`, `start_char`, `end_char`, `quote`, `quote_sha`; offset **Unicode code point**, 0-based/end-exclusive, trên toàn canonical document. `pages` tùy chọn với PDF |
| `questions.master.jsonl` | `id`, `intent_id`, `policy_family_id`, `leakage_group_id`, `split` (`dev/test`), `question`, `lang`, `corpus_lang`, `cross_lingual`, `answerable`, `evidence_sets`, `reference_answer`, `query_types`, `review_status`, `label_version` |
| `review.jsonl` | Log riêng: `question_id`, `decision` (`reviewed/adjudicated`), `reviewer_id`, `reviewed_at`, `notes`, `label_version`, `corpus_version`; câu âm thêm `unanswerable_audit` (`reason`, `search_terms`, `candidate_sections`, `conclusion`) |

`evidence_sets=[[s1,s2],[s3]]`: cần đủ s1+s2 **hoặc** s3. Câu âm có `evidence_sets=[]`, `reference_answer=""`, audit trên toàn corpus; không gán âm vì retriever không tìm thấy. `expected` là doc/page **proxy suy ra**, nếu có thì phải khớp projection, không duy trì gold hai lần.

`query_types`: một hoặc nhiều nhãn `fact`, `procedure`, `condition_exception`, `number_deadline`, `responsibility`, `comparison`, `multi_passage`. Trạng thái nhãn là `draft/reviewed/adjudicated/excluded`, không phải trạng thái ticket.

Cặp EN/VI, cùng policy/leakage group và evidence không được đi qua dev/test. Validator kiểm trùng ID/text, bằng chứng trùng/overlap giữa hai split, hash/quote/offset và đường dẫn thoát dataset. Nó không phát hiện được mọi trùng nghĩa hoặc xác nhận tính đúng của nhãn.

## Lệnh từ `eval/`

```powershell
cd eval
./.venv/Scripts/python.exe -m sopilot_eval.dataset --dataset datasets/annotation-example
./.venv/Scripts/python.exe -m sopilot_eval.dataset --dataset datasets/annotation-example --require-reviewed
```

Lệnh thứ hai **phải thất bại**: mẫu chưa có người duyệt. Không điền reviewer giả hoặc đổi `draft` chỉ để qua validator. Chỉ freeze corpus/nhãn sau khi reviewer đọc nguồn, kiểm đủ điều kiện/ngoại lệ, xác nhận bản VI và audit câu âm; lưu hash/version/split cùng log.

Validator/nhãn chưa tích hợp vào scorer span-aware hay chunker `docproc`. `sopilot_eval.run` hiện dùng `questions.jsonl` + `expected` và báo proxy doc/page; số liệu RQ chính thức vẫn chờ V2-22/V2-07. Không giả lập span thành trang hay file nhỏ để dùng metric hiện tại.

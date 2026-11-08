---
id: RESEARCH-02-dataset-and-labeling
title: "Nhóm 02: Corpus GitLab và thiết kế eval EN/VI có nhãn bằng chứng"
status: final
type: research
scope: research
created: 2026-10-19
updated: 2026-10-19
author: "Owner"
refs:
  - docs/04-reports/RESEARCH-01-scope-and-rqs.md
  - docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md
  - eval/README.md
---

# Corpus và bộ eval đề xuất cho SOPilot

## 1. Khuyến nghị cuối và mức độ hoàn tất

**Chọn một tập con GitLab Handbook, SOP tiếng Anh gốc: 8 trang công khai, khởi đầu 24 mục có ranh giới heading ở §3. Xây 120 ý hỏi khác nhau, mỗi ý có một câu EN và một câu VI: 240 dòng query; dev 30 ý/60 dòng, test 90 ý/180 dòng.** Trong mỗi ngôn ngữ: 72 câu một đoạn, 24 câu nhiều đoạn, 24 câu unanswerable. Chọn trước tập con answer-level 32 ý/64 dòng, dùng một generator API cố định, hai điều kiện rerank tắt/bật và người duyệt. Không dịch corpus, không trộn handbook công ty khác.

Đây là phương án triển khai được đề xuất theo yêu cầu owner ưu tiên nhanh, không cần thêm vòng chọn nguồn thông thường. RQ1–3 là lõi; RQ5 dùng hai embedding do nhóm 03 chọn, chạy tuần tự trên CPU/RAM 32 GB; RQ4 ngoài lõi. Không cần generation cho toàn bộ retrieval eval hoặc cho cả hai embedding. Giữ nguyên giới hạn tuyên bố ở nhóm 01: query EN/VI trên corpus EN, chưa kiểm chứng corpus VI hoặc cross-lingual hai chiều.

`final` nghĩa là hoàn tất tài liệu lựa chọn và thiết kế nhóm 02. **Chưa có corpus tải về/ghim SHA, 120 ý hỏi, nhãn gold hoặc answer outputs đã duyệt.** Những con số bên dưới là thiết kế trước thí nghiệm, không phải kiểm kê dữ liệu đã tạo hay bằng chứng power thống kê. Không tự nhận owner đã phê duyệt PRD/ADR/PLAN hoặc đã có reviewer được phân công.

## 2. Đã kiểm tra gì trong repo

Đã kiểm tra `git status --short` trước khi đọc nội dung; nhánh hiện tại `fix/auth-google-roster-admission` có nhiều thay đổi staged/unstaged/untracked từ trước, bao gồm `eval/`. File đích nhóm 02 chưa tồn tại lúc bắt đầu. Đã đọc `AGENTS.md`, `docs/README.md`, toàn bộ handoff nhóm 01 và handoff workstreams; không đọc `.env`. Chỉ thêm báo cáo này, không đổi nhánh, code, PRD/ADR/PLAN/ticket hoặc file của session khác. Nhóm 03–04 đang chạy song song; không chờ hoặc giả định kết quả của họ.

| File/đầu vào đã đọc | Hiện trạng trên đĩa | Hệ quả cho thiết kế |
|---|---|---|
| `eval/README.md`, `datasets/smoke/` | 3 file Markdown, 9 query; 7 answerable, 2 unanswerable; 8 VI, 1 EN. Corpus smoke trộn EN/VI; chỉ một câu VI có `cross_lingual: true` | Chỉ smoke công cụ, không tái dùng làm corpus/nghiên cứu mới hoặc cộng vào 120 ý |
| `questions.jsonl` | Trường đang dùng: `id`, `question`, `lang`, `cross_lingual`, `answerable`, `expected: [{doc, pages?}]`, `reference_answer`; unanswerable có `expected: []` | Thiếu split, nhóm nghĩa, phiên bản nguồn, section/span, kiểm tra nhãn và nhật ký unanswerable |
| `sopilot_eval/corpus.py` | Chỉ đọc file ngay trong `corpus/`, đuôi MD/TXT/PDF; `\f` là trang trong text; MD không có ký tự này thành một trang. Chunk chỉ có `doc/page/text`, SHA của text | Không giả định đã hỗ trợ DOCX, đệ quy thư mục hoặc offset. SHA text đơn lẻ không phân biệt hai vị trí cùng nội dung |
| `split_text` | Cửa sổ theo số ký tự/paragraph; mặc định 800 ký tự, overlap 100; có thể tách đoạn dài | Nhãn phải độc lập cấu hình chunk; số ký tự không phải số token |
| `metrics.py` | Hit theo file/trang, `is_hit` trả target đầu tiên; Recall đếm target được phủ. DCG cộng từng chunk hit, ideal theo số target | Một file MD dài có thể được chấm đúng dù lấy sai mục. Hai target cùng file/trang có thể bị nhập nhằng; duplicate chunk có thể làm nDCG vượt 1. Không dùng metric này như span-level đã hoàn thiện |
| `run.py`, `retrievers.py` | Chạy tất cả dòng trong `questions.jsonl`, chưa lọc split/group; outputs hiện chưa đủ chunk/offset để đối chiếu span. Refusal sweep là proxy score, không gọi generator | Cần xuất dev/test riêng và artifact mapping ở nhóm 04; không chạy test để chọn threshold rồi báo là kiểm chứng độc lập |
| `configs/rq1-rq3-bge-m3.yaml`, `embedders.py`, `tests/test_eval.py` | Model config chưa ghim revision; embedder/reranker cap 512 tokens; test chủ yếu smoke, file/page và fusion | Tên config không chứng minh đã thực hiện RQ2–3 answer-level; kiểm tra truncation/mapping trước research run |

Tài liệu này đặc tả dataset eval offline; không đổi schema DB, endpoint, event hoặc RBAC của ứng dụng. Các artifact dự kiến trong §8 là hợp đồng bàn giao, chưa phải file đã tạo.

## 3. Nguồn corpus, danh sách lấy và ranh giới

### 3.1. Vì sao chọn GitLab

GitLab có quy trình công khai và owner từng dùng nguồn này. [Content Websites](https://handbook.gitlab.com/handbook/about/maintenance/) xác định repo public handbook; [View page source của Onboarding](https://gitlab.com/gitlab-com/content-sites/handbook/blob/main/content/handbook/people-group/general-onboarding/_index.md) cho biết đường dẫn Markdown. Đây là thuận lợi để ghim cùng phiên bản và giữ cấu trúc heading. Công cụ web hiện chỉ trả `Loading` ở trang source GitLab: **chưa xác minh bytes Markdown hoặc immutable SHA**, không coi link source là đã thu được dữ liệu.

So sánh duy nhất: [Added Bytes Handbook](https://handbook.addedbytes.com/) có các mục onboarding, offboarding, holidays và remote work, nhỏ và có thể dễ đọc hơn; trang chủ ghi CC BY-SA 4.0 trừ ảnh/logo, và có kế thừa một phần GitLab. Chưa kiểm kê đủ ý hỏi hoặc xác minh immutable revision công khai của nguồn này. **Giữ GitLab** vì quen nguồn, có đường dẫn source rõ và nhiều mục tác nghiệp để lấy đủ câu khác nghĩa; không trộn Added Bytes vào cùng corpus để bù số lượng hay gọi đó là miền độc lập.

### 3.2. Allowlist ban đầu: 8 trang, 24 đơn vị mục

Các trang và heading dưới đây đã đọc qua nguồn chính thức ngày **19/10/2026**. Đây là danh sách lấy cụ thể; tên mục phải đối chiếu lại trên snapshot được ghim trước khi gán ID. Mỗi đơn vị lấy một vùng liên tục dưới heading, giữ trọn câu điều kiện/ngoại lệ và danh sách liên quan; không lấy đoạn rời để đáp ứng trước một câu hỏi.

| Mã / số đơn vị | URL nguồn chính thức | Mục chọn để lấy | Phạm vi loại bỏ |
|---|---|---|---|
| ONB / 3 | [GitLab Onboarding](https://handbook.gitlab.com/handbook/people-group/general-onboarding/) | Phần mở đầu trước `TaNewKi Welcome Call`; `TaNewKi Welcome Call`; `Managers of New Team Members` gồm các mục con | Không tải issue mẫu nội bộ, onboarding theo engineering/sales/support hoặc contractor |
| BUD / 2 | [Onboarding Buddies](https://handbook.gitlab.com/handbook/people-group/general-onboarding/onboarding-buddies/) | `Buddy Responsibilities`; `Managers: Who should I pick as an Onboarding Buddy?` | Không lấy org chart, ví dụ email dài và hồ sơ cá nhân |
| OFF / 2 | [Offboarding FAQ](https://handbook.gitlab.com/handbook/people-group/offboarding/faq/) | `Timing`; `Your Laptop and Account steps` | Bỏ payroll, benefits và quy định riêng quốc gia |
| AWAY / 4 | [Time Away Philosophy](https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/time-away-philosophy/) | Trong planned time away: vùng liên tục `Communication Essentials` đến hết `Communication Checklist`; `Calendar and Meeting Management`; `Knowledge Transfer and Work Continuity`; thêm `Communicating Unplanned Time Away` | Bỏ bài luận chung, dữ liệu cá nhân và job aid cần đăng nhập |
| PTO / 3 | [Time Off Types](https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/time-off-types/) | Trong `Flexible Paid Time Off (PTO)`: vùng `Overview` đến hết `PTO Protocols (Planning and Coordination)`; `How to Prepare for PTO`; trong `Sick Time`: `Reporting Procedures` | Không mở trang con quốc gia, mức quyền lợi luật định, chế độ y tế hoặc leave dài hạn |
| COM / 3 | [GitLab Communication](https://handbook.gitlab.com/handbook/communication/) | `Asynchronous communication`; `Indicating availability`; `Emergency chat` và các mục con | Bỏ toàn bộ phần còn lại, thông tin cá nhân, bài hướng dẫn tool ngoài allowlist |
| MEET / 3 | [All-Remote Meetings](https://handbook.gitlab.com/handbook/company/culture/all-remote/meetings/) | Trong `How to run an effective meeting at GitLab`: `What to do before the meeting`, `What to do during the meeting`, `What to do after the meeting` | Bỏ các danh sách mẹo/FAQ trùng và video/ảnh |
| EXP / 4 | [Global Travel and Expense Policy](https://handbook.gitlab.com/handbook/finance/expenses/) | `2. Responsibilities`; `3. General Guidelines` và mục con; `Equipment` và mục con trong non-travel expenses; `4.4 Reimbursement Payout Timelines` và mục con | Không lấy toàn bộ airfare/hotel, procurement, quà tặng, pháp lý và tài liệu Drive liên kết |

**Corpus bao phủ:** trách nhiệm/bước/thời điểm trong vòng đời nhân viên, chuẩn bị nghỉ và bàn giao, giao tiếp/họp từ xa, trách nhiệm và hoàn trả chi phí làm việc. Đây là tập con quy trình/chính sách tác nghiệp của một công ty; không phải mọi trang đều mang tên “SOP”, không đại diện SOP công nghiệp hoặc pháp luật lao động Việt Nam. Câu hỏi phải nêu GitLab và điều kiện đối tượng khi cần; giữ nguyên phân biệt US/non-US hoặc loại thực thể nếu phần đã chọn chứa chúng, không áp dụng số liệu cho mọi nhân viên.

**Giới hạn lấy:** 24 mục là đơn vị biên tập, không phải 24 trang web hay 24 chunk. Lưu 8 tài liệu canonical theo trang, kèm section allowlist; chỉ nội dung allowlist được index. Dự kiến khoảng **15.000–30.000 từ EN**, vài trăm chunk ở cấu hình ký tự hiện tại; chưa đo nên đây là dự toán. Không thêm văn bản để đạt số từ. Nếu ít hơn nhưng đủ ý hỏi độc lập thì giữ corpus nhỏ. Nếu không đủ 120 ý sau loại trùng, mở thêm mục liền kề thuộc đúng 8 trang (ưu tiên nội dung tác nghiệp), ghi lại thay đổi trước tạo/freeze test; không bù bằng paraphrase hoặc bản dịch. Nếu vẫn không đủ, báo thiếu và chưa qua gate dữ liệu, không tự hạ mốc ≥100.

Nội dung công khai nói được gì thì có thể dùng đúng điều đó. Ví dụ, trang Onboarding công khai có mô tả thời điểm mở issue; không vì câu đó trỏ vào link nội bộ mà loại cả câu công khai. Nhưng **không suy ra nội dung issue, danh sách bước trong Compass/Workday/Drive/Slack hoặc nội dung video chỉ từ tên link**. Ghi link chưa đọc được vào `excluded_dependencies`, không lấy làm evidence. Câu hỏi đòi nội dung các link đó nên loại khỏi eval lõi để giảm mơ hồ; nếu giữ làm unanswerable phải ghi rõ “thiếu trong corpus đã chọn”.

### 3.3. Giấy phép và ghim phiên bản

[GitLab Handbook Usage, External use](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook) nêu riêng nội dung handbook theo **CC BY-SA 4.0**. Không suy giấy phép nội dung từ LICENSE phần software của repo. Theo [Creative Commons BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), khi phân phối cần ghi nguồn/tác giả, link giấy phép, nêu thay đổi và tuân thủ ShareAlike cho phần chuyển thể. Gói corpus trích/chuyển định dạng và phần dữ liệu dẫn xuất từ nội dung chọn cùng CC BY-SA 4.0; không tự đổi license code toàn repo. Chỉ lấy text, bỏ logo, ảnh, dữ liệu cá nhân không cần và tài sản bên thứ ba có điều khoản riêng; trang công khai không mặc nhiên cấp phép mọi file được liên kết.

Quy trình acquisition cho bước thực thi sau này:

1. Resolve **một full commit SHA** của `gitlab-com/content-sites/handbook`, dùng SHA chung lấy toàn bộ 8 trang và các include thực sự cần. Không dùng nhánh `main`, ngày truy cập hoặc SHA “Last modified” khác nhau của từng trang như snapshot thống nhất.
2. Từ `View page source` ghi đúng path ở commit đó; lưu bytes raw, `sha256_raw`, URL nguồn người đọc, immutable source URL và `retrieved_at` UTC. Không đoán path từ URL rồi coi đã xác minh. Nếu Markdown có template/include, resolve chúng ở cùng SHA và lưu dependency hashes; nếu chưa resolve được thì không dùng vùng thiếu để gán gold.
3. Trích đúng allowlist sang canonical UTF-8, Unicode NFC, newline LF, giữ thứ tự heading/list/câu và anchor. Bỏ navigation/footer, HTML/template không hiển thị; giữ nhãn link như văn bản nhưng không nạp trang đích. Lưu `normalization_version`, `sha256_canonical`, source ranges và attribution/license notice. Chạy chunk trên đúng canonical này.
4. Lập `corpus_version` từ SHA nguồn + manifest/allowlist + hash canonical + phiên bản chuẩn hóa. Cùng source SHA nhưng chọn mục/chuẩn hóa khác là phiên bản corpus khác. Khi công bố giữ notice “GitLab Handbook, GitLab và contributors”, URL nguồn, SHA, license, ngày lấy và mô tả phần đã bỏ/chuyển định dạng.
5. Nếu source repo không đọc được ở bước tải, dùng snapshot HTML công khai có raw hash và capture time cho **toàn bộ** 8 trang, ghi `pin_mode: web-snapshot`, lưu bản nội dung tái lập; không tự nhận ghim git. Kiểm tra lại nội dung/heading/nhãn trước freeze. Ưu tiên git; không để acquisition thất bại biến thành bằng chứng nguồn giả.

Chưa điền SHA giả hoặc khẳng định đã tải corpus trong báo cáo này. Ngày kiểm tra nguồn không bảo đảm các chính sách còn giống nhau ở commit sẽ chọn.

## 4. Quy mô câu hỏi, chia tập và giới hạn mẫu

### 4.1. Đếm theo ý hỏi và theo dòng query

Một `intent_id` là một nhu cầu thông tin có cùng điều kiện và đáp án, có đúng hai biến thể ngôn ngữ. 120 ý **không có nghĩa 120 quan sát độc lập hoàn toàn**, vì còn chung policy/source; nhưng đạt mốc dự kiến ≥100 ngay cả khi không đếm bản dịch là câu hỏi mới. Nếu yêu cầu của đề cương sau này là ≥100 ý **test** riêng thì thiết kế 90 ý test chưa đáp ứng: phải tăng mẫu trước freeze, không đổi cách đếm. Handoff 01 hiện chỉ ghi ≥100 tổng câu, không ghi ≥100 test.

| Loại ý hỏi | Dev: số ý | Test: số ý | Tổng ý | Tổng dòng EN + VI |
|---|---:|---:|---:|---:|
| Answerable, một passage | 18 | 54 | 72 | 144 |
| Answerable, nhiều passage | 6 | 18 | 24 | 48 |
| Unanswerable gần chủ đề | 6 | 18 | 24 | 48 |
| **Tổng** | **30** | **90** | **120** | **240** |

| Split / hướng query→evidence | Một passage | Nhiều passage | Unanswerable | Tổng dòng |
|---|---:|---:|---:|---:|
| Dev EN→EN | 18 | 6 | 6 | 30 |
| Dev VI→EN | 18 | 6 | 6 | 30 |
| Test EN→EN | 54 | 18 | 18 | 90 |
| Test VI→EN | 54 | 18 | 18 | 90 |

Với unanswerable, mũi tên mô tả ngôn ngữ corpus được tìm chứ không nói tồn tại bằng chứng. `lang=vi`, `corpus_lang=en`, `direction=vi_to_en`; nếu cần tương thích cờ hiện tại, `cross_lingual=true` cho tất cả câu VI và ghi rõ quy ước này. Không có gold retrieval dương cho câu unanswerable; không gán Recall=0 rồi trộn vào trung bình answerable.

Một passage là một đoạn văn/list ngắn chứa đủ điều kiện và đáp án; nhiều passage cần ít nhất hai vùng bằng chứng riêng, cùng mục hoặc khác mục/trang. Không gọi là nhiều passage chỉ vì splitter cắt một đoạn ra hai chunk. Trong 24 ý nhiều passage, hướng tới 12 ý trong một trang và 12 ý liên trang, dev lần lượt 3/3, test 9/9; đây là quota cần kiểm tra khi chuẩn bị, không ép ghép những câu tổng hợp thiếu tự nhiên. Tối đa ba passage thiết yếu mỗi câu để giữ công duyệt thấp.

Phủ đủ các cụm chủ đề ở §3; tối đa 20% ý hỏi từ một trang nguồn, tránh nguồn dài EXP/COM chiếm hết. Ưu tiên câu hành động, vai trò, điều kiện/thời điểm, ngoại lệ và tổng hợp đơn giản. Không tạo hàng chục biến thể đổi một con số/tên riêng của cùng quy tắc. Bản VI phải tự nhiên và giữ đủ điều kiện, số, đơn vị, phủ định; tên tool/định danh có thể giữ EN. Corpus không được thêm bản dịch hay reference answer.

### 4.2. Split trước khi dùng model và chống rò rỉ

1. Lập `policy_family_id` theo cùng quy tắc/quy trình và nguồn lặp, không chỉ theo URL. Nối các mục diễn đạt cùng fact (ví dụ chuẩn bị PTO và thông báo vắng mặt), các paraphrase, cặp EN/VI và bản sửa câu vào cùng `leakage_group_id` bằng connected components.
2. Phân bổ nhóm nội dung vào dev/test trước khi so model; cùng fact/evidence hoặc biến thể positive/near-negative phải ở cùng phía. Câu nhiều passage chỉ lấy bằng chứng từ các family cùng split; nếu nối hai phía, chuyển cả component và cân lại quota trước freeze. Không chia ngẫu nhiên 240 dòng.
3. Kiểm tra text chuẩn hóa, lexical near-duplicate và duyệt nghĩa cả EN lẫn VI. Có thể dùng embedding để gợi ý cặp trùng, nhưng không dùng một model đánh giá làm người quyết định duy nhất. Bản VI thay đổi điều kiện phải sửa hoặc tách ý, không coi tương đương tự động.
4. Mọi cấu hình đều index **cùng toàn corpus EN**, gồm cả mục dùng đặt câu dev và test. Đây là eval query-held-out trong corpus đã biết, không phải đánh giá document-held-out. Corpus public có thể nằm trong pretraining LLM: không tuyên bố triệt tiêu contamination, cần kiểm tra output có căn cứ context được cấp.
5. Dev dùng pilot, chọn threshold và cấu hình. Khóa `split_version`, seed phân bổ, query IDs và hash trước test; không đưa test/gold test vào prompt sinh câu dev, tuning hoặc chọn model. Nếu người xây nhãn cũng là người chạy model, ghi rõ không có test steward độc lập.
6. Sửa gold sau test chỉ vì lỗi chú giải có log trước/sau/lý do/người duyệt; tăng dataset version, chạy lại **mọi** điều kiện bị ảnh hưởng. Không thay câu model làm sai bằng câu dễ hơn.

Báo số mẫu theo ngôn ngữ và loại câu, paired differences trên cùng query; bootstrap/CI nên gom cặp EN/VI và policy family theo nhóm 03, không bootstrap 240 dòng như độc lập. Test chỉ có 18 ý unanswerable và 18 ý nhiều passage mỗi ngôn ngữ; một lỗi làm thay đổi khoảng 5,6 điểm phần trăm trong ô đó. Không dùng tổng số dòng lớn để che khoảng bất định, không suy đại diện SOP toàn ngành hoặc hai ngôn ngữ đối xứng.

## 5. Nhãn bằng chứng ổn định và ánh xạ chunk

### 5.1. Canonical evidence là gold, chunk là sản phẩm phái sinh

| Đối tượng / trường đề xuất | Định nghĩa |
|---|---|
| `doc_id`, `source_path`, `source_commit`, `corpus_version` | ID trang logic ổn định và phiên bản cụ thể; đổi source path có bảng alias, không tự gán lại ID cho nguồn khác |
| `section_id`, `heading_path`, `anchor`, `section_sha` | ID mục trong corpus version, cây heading và hash text; anchor dùng để mở nguồn, không tự nó bảo đảm bất biến |
| `span_id`, `doc_id`, `section_id`, `start_char`, `end_char`, `quote_sha`, `quote` | Offset Unicode code point 0-based, end-exclusive trên toàn canonical document; quote là text EN tối thiểu đủ hỗ trợ claim, gồm điều kiện/ngoại lệ thiết yếu. Không dùng byte offset, số dòng Markdown web hoặc số thứ tự chunk làm gold |
| `required_claims`, `evidence_sets` | Claim/đáp án ngắn theo điều kiện. Mỗi evidence set là một danh sách span cần **đồng thời** (AND); các set là phương án đủ bằng chứng thay thế (OR), do người duyệt xác nhận |
| `chunk_id`, `chunking_version`, `doc_id`, `source_intervals`, `text_sha` | ID gồm corpus version + doc/location + splitter/config hash; mapping từ đoạn text chunk về canonical. Chunk trùng text ở hai chỗ vẫn có ID khác |
| `annotation_status`, `reviewer_id`, `reviewed_at`, `label_version` | Dùng `draft`, `reviewed`, `adjudicated`, `excluded` cho nhãn (không phải trạng thái ticket); chỉ nhãn đã duyệt được vào bộ khóa |

Ví dụ cấu trúc quan hệ, **không phải câu hỏi/nhãn thật**: `evidence_sets=[[s1,s2],[s3]]` nghĩa là cần s1+s2, hoặc chỉ s3 nếu s3 độc lập chứa đủ nội dung tương đương. Không chấm trúng s1 là tìm đủ đáp án. Reference EN và VI cùng dựa trên bộ claims/evidence này, không dựa trên câu trả lời của model đang được chấm.

Khi chuẩn hóa hoặc source đổi, ID span cũ vẫn chỉ phiên bản cũ; tạo mapping/review mới, không tự dịch offset rồi coi nhãn còn đúng. Giữ quote hash để fail khi offset trỏ sai. Không đưa các đoạn giải thích của annotator hoặc reference vào index.

### 5.2. Quy tắc ánh xạ và tính tìm đủ

- Splitter cần xuất offset hoặc mapping đoạn vào canonical; code hiện tại strip/join/overlap text nên không khôi phục bằng tìm chuỗi đầu tiên nếu quote lặp. Heading context thêm vào chunk phải có mapping riêng; metadata tự thêm không được tạo evidence mới.
- Với top-k, lấy hợp các interval nguồn **thực sự có trong text được truy xuất**. Một span được phủ khi toàn bộ nội dung thiết yếu của span nằm trong hợp interval, bỏ qua khác biệt whitespace đã quy định. Có thể hai chunk liền nhau cùng phủ một span; không cho điểm trọn chỉ vì chạm vài ký tự. Chunk overlap phủ cùng span chỉ đếm một lần.
- Với mỗi evidence set, `evidence_recall@k = số span được phủ / số span cần`; nếu có nhiều set thay thế, lấy max của từng set, không trộn nửa set này với nửa set kia. `complete_evidence@k=1` khi có ít nhất một set phủ đủ. Báo cả chỉ số này và hit có ít nhất một span; với nhiều passage, hit không thể thay complete.
- Đây là relevance đủ bằng chứng, không phải phán quyết mọi đoạn cùng chủ đề đều liên quan. `hard_negative_span_ids` ghi các mục rất gần nghĩa nhưng sai điều kiện/đối tượng hoặc thiếu claim; không biến chúng thành positive vì retriever xếp cao. Khi thấy nguồn tương đương hợp lệ bị thiếu, reviewer bổ sung alternative set qua quy trình versioned cho mọi cấu hình.
- Trước research run, mọi gold span phải resolve đúng canonical và có thể được phủ từ toàn bộ chunk index. Sau tokenizer/context truncation, đo lại phần evidence còn nhìn thấy ở embed/rerank/generator; ghi mất bằng chứng ở bước nào. Không lặng lẽ loại câu khó hoặc thay gold theo chunking giúp một model.

**Tương thích harness:** có thể xuất `expected` file/page để smoke, giữ tên file flat vì loader chưa đọc đệ quy. Các cột nhóm/split bổ sung đơn thuần chưa làm scorer hiện tại hiểu span. Không giả lập mỗi span thành một “page” hoặc một file bé để có điểm đẹp; cách đó đổi context retrieval. Nhóm 04 cần loader/adapter sidecar và scorer evidence-aware. Trước khi có mapping, file/page score chỉ là proxy ghi đúng nhãn proxy; không công bố như kết quả chính của bộ gold này. nDCG cần định nghĩa relevance/rank-depth và khử đếm lặp riêng với nhóm 03–04; không áp trực tiếp công thức hiện tại lên evidence sets.

## 6. Answerability và kiểm tra unanswerable toàn corpus

Answerable nghĩa là đủ thông tin trả lời các claim bắt buộc trong **toàn corpus phiên bản đã khóa, cùng phạm vi truy cập**. Nếu nguồn chỉ cho một phần, câu hỏi yêu cầu cả phần thiếu là unanswerable; ghi `reason=missing_required_detail` và các claim đã có để kiểm tra trả lời một phần. Các liên kết ngoài allowlist không thuộc corpus, dù internet có đáp án. Không dùng việc retriever top-k không trúng để gán unanswerable.

24 ý unanswerable gồm 12 ý thiếu chi tiết/quy trình gần chủ đề; 6 ý đổi điều kiện/đối tượng mà corpus không quy định; 6 ý đòi tổng hợp thêm một phần thông tin thiếu. Dev lần lượt 3/1/2, test 9/5/4. Không dùng câu vô nghĩa/lệch chủ đề rõ ràng, tài khoản cá nhân hay deadline “năm nay” không xác định. Câu mâu thuẫn trực tiếp với corpus mà có thể bác bỏ bằng bằng chứng **là answerable dạng sửa tiền đề**, không mặc định unanswerable. Câu mơ hồ mà hỏi lại là hợp lý nên sửa rõ hoặc loại, tránh ép vào nhãn nhị phân.

Quy trình bắt buộc cho từng ý unanswerable, áp dụng lại khi corpus đổi:

1. Viết rõ thông tin còn thiếu, các từ khóa EN/VI, đồng nghĩa và policy family; chỉ ra near-negative gần nhất, kèm lý do chúng không đủ. Cặp EN/VI phải đòi cùng chi tiết thiếu.
2. Tìm trên **toàn canonical corpus** bằng exact/keyword search, đồng nghĩa và đọc các mục liên quan; kiểm tra cả các mục khác chủ đề có thể chứa đáp án. Lưu corpus hash, search terms và candidate section IDs. Search web chỉ dùng xác minh nguồn, không bổ sung corpus âm thầm.
3. Khi công cụ sẵn sàng, dùng hợp kết quả BM25 và cả hai dense model, lấy tối đa top-10 mỗi nhánh, khử trùng rồi reviewer đọc candidate chưa xem. Đây là cách phát hiện bỏ sót nhãn, không phải chứng minh vắng đáp án vì cả model đều trượt. Nếu chưa có model, vẫn có thể chuẩn bị nhãn bằng tìm từ/đọc toàn scope; chưa freeze nhãn cuối trước bước đối chiếu candidate.
4. Người duyệt xác nhận không có đủ evidence set ở bất kỳ mục hợp lệ nào. Lưu `unanswerable_audit` gồm reason, candidates đã kiểm, phạm vi toàn corpus, người/ngày và kết luận. Nếu có đáp án, chuyển positive và thêm span hoặc thay câu trước freeze, rồi cân lại quota theo nhóm; không giữ nhãn âm để đúng tỷ lệ.
5. Duyệt lại **toàn bộ 24 ý âm** độc lập nếu có reviewer thứ hai; có bất đồng thì đưa `excluded/pending`, giải quyết bằng nguồn chứ không bỏ phiếu cho output LLM. Một người tự rà lại sau khoảng nghỉ phải ghi là tự duyệt, không gọi đồng thuận hai người.

Không thực hiện candidate mining để chọn các câu chỉ một model thất bại rồi báo test “trung lập”. Tập câu chọn trước; pool model ở bước 3 chỉ tìm lỗi gold. Nếu phát hiện lỗi qua kết quả test thì áp dụng quy trình sửa nhãn có version ở §4.2.

## 7. Tập con answer-level và công duyệt

### 7.1. Quy mô cố định trước generation

Chọn có phân tầng và seed công khai **32 ý = 64 dòng** từ 120 ý, giữ nguyên split và cặp EN/VI. Chọn theo loại câu/chủ đề trước khi xem output hoặc model thắng; phủ các cụm chủ đề, không chỉ câu dễ hoặc rerank làm tốt.

| Answer subset | Một passage | Nhiều passage | Unanswerable | Tổng ý / dòng |
|---|---:|---:|---:|---:|
| Dev | 4 | 2 | 2 | 8 / 16 |
| Test | 14 | 4 | 6 | 24 / 48 |
| **Tổng** | **18** | **6** | **8** | **32 / 64** |

Chạy một retriever/dense baseline và candidate pool cố định do nhóm 03 chọn, rerank tắt/bật, **cùng generator, prompt, context budget và chính sách citation**. Hai điều kiện × 64 query = tối đa **128 answer outputs** (32 dev, 96 test) cần đọc; không nhân thêm hai embedding cho answer-level RQ5. Trả lời theo ngôn ngữ query. Lưu nguyên input context, thứ tự chunk, output, citations và cả refusal tự phát của generator; context không được chứa reference answer.

RQ3 dùng gate cố định trước generation: có thể tái dùng output của cùng context/prompt ở trên cho các câu được gate cho qua; câu bị gate chặn là refusal xác định. So với không gate trên **cùng query**, không gọi API lại cho từng threshold. Tái dùng chỉ hợp lệ nếu gate không đổi prompt/context/generator. Nếu muốn đánh giá prompt refusal khác, đó là điều kiện generation khác, cần thêm output và công duyệt; không suy từ score-only. Khóa threshold trên dev theo nhóm 03; test chỉ áp dụng threshold đã khóa. Bộ dev 60 dòng có thể hiệu chỉnh score proxy, nhưng chỉ 16 dòng dev có nhãn output nên không đủ để tuyên bố threshold đã tối ưu rủi ro answer thực trên mọi câu.

Tập test answer-level chỉ 24 ý, trong đó 6 ý âm và 4 ý nhiều passage cho mỗi ngôn ngữ; một lỗi đổi tỷ lệ refusal ở nhóm âm khoảng 16,7 điểm phần trăm. Báo exploratory với mẫu số, bất định và ví dụ lỗi; không tuyên bố đạt ngưỡng chất lượng sản phẩm chắc chắn từ mẫu này. Nếu cần kết luận chặt hơn, mở subset theo cùng rule trước test; ưu tiên mở công duyệt thay vì thêm model.

### 7.2. Checklist reviewer ngắn

**Duyệt dataset (mỗi ý và cả hai ngôn ngữ):**

1. Câu rõ điều kiện, cần thông tin tác nghiệp; EN/VI cùng nghĩa và không gợi đáp án; đúng split/family, không trùng fact với phía kia.
2. Nhãn answerability đúng toàn corpus; câu dương có đủ span EN và ngoại lệ; câu âm có audit, không chỉ retrieval miss.
3. Reference/required claims EN và VI được nguồn hỗ trợ, số/đơn vị/đối tượng không đổi; quote/offset/hash resolve được. Ghi reviewer, ngày, quyết định và lý do sửa.

**Duyệt output (ẩn tên cấu hình, tráo thứ tự, giữ ID để ghép cặp):**

1. `decision`: answered / refused / partial / invalid; với câu dương, đã trả lời đủ claim và đúng điều kiện chưa? `correctness`: 0 sai, 1 đúng một phần, 2 đủ/đúng; câu âm không chấm correctness bằng chuỗi reference rỗng.
2. `faithfulness`: từng claim thực tế có được **context thực sự cấp cho generator** hỗ trợ không? Ghi số claim được hỗ trợ/tổng claim và claim lỗi; đáp án đúng nhờ kiến thức ngoài context vẫn không grounded.
3. `citation`: link/ID mở đúng doc/mục/span không; mỗi citation có hỗ trợ claim gắn với nó không; bao nhiêu claim cần dẫn đã có citation hợp lệ? Lưu counts để tính precision/completeness; mẫu số 0 ghi N/A. Câu có claim cần dẫn nhưng không dẫn: completeness 0.
4. `refusal`: câu dương bị từ chối là false refusal; câu âm đưa đáp án quyết đoán cho phần thiếu là false acceptance. Trả lời phần có căn cứ và nêu rõ thiếu phần còn lại ghi `partial`, nhóm 03 phải định rule đếm trước test; không coi mọi partial là refusal đúng.
5. Ngôn ngữ output đúng yêu cầu, VI tự nhiên/hiểu được; dẫn chứng vẫn EN là hợp lệ. Ghi lỗi chính ngắn: retrieval thiếu, context/truncation mất, tổng hợp sai, bỏ điều kiện, citation sai hoặc refusal sai.

Giữ correctness theo gold, faithfulness theo context và citation theo claim tách biệt. Reviewer có thể dùng bản claims thay vì một đáp án mẫu dài để giảm công so văn phong. LLM chỉ hỗ trợ nháp/candidate/dịch query; reviewer phải mở nguồn, không gọi LLM judge là gold.

### 7.3. Khối lượng dự toán và cơ chế bất đồng

| Việc | Dự toán công người (chưa đo) |
|---|---:|
| Thu hẹp/đọc 24 mục, kiểm tra extraction và manifest | 3–5 giờ |
| Soạn/duyệt 120 ý, claims/spans và audit âm, trung bình 5–8 phút/ý | 10–16 giờ |
| Soạn/duyệt 120 biến thể VI, trung bình 1–2 phút/ý | 2–4 giờ |
| Đọc 128 outputs, trung bình 3–5 phút/output | 6,4–10,7 giờ |
| Reviewer thứ hai: toàn bộ 24 ý âm + 24 ý dương chọn phân tầng; 32 outputs gồm đủ ngôn ngữ/loại | 4–7 giờ |
| **Tổng dự kiến** | **Khoảng 26–43 giờ công**, chưa gồm thời gian sửa bất đồng/chạy inference |

Đây là tổng person-hours, không hứa deadline; pilot 12 ý từ dev (6 một passage, 3 nhiều passage, 3 âm, đủ EN/VI) và 8 outputs dev để thay dự toán bằng thời gian thực. Reviewer chính đọc 100% dữ liệu và output; reviewer thứ hai kiểm tra độc lập các phần trên, toàn bộ trường hợp chưa rõ và lỗi citation/claim nghiêm trọng. Với bất đồng: lưu hai nhãn ban đầu, span/claim gây tranh luận và quyết định adjudication; chưa giải quyết thì không vào gold khóa. Báo agreement trên tập được chấm đôi, không suy thành toàn bộ dataset.

Nếu chỉ có owner duyệt, vẫn làm được theo hai lượt cách nhau, ẩn tên model; ghi rõ `single_reviewer/self_review` và thiếu kiểm tra độc lập. Không tự giả định có thêm người hoặc thêm lịch hỏi owner. Không giảm bằng cách giữ nguyên nhãn LLM hoặc bỏ đọc câu âm. Khi công vượt dự toán, ưu tiên giữ 120 ý retrieval và subset 32 ý đã định, cắt model/config phụ trước; mọi thay đổi subset sau freeze phải có lý do/version và không dựa trên kết quả tốt/xấu.

## 8. Hợp đồng bàn giao cho nhóm 03–04 và các điểm cần resolve

Các đường dẫn sau là **artifact dự kiến cho lần triển khai được phép sau này**, không tạo trong session này. Nhóm 04 có thể chọn tên file tương đương, nhưng phải giữ semantics và hash liên kết.

| Artifact dự kiến dưới `eval/datasets/gitlab-sop-en-v1/` | Trường/nghĩa tối thiểu |
|---|---|
| `manifest.json` và raw/canonical corpus | Source repo/commit hoặc web-snapshot, 8 URL/path, allowlist, raw/canonical hashes, normalizer, license/attribution, excluded dependencies, corpus version; `corpus/` chỉ chứa text được index, không gold |
| `sections.jsonl`, `evidence.jsonl` | doc/section IDs và heading paths, canonical ranges; span IDs, quotes/hashes, required claims và alternative evidence sets |
| `questions.master.jsonl` | `id`, `intent_id`, `policy_family_id`, `leakage_group_id`, `split`, `question`, `lang`, `corpus_lang`, `direction`, `cross_lingual`, `answerable`, `evidence_sets`, `reference_answer`, `type`, `review_status`, `label_version` |
| `review.jsonl` | Người/ngày/provenance nháp, audit âm toàn corpus, candidate IDs, quyết định duyệt/sửa/adjudicate; giữ tách khỏi model input |
| `dev/questions.jsonl`, `test/questions.jsonl` hoặc exports tương đương | 60/180 dòng đúng nhóm; export cho CLI hiện tại cần cách resolve cùng corpus bằng adapter. Không giả định `run.py` đã dùng split field hoặc tự dùng corpus thư mục cha |
| `chunk-map.jsonl` | Corpus/chunking version, ID/vị trí/hash chunk, source intervals, truncation/effective text và mapping span, đầy đủ ở run artifact |
| `answer-subset.json`, `answer-review.jsonl` | 32 intent IDs chọn trước/seed/split; run/output IDs, prompt/context/model version, claim/citation counts, nhãn rubric, reviewer và bất đồng |

Không đưa gold test vào payload generator hoặc index; khi dùng API chỉ gửi query/context cần thiết. Dataset manifest hash + label version + split hash + subset hash phải đi cùng mọi run. Hai embedding dùng **cùng corpus/chunks/gold**, khác model không được âm thầm đổi chunking.

| Điểm đối chiếu | Mặc định nhóm 02 bàn giao | Bên resolve / ảnh hưởng |
|---|---|---|
| Relevance của nhóm 03 có thể đang dùng doc/page/chunk | Gold theo span, AND/OR evidence sets; Recall và complete-evidence có semantics §5 | Nhóm 03–04 chốt scorer; file/page hiện tại chỉ proxy. Bất đồng này phải giải trước test, không đổi nhãn theo metric tiện có |
| k, pool, token budget và cap 512 | Nhóm 02 không chốt model/k; mapping phải giữ vị trí sau chuẩn hóa và ghi mất bằng chứng do truncation | Nhóm 03 chọn, nhóm 04 xuất artifacts; chưa bảo đảm mọi span nhìn thấy trong context |
| ≥100 câu | 120 ý tổng/240 dòng, test 90 ý | Nếu đề cương đòi ≥100 test độc lập phải mở mẫu trước freeze; không tăng n bằng bản dịch |
| RQ2 subset/rerank CPU | Gold retrieval toàn 240 dòng; answer subset cố định 64 dòng, rerank off/on | Nếu nhóm 03 cần giảm retrieval rerank theo pilot thì preselect subset phân tầng, báo đúng số mẫu; không thu hẹp sau xem test |
| RQ3 partial và gate score | Lưu answered/refused/partial riêng, không gọi score sweep là answer quality | Nhóm 03 chốt rule false acceptance/false refusal trước test; nhóm 04 giữ riêng dense/RRF/rerank/gate scores và output |
| Provider và model RQ5 | Một generator cố định cho subset; hai embedding retrieval, chưa xác minh quota API | Nhóm 03–05 kiểm tra khi chạy; hết quota thì checkpoint, không trộn provider/model trong cùng điều kiện |
| Quyền/tenant | Corpus lõi public EN cùng phạm vi truy cập; không trộn unauthorized với câu corpus không có đáp án | Isolation là test hệ thống riêng nhóm 04/06 dù RQ4 ngoài lõi |
| Trạng thái phê duyệt và dữ liệu | Báo cáo hoàn tất thiết kế; chưa có gold, run hay sign-off nghiên cứu | Không sửa PRD/ADR/PLAN để phản ánh một nghiệm thu chưa diễn ra |

Đây là giả định/hợp đồng để hai nhóm làm song song, không phải xác nhận họ đã đồng ý. Không đợi nhóm 03–04 để chốt khuyến nghị nguồn và công duyệt; trước khi chạy test cần một lần đối chiếu các điểm trên bằng tài liệu/version đã khóa.

## 9. Các bước thực hiện cụ thể và phần cần người duyệt

| Bước | Việc / đầu ra | Gate hoàn thành |
|---|---|---|
| 1 | Thu đúng 8 trang/24 mục theo §3, resolve SHA, canonical và manifest | Nguồn đọc được, quyền dùng/attribution rõ, text gốc EN không thiếu điều kiện/include; thống kê từ/mục thật |
| 2 | Reviewer đọc inventory, xác định policy family và source overlap; dựng span/claim pilot 12 ý dev và hai biến thể | Câu hỏi có ích, quote/offset đúng; pilot công người và mapping không lẫn doc/page với evidence |
| 3 | Chia family dev/test, soạn đủ 120 ý/240 dòng theo bảng, kiểm tra trùng và toàn corpus cho câu âm | 30/90 ý, EN/VI cân bằng, không cặp nghĩa/fact qua split, đủ audit và người duyệt; thiếu thì chưa gọi gold |
| 4 | Nhóm 04 tạo export/mapping/scorer; đối chiếu nhóm 03 về evidence, partial, k/context | Tất cả span resolve/cover được, duplicate không cộng thưởng, không dùng test chọn ngưỡng; phép đo đúng nhãn |
| 5 | Chọn 32 ý answer subset trước run, freeze corpus/labels/split/subset cùng hash | Có review log, adjudication xong, hai bên dùng cùng phiên bản; chưa có output test để chọn mẫu |
| 6 | Chạy dev rồi khóa config/gate; chạy test và generation subset theo nhóm 03–05; người đọc outputs theo §7 | 128 outputs tối đa cho hai điều kiện, hoặc log rõ failure/quota; không đổi model âm thầm; số mẫu/CI và giới hạn được báo |

**Phần thực sự cần người:** xác nhận span đủ chứng minh và điều kiện đúng; kiểm tra VI tương đương EN; xác minh 24 ý không có đủ đáp án trên toàn corpus; xử lý bất đồng; đọc correctness/faithfulness/citation/refusal của 128 outputs. Có thể tự động hóa tải/chuẩn hóa/hash, dò trùng, ánh xạ, quota và xuất bảng; không dùng chúng thay phán quyết nội dung. Thiết kế này không cần owner chọn lại nguồn, deadline hay phần cứng để bắt đầu chuẩn bị.

## 10. Bằng chứng kiểm tra và giới hạn của session

- Đã đọc schema/call path trong `eval/`, xác minh smoke 3 tài liệu/9 câu, ghi rõ những trường/chức năng chưa có; chưa chạy benchmark, model hoặc API generation.
- Đã tra cứu trực tiếp các nguồn chính thức liên kết tại §3 (8 trang, Handbook Usage, Content Websites, Creative Commons; Added Bytes để đối chiếu ngắn). Link source GitLab chỉ hiện `Loading`, nên acquisition/immutable revision vẫn là gate thực thi, không là bằng chứng đã có corpus.
- Chỉ ghi file HANDOFF nhóm 02 này; không thay đổi code hoặc tài liệu tiến độ, không đọc `.env`, không commit/push. Do thay đổi chỉ là báo cáo, kiểm tra phù hợp là nội dung, frontmatter, số lượng/phân bố và diff file đích; không chạy full stack/build/test suite vốn không xác minh thiết kế dataset.
- Kết luận cuối: **GitLab, 8 trang/24 mục EN, 120 ý/240 query EN–VI, dev/test 30/90 ý, answer subset 32 ý/64 query**. Triển khai theo gate ở §9; chưa có cơ sở gọi dataset là gold hoặc kết luận phương pháp/model nào thắng trước khi có dữ liệu và duyệt thật.

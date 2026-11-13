---
id: RESEARCH-01-scope-and-rqs
title: "Nhóm 1: Phạm vi, câu hỏi và tiêu chí kết luận nghiên cứu SOPilot"
status: final
type: research
scope: research
created: 2026-10-18
updated: 2026-10-19
author: "Owner"
refs:
  - docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/execution/initiatives/v2-sopilot-mvp/PLAN.md
  - docs/04-reports/AUDIT-retrieval-stack-research-2026-10-18.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
  - temp/De_cuong_NCKH_sinh_vien_2026.md
---

# Phạm vi và câu hỏi nghiên cứu SOPilot

## 1. Kết luận định hướng và trạng thái bàn giao

**Phạm vi ngôn ngữ owner làm rõ ngày 19/10/2026:** corpus chỉ nạp SOP tiếng Anh gốc; bộ eval có câu hỏi tiếng Anh và tiếng Việt, tương ứng EN→EN và VI→EN. Không cần dịch corpus sang tiếng Việt. Nghiên cứu khả năng tìm bằng chứng bằng dense, BM25 và hybrid RRF; đánh giá tác động của một reranker và ngưỡng từ chối lên một tập con hỏi đáp có người duyệt. So sánh embedding là câu hỏi phụ có giới hạn để xác định tính phụ thuộc của kết luận hybrid vào dense model. CPU là ràng buộc đo tài nguyên, không phải lý do bỏ phép so sánh hoặc mặc định model thắng.

Giữ RQ1–RQ3 theo PRD làm lõi. RQ1b là phân tích bắt buộc của RQ1 nếu giữ cam kết cross-lingual; RQ5 là phụ, có thể rút xuống một baseline và một challenger. RQ4 về overhead tenant là mở rộng kỹ thuật; kiểm tra không lộ dữ liệu vẫn bắt buộc cho hệ thống dù không thực hiện RQ4. Không chốt model, provider, shortlist cuối hoặc ma trận thực nghiệm chi tiết trong tài liệu này.

**Cập nhật owner ngày 19/10/2026:** đã đồng ý QĐ-01 và QĐ-02, gồm RQ1–3 có answer-level subset, RQ5 bắt đầu với hai embedding và RQ4 ngoài lõi. Owner có máy RAM 32 GB, không GPU, muốn kết hợp local với API LLM miễn phí và ưu tiên hoàn thành nhanh. Nguồn corpus đang được đề xuất ở §8.4, chưa được owner chọn. Chi tiết generator và tình trạng duyệt đề cương được owner yêu cầu bỏ qua trong vòng hỏi đáp này; không coi đó là đã xác minh.

Làm rõ tiếp theo của owner thay đề xuất bốn hướng và dịch corpus trước đó bằng hai hướng EN→EN, VI→EN. Tuyên bố dự kiến là **hỗ trợ truy vấn VI/EN trên tài liệu EN**, trong giới hạn kết quả thực đo; chưa đánh giá corpus VI hoặc cross-lingual hai chiều. PRD và handoff tổng còn phạm vi rộng hơn; nhật ký này ghi quyết định cho nghiên cứu hiện tại, chưa sửa các tài liệu thượng nguồn.

`status: final` chỉ kết thúc tài liệu khảo sát nhóm 1; không chứng nhận đã khóa toàn bộ phạm vi, hoàn tất nhóm thực thi, nghiệm thu chất lượng hay phê duyệt PRD/ADR/PLAN. Nhật ký quyết định ở §8.3 phân biệt phần đã chốt và đề xuất còn lại. Chưa sửa PRD/ADR/PLAN, chưa tạo ticket hoặc triển khai code.

## 2. Căn cứ, kế thừa và khoảng trống hiện tại

### 2.1. Những gì đã đối chiếu trong workspace

| Đầu vào | Nội dung kế thừa / kết quả kiểm tra | Hệ quả cho nhóm 1 |
|---|---|---|
| `AGENTS.md`, `docs/README.md` | Kiểm tra Git trước; giữ công việc có sẵn; tài liệu tiến độ chỉ ở `docs/03-plans/`; report dùng `draft/final` | Chỉ thêm file HANDOFF này; không đọc `.env`, không commit/push, không suy trạng thái từ scaffold |
| PRD-V2 §4, §6–8 | `draft`, cập nhật 17/10; RQ1–3 chính, RQ4 phụ, RQ5 đề xuất; CPU không GPU; VI/EN và cross-lingual | Các mục tiêu chất lượng vẫn là mục tiêu, không phải số đo hay phê duyệt |
| ADR-004/005/006, PLAN-V2 | Đều còn `draft`; PLAN ghi 0 ticket `done`, 1 `review` | Kiến trúc hai service và workspace là đích đề xuất, không đại diện runtime hiện tại |
| Handoff workstreams 18/10 | Ưu tiên nghiên cứu/báo cáo trước deploy; mở lại lựa chọn embedding | Có quyền khảo sát và viết bàn giao; không chốt stack từ báo cáo nguồn |
| Audit retrieval 18/10 | Khuyến nghị có điều kiện; BGE-M3 chỉ được xét như dense khi lexical là BM25 riêng | Không tính sparse/ColBERT chưa dùng thành đóng góp; chưa có model thắng trên SOP |
| Đề cương tại `temp/De_cuong_NCKH_sinh_vien_2026.md` | Hệ thống tích hợp, dữ liệu, công cụ và thực nghiệm; dự kiến tối thiểu 100 câu hỏi, cho phép điều chỉnh; tách hiệu chỉnh/đánh giá | Không tự hạ yêu cầu dữ liệu; không tuyên bố thuật toán mới. Tình trạng nộp/duyệt của đề cương chưa có bằng chứng tại lần đọc này |
| `eval/README.md`, config, smoke JSONL, `metrics.py`, `run.py`, `embedders.py` | Harness retrieval-only; corpus smoke 3 tài liệu, 9 câu; chưa có EN→VI trong smoke; mọi SentenceTransformer bị giới hạn tối đa 512 tokens; config nghiên cứu chưa ghim revision | Smoke chỉ kiểm tra công cụ. Chưa có bộ nhãn người duyệt hoặc kết quả đủ để trả lời RQ; EN→VI không còn là điều kiện thiếu theo scope owner làm rõ ngày 19/10 |
| Runtime `chunk_repo.py`, `api/routes/chat.py`, `pipeline_orchestrator.py` | `bm25_search` dùng `ts_rank`; chat khởi tạo `PipelineOrchestrator()`; reranker tùy thuộc dependency/settings trong orchestrator | Không gọi eval BM25 là đã đại diện runtime; chưa thể lấy cấu hình có rerank làm bằng chứng chat mặc định có rerank |

Đã kiểm tra danh sách `docs/04-reports/HANDOFF-research*`: trước khi viết chỉ có handoff chung, chưa có đầu ra nhóm 1–6 để kế thừa và file đích chưa tồn tại. Không thấy tài liệu phê duyệt mới hơn trong bộ PRD/ADR/PLAN và các report đã kiểm tra. Điều này không thay thế xác nhận của owner về quyết định ở ngoài repo.

Git đang ở `fix/auth-google-roster-admission`, có nhiều thay đổi staged/unstaged/untracked từ trước. Tài liệu này không nhận các thay đổi đó là sản phẩm của session. Không chuyển nhánh hoặc sửa code để phục vụ khảo sát.

### 2.2. Quy tắc đọc bằng chứng

- **Đã xác minh:** nội dung và trạng thái trên đĩa, cùng các nguồn gốc ở §10.
- **Kế thừa định hướng:** nghiên cứu trước deploy, CPU không GPU, không mặc định model tốt nhất; không đồng nghĩa toàn bộ V2 đã approved.
- **Giả thuyết:** hybrid, rerank hoặc embedding khác có thể cải thiện; phải cho phép kết quả không ủng hộ.
- **Nguồn lực owner xác nhận ngày 19/10:** máy RAM tổng 32 GB, không GPU; kết hợp local và API LLM miễn phí; ưu tiên triển khai nhanh, không yêu cầu khai chi tiết ngân sách giờ chạy. RAM trống, CPU cụ thể, corpus thực, reviewer và generator cuối chưa được xác minh. Không có số latency/chất lượng dự án được đo.

## 3. Vấn đề nghiên cứu, đối tượng và đóng góp

### 3.1. Vấn đề cần giải quyết

Người dùng hỏi một quy trình hoặc chính sách bằng VI/EN; bằng chứng nằm trong tài liệu được phép truy cập, có thể khác ngôn ngữ với câu hỏi. Khớp từ khóa có thể bỏ sót diễn đạt khác; dense có thể tìm đoạn gần nghĩa nhưng sai điều kiện, con số hoặc chính sách. Thêm rerank có thể cải thiện thứ tự nhưng tốn CPU. Tăng ngưỡng từ chối có thể giảm lượt trả lời thiếu căn cứ và đồng thời chặn những câu có đáp án. Đây là các **cơ chế lỗi cần kiểm chứng**, không phải tần suất lỗi đã biết của SOPilot.

Câu hỏi bao trùm: **Với câu hỏi VI/EN trên corpus SOP tiếng Anh có nhãn bằng chứng được kiểm tra, cấu hình truy xuất và từ chối nào cân bằng được việc tìm đúng bằng chứng, trả lời có căn cứ và tài nguyên CPU?** Không đặt mục tiêu chứng minh hybrid luôn hơn dense, hay tìm model tốt nhất cho mọi loại tài liệu.

### 3.2. Đơn vị và giới hạn đối tượng

- Corpus: SOP, hướng dẫn tác nghiệp và chính sách tiếng Anh gốc dạng văn bản được phép sử dụng; PDF có lớp text, DOCX, MD/TXT theo khả năng trích xuất được kiểm tra. Không dịch corpus sang VI. OCR, ảnh/bảng phức tạp là ngoài phạm vi tối thiểu.
- Tác vụ chính: hỏi độc lập một lượt, cần bằng chứng trong corpus hiện hành của workspace. Câu hỏi nối tiếp hội thoại là kiểm chứng tính năng phụ, không đưa vào so sánh lõi vì thêm biến viết lại query.
- Hai hướng: EN→EN và VI→EN; mũi tên từ ngôn ngữ câu hỏi tới ngôn ngữ bằng chứng. Trả lời theo ngôn ngữ câu hỏi. VI→EN kiểm tra truy xuất chéo ngôn ngữ một chiều; bộ eval đủ hai hướng cho phép kết luận về truy vấn VI/EN trên corpus EN theo kết quả đo. VI→VI và EN→VI ngoài phạm vi nghiên cứu hiện tại.
- Định nghĩa answerable: có **đủ** bằng chứng để trả lời trong corpus/phiên bản và phạm vi truy cập đã cố định. Câu có đáp án ở workspace khác vẫn không answerable cho workspace đang hỏi; quyền truy cập xử lý bằng bộ test riêng.
- Với mỗi câu hỏi, người duyệt cần ghi rõ đoạn chứa đáp án nằm trong tài liệu nào, phiên bản nào, trang hoặc mục nào; sau đó xác định đoạn nhỏ do hệ thống chia ra (chunk) chứa bằng chứng đó. Ví dụ: câu “Xin nghỉ phải báo trước bao lâu?” có đáp án ở trang 3 của “Quy định nghỉ phép”, bản v2. Tìm đúng file nhưng chỉ lấy đoạn nói về số ngày phép năm vẫn chưa đủ để trả lời. Nhóm 2 sẽ chốt cách tính tìm đúng bằng chứng, kể cả khi cần nhiều đoạn; không chỉ lưu số thứ tự chunk vì số này có thể đổi khi chia lại tài liệu.
- Bộ câu hỏi chủ yếu gồm câu có đáp án trong một đoạn và câu gần chủ đề nhưng tài liệu không có đáp án để kiểm tra khả năng từ chối. Ví dụ: tài liệu ghi “12 ngày phép/năm” nên trả lời được câu hỏi về số ngày phép, nhưng phải từ chối câu “Phép chưa dùng đổi được bao nhiêu tiền?” nếu tài liệu không quy định. Thêm một nhóm nhỏ câu cần ghép nhiều đoạn, như kết hợp quy định nghỉ phép và nghỉ không lương để trả lời “Hết phép thì xin nghỉ thế nào?”. Trước mắt chỉ đánh giá tiếng Việt/Anh và khả năng tổng hợp đơn giản, chưa xét bài toán suy luận phức tạp nhiều bước hoặc các ngôn ngữ khác.

### 3.3. Đóng góp dự kiến và điều kiện để được tuyên bố

| Đóng góp | Bằng chứng tối thiểu cần có | Giới hạn cách viết |
|---|---|---|
| Corpus SOP EN và câu hỏi VI/EN có nhãn khả năng trả lời và bằng chứng | Nguồn/giấy phép, manifest phiên bản, ngôn ngữ query, người duyệt, split và xử lý bất đồng | Chỉ gọi bộ đánh giá quy mô dự án; không gọi benchmark đại diện toàn ngành hoặc corpus VI. Nếu không thể công bố corpus, nói rõ mức tái lập bị hạn chế |
| Phân tích thực nghiệm hybrid/rerank/refusal có kiểm soát trên CPU | Cấu hình cố định, dev/test riêng, paired outputs, bất định, phân tích lỗi và tài nguyên thực đo | Đóng góp thực nghiệm và đặc trưng đánh đổi; không tuyên bố đề xuất RRF, BM25 hay kiến trúc model mới |
| Hệ thống minh họa và gói tái lập | Pipeline cuối nối thật, citation kiểm tra được, refusal, test tenant và artifacts đủ chạy lại | Tích hợp hệ thống phục vụ nghiên cứu; không suy chất lượng từ demo chạy hoặc từ kết quả retrieval-only |

Giá trị khoa học đến từ câu hỏi có thể bác bỏ, dữ liệu kiểm tra được và phân tích nhân tố; ghép các công cụ sẵn có mà không ablation/bằng chứng chưa đủ cho đóng góp thực nghiệm.

## 4. RQ, giả thuyết và tiêu chí kết luận

Giữ mã RQ của PRD để nhóm sau đối chiếu. Bảng dưới là cách vận hành hóa đề xuất, chưa sửa câu chữ/độ ưu tiên chính thức trong PRD.

| RQ / ưu tiên đề xuất | Câu hỏi và giả thuyết có thể kiểm chứng | So sánh / bằng chứng cần có | Khi nào có thể kết luận |
|---|---|---|---|
| **RQ1 — chính** | Trên cùng corpus/chunks và dense model cố định, hybrid RRF thay đổi khả năng lấy bằng chứng so với dense và BM25 thế nào? **H1:** cải thiện Recall@5 so với từng nhánh riêng nhờ tính bổ sung | Dense, BM25, hybrid; cùng câu và ngân sách output; Recall@5 theo evidence targets, candidate recall, ranking metric đã kiểm tra, chi phí CPU | Báo chênh lệch ghép cặp với từng baseline, khoảng tin cậy và số câu thắng/hòa/thua. Chỉ nói hỗ trợ H1 khi kết quả đủ rõ; thắng BM25 nhưng thua dense không được gọi hybrid thắng cả hai |
| **RQ1b — phân tích phụ bắt buộc theo ngôn ngữ query** | Khác biệt RQ1 thay đổi thế nào giữa EN→EN và VI→EN? **H1b:** dense/hybrid có lợi thế tương đối so với lexical ở VI→EN; mức chênh lệch so với EN→EN cần đo | Cùng corpus EN; báo riêng số mẫu, kết quả và bất định cho query EN và VI. Nhóm câu hỏi cùng nghĩa phải được nhận diện để phân tích ghép cặp và xử lý phụ thuộc | Không dùng mean toàn bộ che nhóm VI yếu. Nếu mẫu quá ít, báo exploratory/chưa đủ bằng chứng; BM25 không được mặc định bằng 0 vì có tên riêng, số và từ vay mượn. Không kết luận cho corpus VI hoặc cross-lingual hai chiều |
| **RQ2 — chính, đánh giá hai tầng** | Rerank thay đổi thứ tự bằng chứng, citation, faithfulness và thời gian ra sao? **H2:** cải thiện chất lượng ở đầu danh sách và có thể cải thiện câu trả lời, đổi lại latency | Một retriever/candidate pool cố định, bật/tắt cùng reranker; tầng retrieval trên tập đã định; tầng answer trên cùng tập con, generator/prompt/budget cố định | Tách kết luận ranking khỏi kết luận answer. Chỉ nhận cải thiện citation/faithfulness khi có nhãn đánh giá câu trả lời; không suy từ Recall/MRR. Nếu ranking tốt mà answer không tốt, ghi rõ H2 chỉ được hỗ trợ một phần |
| **RQ3 — chính** | Đổi ngưỡng từ chối làm thay đổi lỗi trả lời và từ chối nhầm thế nào? **H3:** có operating point trên dev giảm câu trả lời không được hỗ trợ với coverage còn hữu ích, rồi giữ được đánh đổi trên test | Cùng pipeline, ngưỡng chọn từ dev, so với luôn trả lời; nhãn answerable/unanswerable và chất lượng output; ghi coverage và lỗi theo lớp/ngôn ngữ | Khóa ngưỡng trước test. Báo cả từ chối nhầm trên câu answerable và nhận trả lời trên câu unanswerable, cùng lỗi trong các câu thực sự trả lời. Nếu chỉ chặn gần hết câu mới đạt độ an toàn, không nhận H3 đạt giá trị sử dụng |
| **RQ5 — phụ có giới hạn** | Dense model thay thế có cải thiện dense riêng và phần đóng góp vào hybrid, trong ngân sách CPU? **H5:** thứ hạng model ở dense riêng có thể khác trong hybrid; không giả định model cụ thể thắng | Ít nhất baseline và một challenger nếu đủ nguồn lực; chunks và lexical cố định; mỗi model có đường dense và hybrid; thời gian/RAM và lỗi theo hướng | Kết luận trong corpus/cấu hình đã thử; không gọi tốt nhất thị trường. Nếu chất lượng tương đương trong bất định, ưu tiên tài nguyên trong giới hạn owner chốt; không nhận tương đương thống kê chỉ vì không có khác biệt có ý nghĩa |
| **RQ4 — mở rộng tùy chọn** | Thêm RLS trên nền đã lọc ứng dụng thay đổi retrieval latency bao nhiêu? Không đặt giả thuyết về tốc độ khi chưa đo | Cùng DB/data/query/load và index, so điều kiện lọc; kiểm tra isolation trước đo | Chỉ kết luận overhead với môi trường đã đo. Chưa làm RQ4 không có nghĩa được bỏ isolation; không đưa chế độ thiếu bảo vệ lên môi trường public |

### 4.1. Tách chỉ số và tránh suy luận vượt bằng chứng

- **Retrieval:** Recall@5 tính trên các đơn vị bằng chứng nhóm 2 chốt; báo cả tìm thấy ít nhất một bằng chứng và tìm đủ bằng chứng cho câu nhiều đoạn. Nhóm 3 chốt k/pool và metric phụ; nDCG/MRR cần relevance và độ sâu xếp hạng đúng, không chỉ tên cột trong harness.
- **Citation:** tách trỏ đúng nguồn/vị trí, nguồn thực sự hỗ trợ claim (precision) và các claim cần dẫn đã có nguồn hỗ trợ (completeness). Dẫn đúng document_id không chứng minh nội dung câu trả lời đúng.
- **Faithfulness:** claim có được ngữ cảnh cung cấp hỗ trợ không; đánh giá độc lập với đúng đáp án tham chiếu. Một câu bám nguồn nhưng bỏ thiếu điều kiện vẫn có thể không hoàn thành yêu cầu.
- **Refusal:** retrieval proxy là “quyết định nhận trả lời theo score”, không phải bằng chứng LLM đã trả lời sai. Định nghĩa riêng: false refusal = số câu answerable bị từ chối / tổng câu answerable; false acceptance = số câu unanswerable được nhận trả lời / tổng câu unanswerable; coverage = số câu được nhận trả lời / tổng câu. Rủi ro answer thực tính trên output có nhãn, gồm cả answerable nhưng trả lời sai. Khi mẫu số bằng 0, báo không áp dụng; không gán 0% lỗi.
- **Tài nguyên:** tách embed corpus một lần, query embedding, retrieval, rerank và generation; warm/cold và cache khác nhau. CPU latency đo offline không chứng minh warm TTFT public đạt NFR.

RRF hợp nhất theo hạng, không biến score thành xác suất có đáp án [S1]. Không tái sử dụng nguyên ngưỡng giữa dense, hybrid và rerank, hoặc sau khi đổi embedding. “Không tìm thấy” có thể do corpus không có đáp án, truy xuất bỏ sót, mất đoạn khi cắt context hoặc model sinh sai; nhóm 5–6 cần phân loại nguyên nhân thay vì gộp vào một tỉ lệ.

### 4.2. Quy tắc kết luận trước khi nhìn test

1. Nhóm 3 phải ghi metric chính, mức chênh lệch có ý nghĩa thực tiễn, ràng buộc tài nguyên và cách lượng hóa bất định trước test. Chưa có cơ sở để đặt mức tăng 5% hay ngân sách vài giây thành tiêu chuẩn đã duyệt.
2. So sánh paired trên cùng câu; câu dịch/paraphrase hoặc chung nguồn cần xử lý phụ thuộc khi chia tập và tính bất định. Phân tích nhiều model/ngôn ngữ là phụ hoặc cần kiểm soát so sánh nhiều lần; không chọn riêng kết quả thuận lợi.
3. Có ba kết luận hợp lệ: hỗ trợ giả thuyết trong phạm vi mẫu; không hỗ trợ/kết quả ngược; chưa đủ bằng chứng vì mẫu/bất định/gate dữ liệu. Không có cải thiện vẫn là kết quả nghiên cứu nếu phép đo hợp lệ.
4. Phân biệt **RQ đã được trả lời** với **đạt mục tiêu sản phẩm**. PRD đề ra Recall@5 ≥ 0.80, citation precision ≥ 0.85, từ chối đúng trên unanswerable ≥ 0.80. Đây là mục tiêu ban đầu còn draft, không phải kết quả, không phải effect size và không đủ để chấp nhận một hệ thống từ chối mọi câu.
5. Nếu điều chỉnh mục tiêu sau baseline, chỉ dùng dev/baseline được phép; ghi lý do và đóng băng trước test. Không sửa ngưỡng/mục tiêu sau khi nhìn test rồi coi test cũ là kiểm chứng độc lập.

## 5. Phạm vi tối thiểu và những gì không mở rộng

| Giữ trong lõi nghiên cứu | Giữ như yêu cầu kiểm chứng hệ thống | Ngoài lõi / chỉ làm khi đủ điều kiện |
|---|---|---|
| Corpus EN gốc, query VI/EN (EN→EN, VI→EN), corpus cố định và nhãn người duyệt; answerable/unanswerable | Workspace filter và chống lộ dữ liệu; citation ánh xạ được; pipeline nối thật | Corpus VI, EN→VI/VI→VI, ngôn ngữ khác, mọi loại tài liệu hoặc câu hỏi dài nhiều lượt |
| Dense/BM25/hybrid để trả lời RQ1; một reranker bật/tắt; ngưỡng refusal có dev/test | Upload/trích xuất đủ để phục vụ corpus, xem nguồn và chạy lại thí nghiệm | Thử mọi embedding/reranker, fine-tune, thuật toán fusion mới, BGE sparse/ColBERT |
| Một đối chứng embedding cho RQ5 khi khả thi; tài nguyên CPU đo thực | Smoke end-to-end, trace config/model/version và artifacts | Tối ưu provider/free tier, public deploy, so quota hoặc uptime như đóng góp chính |
| Tập con answer-level cố định và người duyệt cho RQ2–3 | Tenant isolation là điều kiện bắt buộc nếu tuyên bố hệ thống đa workspace | Benchmark tenant overhead RQ4, load test lớn, chứng minh bảo mật tuyệt đối, product analytics |

**Không cắt âm thầm để tiết kiệm CPU:** trong scope hai hướng đã làm rõ, không bỏ nhánh BM25, bỏ câu unanswerable, bỏ EN→EN/VI→EN hoặc chỉ giữ câu rerank làm tốt. Có thể giảm số model, số lần thử cấu hình và số câu generation đã chọn trước theo lớp. Nếu phải bỏ answer-level, đầu ra chỉ còn nghiên cứu retrieval/proxy; phải xin owner chấp nhận thu hẹp tuyên bố RQ2–RQ3 và đối chiếu lại đề cương, không gọi đã hoàn tất mục tiêu hiện tại.

## 6. Tính khả thi trên CPU và cách giảm tải có nguyên tắc

Khả thi **có điều kiện**, chưa đủ dữ liệu để hứa thời gian hoàn thành hoặc chọn model. Không dùng số tham số hoặc leaderboard thay số đo CPU của owner. Phần retrieval không cần generator; phần generation là nút ràng buộc riêng.

| Thành phần | Chi phí / điều chưa biết | Cách giữ nghiên cứu khả thi | Điều kiện chuyển bước |
|---|---|---|---|
| Dense embedding | Phụ thuộc CPU, RAM, chiều vector, tokenizer, độ dài, batch và runtime | Embed từng model nối tiếp; cache có provenance; giữ corpus/chunks chung | Nhóm 5 đo pilot sau khi nhóm 2–4 đủ gate; ước lượng thời gian toàn tập và peak RAM trong ngân sách |
| BM25 + RRF | Thường ít tốn inference hơn transformer nhưng chưa đo trên corpus này | Dùng lexical baseline xác định rõ tokenizer/scorer; không mở ma trận fusion lớn | Kiểm tra scorer và run artifact; runtime `ts_rank` phải được tách hoặc làm parity trước kết luận hệ thống |
| Rerank | Số cặp xấp xỉ số query × candidate pool; ngữ cảnh dài tăng chi phí | Một reranker, pool cố định và tập con phân tầng nếu cần; giữ cùng candidate IDs khi bật/tắt | Có candidate recall đủ và pilot không vượt ngân sách; báo giới hạn tập con |
| Generation / duyệt answer | CPU local có thể quá chậm; API phụ thuộc quota, reviewer tốn thời gian | Một generator cố định trên tập con chốt trước; API chỉ xem xét sau, không gọi trong session này; người duyệt là điểm tựa | Có đường generation được phép và reviewer; nếu không thì RQ2–3 answer-level chưa sẵn sàng |
| Phân tích / tái lập | Không chỉ inference: cần giữ outputs, config, dữ liệu và nhãn | Ưu tiên paired artifacts và chạy tuần tự; tách cold/warm/cache | Có hash/revision/runtime/hardware và lệnh chạy; không chỉ ghi commit khi working tree còn dirty |

Quan hệ để nhóm 5 ước lượng: thời gian embed mỗi model ≈ số chunk / throughput pilot; rerank ≈ số query × pool × chi phí trung bình mỗi cặp (phải hiệu chỉnh theo batch); generation ≈ số query tập con × số điều kiện × thời gian một lượt. Đây là phép lập ngân sách, **không phải benchmark**. Chạy model nối tiếp để tránh cộng đồng thời peak RAM; không giảm corpus test sau khi thấy model nào thua.

Đề cương dự kiến ít nhất 100 câu, nhưng chia dev/test, hai ngôn ngữ query và answerability vẫn có thể làm từng ô nhỏ. Không coi 100 là bảo đảm statistical power; nhóm 2 phải đưa số câu thực mỗi ô và khối lượng duyệt, nhóm 3 định mức kết luận tương ứng. Nếu reviewer chỉ có một người, ghi tự duyệt và ưu tiên một phần kiểm tra độc lập; không tự gọi nhãn đó là đồng thuận hai người.

## 7. Các bước nhỏ để chốt nhóm 1

Đây là checklist nghiên cứu, không phải PLAN/ticket và không cập nhật bộ đếm thực thi.

| Bước | Việc cần làm / người tham gia | Phụ thuộc | Đầu ra cụ thể | Tiêu chí hoàn thành |
|---|---|---|---|---|
| 1. Đối chiếu cam kết | Người phân tích đọc PRD, đề cương, handoff và quyết định mới | Tài liệu hiện có | Bảng kế thừa ở §2 và bản đồ RQ ở §4 | Nêu được draft/định hướng/đã đo; không có phê duyệt suy diễn. Đã thực hiện trong tài liệu này |
| 2. Chốt phát biểu vấn đề | Owner xác nhận đối tượng SOP, VI/EN, hỏi một lượt và evidence-grounded QA | Bước 1 | Một đoạn scope charter dựa trên §3 | Có corpus/task/ngôn ngữ, giới hạn khái quát và loại đóng góp; ghi xác nhận thay vì chỉ có đề xuất |
| 3. Chốt ưu tiên | Owner cùng người hướng dẫn nếu yêu cầu trường ảnh hưởng phạm vi | Bước 2 | Danh sách RQ chính/phụ/ngoài phạm vi | RQ1–3 được giữ hoặc thay đổi có lý do; RQ5 và RQ4 không vô tình trở thành điều kiện chặn toàn nghiên cứu |
| 4. Định nghĩa khái niệm | Nhóm 1 bàn giao, nhóm 2–3 hoàn thiện relevance/metrics | Bước 2–3 | Từ điển answerable/evidence/citation/refusal và bảng RQ→bằng chứng | Không đánh đồng retrieval proxy, citation mapping, faithfulness và đúng đáp án; có xử lý nhiều bằng chứng |
| 5. Xác nhận nguồn lực | Owner cung cấp CPU/RAM khả dụng, giờ chạy, deadline, reviewer, nguồn corpus | Bước 3 | Resource envelope và danh sách thiếu ở §8 | Có giới hạn định lượng hoặc ghi rõ pending; chưa có thì chưa cam kết full model sweep |
| 6. Kiểm tra khả thi dữ liệu/phương pháp | Nhóm 2–3 phản hồi theo scope, không chạy benchmark dài | Bước 4–5 | Số mẫu theo lớp dự kiến, quyền sử dụng, phương án tập con và tiêu chí quyết định | Không chỉ smoke; có kế hoạch dev/test và duyệt nhãn; nhận diện phạm vi nào phải thu hẹp trước khóa test |
| 7. Khóa bản phạm vi | Owner duyệt scope charter và các lựa chọn ở §8 sau vòng phản hồi | Bước 6 | Nhật ký quyết định: người/ngày/nội dung/lý do/phần còn mở | Không còn mâu thuẫn giữa tuyên bố đóng góp và dữ liệu/nguồn lực dự kiến; các thay đổi PRD/đề cương chỉ thực hiện khi được yêu cầu riêng |

Nhóm 2 và 3 có thể bắt đầu khảo sát từ bản này với trạng thái **provisional**. Nhóm 1 chỉ được xem là “đã chốt phạm vi” sau bước 7; chưa cần model thắng hoặc có benchmark để hoàn tất quyết định phạm vi.

## 8. Lựa chọn cần owner chốt và đầu vào còn thiếu

### 8.1. Các lựa chọn thực sự ảnh hưởng phạm vi

| Quyết định | Khuyến nghị để owner xem xét | Nếu chọn khác | Trạng thái |
|---|---|---|---|
| QĐ-01: Mức cam kết của nghiên cứu | Giữ RQ1–3, có answer-level subset cho RQ2–3; chỉ kết luận cho query VI/EN trên corpus SOP EN đã chọn | Retrieval-only giảm công nhưng không trả lời đầy đủ đề cương/PRD về câu trả lời, citation và refusal | Owner đồng ý 19/10/2026; ngôn ngữ corpus theo QĐ-03 được làm rõ tiếp sau |
| QĐ-02: So embedding đến đâu | RQ5 phụ, baseline + một challenger trước; model thứ ba là mở rộng sau pilot | Ba model bắt buộc tăng embedding runs và duyệt phân tích; bỏ RQ5 thì không có bằng chứng chọn dense model qua so sánh | Owner đồng ý 19/10/2026; RQ4 ngoài lõi, isolation vẫn bắt buộc |
| QĐ-03: Phạm vi ứng dụng và ngôn ngữ của corpus | Corpus EN gốc; query eval VI/EN, hai hướng EN→EN và VI→EN; không dịch corpus. Đề xuất tập con GitLab về quy trình nhân viên/làm việc từ xa; Added Bytes là phương án thay thế | Chỉ kết luận hỗ trợ query VI/EN trên corpus EN; chưa đánh giá corpus VI hoặc cross-lingual hai chiều | Owner làm rõ ngôn ngữ ngày 19/10/2026; nguồn cụ thể và ranh giới chủ đề còn là đề xuất |
| QĐ-04: Ngân sách nghiên cứu và đánh giá answer | Máy RAM 32 GB, không GPU; kết hợp local + API LLM miễn phí; ưu tiên hoàn thành nhanh | Ma trận nhỏ, chạy tuần tự và pilot ngắn; chưa hứa thời gian hoặc khả năng chạy model cụ thể | Đã chốt định hướng 19/10/2026; không yêu cầu thêm bảng giờ chạy/deadline ở nhóm 1; đường sinh và duyệt cần kiểm tra khi thực hiện |

Không cần owner quyết ngay provider deploy, Java version, chỉ số thread/batch, toàn bộ danh sách model, hoặc từng k/threshold trong nhóm 1. Nhóm 3–5 đề xuất các chi tiết đó trong giới hạn đã chốt. RQ4 mặc định là mở rộng theo đề xuất này; owner chỉ cần quyết thêm nếu muốn nâng nó thành mục tiêu nghiên cứu.

### 8.2. Sổ giả định và đầu vào thiếu

| Mã | Giả định tạm dùng | Đầu vào cần / bên cung cấp | Tác động nếu sai |
|---|---|---|---|
| A1 | Nghiên cứu/báo cáo trước deploy; owner yêu cầu làm nhanh nhất có thể ngày 19/10 | Chưa có ngày deadline cụ thể; dùng phạm vi nhỏ và tái sử dụng công cụ hiện có | Không biến free tier thành tiêu chí model khoa học hoặc cam kết ngày hoàn thành chưa đo |
| A2 | Corpus EN gốc và bộ câu hỏi VI/EN theo owner làm rõ | Nhóm 2: kiểm tra nguồn ở §8.4, quyền chia sẻ, phiên bản, nhãn và ngôn ngữ câu hỏi | Không yêu cầu corpus/bản dịch VI; chưa thể hứa tính đại diện ngoài nguồn được chọn |
| A3 | Giữ người duyệt nhãn và output theo QĐ-01 | Chưa có tên reviewer/giờ duyệt; nhóm 2–3 đề xuất khối lượng nhỏ, không đòi chốt lịch để tiếp tục khảo sát | Thiếu người duyệt thì chưa có gold/answer-level evidence; nếu một người tự duyệt phải ghi rõ |
| A4 | Máy owner RAM 32 GB, không GPU; local dùng cho retrieval/embedding/rerank theo pilot | Nhóm 5 tự ghi CPU, RAM trống và thời gian pilot khi chạy; không cần hỏi thêm ngân sách chi tiết ở nhóm 1 | Không coi 32 GB tổng là RAM trống hoặc bằng chứng model cụ thể chạy đủ nhanh |
| A5 | Owner muốn tận dụng API LLM miễn phí kết hợp local | Chi tiết generator được yêu cầu skip; nhóm thực hiện chọn một generator/model cố định và kiểm tra quota thực khi bắt đầu | Chưa có provider/quota được xác minh; nếu hết quota, lưu checkpoint và chờ hoặc chạy lại điều kiện bị ảnh hưởng khi đổi model |
| A6 | Owner đồng ý QĐ-01–02; chưa chọn nguồn corpus | Owner yêu cầu skip câu hỏi về tình trạng duyệt đề cương; không hỏi lại trong vòng này | Không suy thành PRD/ADR/đề cương đã approved; giữ phần chưa xác minh trong giới hạn báo cáo |

### 8.3. Nhật ký quyết định owner ngày 19/10/2026

Căn cứ: owner trả lời “đồng ý 1 và 2”; chưa tìm trước nguồn, từng dùng GitLab Handbook và yêu cầu recommend; máy local RAM 32 GB không GPU, kết hợp API LLM free; muốn triển khai nhanh, không tốn nhiều thời gian; yêu cầu skip mục 6–7 của vòng hỏi đáp trước (chi tiết generator và đề cương).

- **Đã chốt:** RQ1–3 chính, answer-level subset có người duyệt; RQ5 phụ với baseline + một challenger, model thứ ba chỉ mở rộng sau pilot; RQ4 ngoài lõi, kiểm tra isolation vẫn bắt buộc.
- **Đã chốt định hướng nguồn lực:** local + API LLM miễn phí; ưu tiên giảm công chuẩn bị dữ liệu và số cấu hình. Không đặt thêm vòng hỏi CPU model/giờ chạy/deadline làm điều kiện bắt đầu nhóm 2–3.
- **Ngôn ngữ đã làm rõ tiếp theo:** owner yêu cầu corpus chỉ có EN gốc, thêm query VI vào test/eval để kiểm chứng query đa ngôn ngữ. Áp dụng EN→EN và VI→EN; bỏ yêu cầu dịch corpus/bốn hướng của đề xuất trước. Đây là thu hẹp phạm vi đánh giá theo mục tiêu owner, không phải cắt thí nghiệm sau khi xem kết quả.
- **Còn mở:** nguồn corpus cụ thể và ranh giới chủ đề. GitLab/Added Bytes ở §8.4 là khuyến nghị của agent, chưa phải nguồn đã được owner xác nhận.
- **Chuyển sang kiểm tra khi thực hiện:** generator khả dụng và quy trình duyệt thực tế. Yêu cầu skip là bỏ vòng hỏi chi tiết hiện tại, không tự chứng nhận đã có quota, reviewer hoặc đề cương được duyệt. Không chạy model/API hoặc sinh nhãn hàng loạt trong lần cập nhật này.

### 8.4. Khuyến nghị corpus để triển khai nhanh

Tra cứu nguồn chính thức ngày 19/10/2026. Khuyến nghị **tiếp tục dùng một tập con GitLab Handbook** vì owner đã quen nguồn; thu hẹp vào quy trình nhân viên và làm việc từ xa, thay vì thu toàn handbook hoặc trộn nhiều công ty ngay từ đầu. Đề xuất khởi đầu khoảng 20–30 trang/mục có quy trình, điều kiện hoặc trách nhiệm rõ; con số này là mức chuẩn bị dữ liệu để nhóm 2 kiểm tra, không bảo đảm đủ câu hỏi hay statistical power.

| Nguồn | Nội dung đã kiểm tra | Cách dùng đề xuất / giới hạn |
|---|---|---|
| **GitLab Handbook — ưu tiên** | [Onboarding](https://handbook.gitlab.com/handbook/people-group/general-onboarding/) có vai trò và bước thực hiện; [Travel and Expense](https://handbook.gitlab.com/handbook/finance/expenses/) là chính sách tác nghiệp. [Handbook Usage, External use](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook) nêu giấy phép nội dung CC BY-SA 4.0 | Chọn các trang công khai trong cùng miền quy trình; lấy Markdown gốc, ghim commit/snapshot và giữ URL/mục. Loại liên kết nội bộ không đọc được khỏi bằng chứng; kiểm tra điều khoản riêng của tài sản bên thứ ba. Không suy giấy phép nội dung từ LICENSE phần software của repo |
| **Added Bytes — phương án thay thế gọn hơn** | [Trang chủ](https://handbook.addedbytes.com/) liệt kê onboarding, holidays, offboarding, remote/flexible working; công bố CC BY-SA 4.0 trừ ảnh/logo. Đã đọc [Onboarding](https://handbook.addedbytes.com/employment/onboarding) và [Holidays](https://handbook.addedbytes.com/employment/holidays) | Thuận tiện nếu muốn một handbook ít mục để đọc/duyệt. Chưa kiểm kê số câu có thể tạo; có thể quá nhỏ cho bộ eval dự kiến. Nguồn ghi có kế thừa GitLab nên không coi hai handbook là hai miền hoàn toàn độc lập |

Theo owner làm rõ, **chỉ nạp tài liệu EN gốc; không dịch corpus**. Câu hỏi eval viết bằng EN và VI, có thể dùng cặp câu cùng nghĩa để so sánh ảnh hưởng của ngôn ngữ query. Nhãn bằng chứng cho câu VI vẫn trỏ tới tài liệu/đoạn EN; câu trả lời tham chiếu VI cần được kiểm tra theo cùng bằng chứng đó.

Quy tắc tối thiểu khi nhóm 2 thiết kế dữ liệu:

1. Tạo manifest cho tài liệu/phiên bản EN và nhóm câu hỏi cùng nghĩa; chia dev/test theo nhóm nội dung/câu hỏi liên quan, tránh cặp EN/VI hoặc paraphrase tương ứng nằm hai phía.
2. Giữ hai hướng EN→EN và VI→EN trên cùng corpus EN và cùng phạm vi truy cập cho các phương pháp so sánh. Câu VI nên có diễn đạt tự nhiên; nếu dịch từ câu EN phải duyệt lại, giữ nguyên ý và điều kiện cần trả lời.
3. Giữ câu answerable và unanswerable gần chủ đề ở cả hai ngôn ngữ query; kiểm tra unanswerable trên toàn corpus hợp lệ. Không chỉ đảo ngôn ngữ một câu rồi tính thành quan sát độc lập.
4. Báo riêng retrieval và answer-level theo query EN/VI. Tìm đúng đoạn EN từ query VI chứng minh khả năng truy xuất VI→EN trong bộ eval; muốn kết luận QA tiếng Việt còn phải duyệt độ đúng, căn cứ và trích dẫn của output VI. Không suy kết quả cho corpus VI hoặc cross-lingual hai chiều. Số câu và answer-level subset do nhóm 2–3 đề xuất trước test, giữ mốc dự kiến ≥100 của đề cương làm đầu vào hiện có.

Đường triển khai nhanh đề xuất: một nguồn, tập con có ranh giới, dữ liệu văn bản dễ lấy; local chạy retrieval và hai embedding tuần tự; một reranker; một generator API miễn phí cố định cho tập con answer-level. Không mở so sánh provider hoặc chạy LLM local nặng mặc định. Khả dụng/quota API phải kiểm tra khi thực hiện; chưa chọn provider và chưa hứa thời gian. Nếu cần đổi generator, không trộn output khác model vào cùng phép so sánh như một điều kiện cố định.

## 9. Tiêu chí hoàn tất và bàn giao cho các nhóm sau

### 9.1. Phân biệt hoàn tất tài liệu với chốt nghiên cứu

- [x] Đã đọc AGENTS, handoff, PRD/RQ/giới hạn và các đầu vào hiện có; kiểm tra file đích và trạng thái Git.
- [x] Đã ghi vấn đề, đóng góp dự kiến, RQ chính/phụ, giả thuyết, giới hạn, cách kết luận và rủi ro CPU.
- [x] Đã tách đề xuất khỏi kết quả nguồn, kết quả đo, phê duyệt và yêu cầu kỹ thuật; liệt kê bước nhỏ, đầu ra và phụ thuộc.
- [x] Owner xác nhận QĐ-01–02 ngày 19/10/2026; đã ghi nhật ký ở §8.3.
- [x] Owner cung cấp định hướng QĐ-04: RAM 32 GB, không GPU, local + API LLM miễn phí, ưu tiên nhanh; chi tiết vận hành kiểm tra khi thực hiện.
- [x] Owner làm rõ QĐ-03 về ngôn ngữ: corpus EN gốc, query eval VI/EN; không dịch corpus.
- [ ] Owner chọn nguồn cụ thể và scope charter cuối; GitLab/Added Bytes cùng ranh giới chủ đề ở §8.4 vẫn là khuyến nghị.
- [ ] Nhóm 2–3 xác nhận corpus/nhãn/dev-test và phương pháp đủ để kiểm chứng RQ trong nguồn lực; chưa có đầu ra.
- [ ] Có bản ghi quyết định để nhóm sau dùng như phạm vi đã khóa; `final` của HANDOFF không thay mục này.

### 9.2. Hợp đồng đầu vào/đầu ra cho nhóm sau

| Nhóm nhận | Dùng được từ bản này | Cần hoàn thiện / không được giả định |
|---|---|---|
| **2 — dataset** | Corpus SOP EN gốc; query EN/VI, hai hướng EN→EN và VI→EN; answerability theo corpus/quyền, nhiều bằng chứng, cam kết dự kiến ≥100 của đề cương | Corpus hợp lệ và đơn vị relevance; số mẫu mỗi lớp/dev-test, reviewer, nhóm câu hỏi EN/VI cùng nghĩa và near-duplicates; không dịch corpus, không coi smoke hoặc LLM draft là gold |
| **3 — phương pháp/model** | RQ1–3 lõi, RQ5 phụ, tiêu chí kết luận và tách retrieval/answer/resources | Shortlist cuối, metric chính/phụ, effect size, pool/chunking/instruction, bất định, subset; phải chốt trước test |
| **4 — công cụ** | Các khoảng trống gây sai tuyên bố: lexical parity, 512-token cap, revision/cache provenance, reranker injection và proxy refusal | Kiểm tra relevance trùng trong `metrics.py`: DCG hiện cộng từng chunk trúng cùng target trong khi ideal theo số target; xác minh nDCG không vượt miền chuẩn và đủ rank depth trước dùng. Đây là cảnh báo từ đọc mã, chưa sửa/chạy test lỗi |
| **5 — runs/analysis** | Ngân sách theo giai đoạn, paired comparison, cho phép kết quả âm, không chọn sau test | Pilot CPU/RAM, gate dữ liệu/công cụ, rule dừng và artifacts đo thực; không ghi latency dự kiến như kết quả |
| **6 — validation/report** | Đóng góp và mức tuyên bố, rubric evidence/citation/refusal, isolation tách RQ4 | Answer-level human review, system call path/parity, leak tests và gói tái lập; không suy end-to-end từ offline retrieval |

## 10. Nguồn gốc và giới hạn suy luận

Đối chiếu nguồn ngày **18/10/2026**. Các nguồn sau cung cấp cơ sở phương pháp; không nguồn nào chứng minh model/cấu hình nào thắng trên corpus SOPilot.

- **[S1] Cormack, Clarke và Büttcher (SIGIR 2009), Reciprocal Rank Fusion.** Nguồn mô tả hợp nhất thứ hạng và thí nghiệm trên các bộ IR của tác giả. **Suy luận cho project:** RRF là baseline hợp nhất phù hợp để khảo sát tính bổ sung, nhưng kết quả gốc không bảo đảm hybrid VI/EN sẽ thắng. [Paper gốc của tác giả](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).
- **[S2] Thakur và cộng sự (NeurIPS 2021), BEIR.** Nguồn đánh giá retrieval trên nhiều miền, cho thấy BM25 là baseline mạnh và reranking có đánh đổi chi phí. **Suy luận cho project:** cần kiểm tra trên miền SOP và đo tài nguyên thay vì chọn theo leaderboard tổng; không mượn điểm BEIR làm số đo SOP. [Paper BEIR](https://arxiv.org/abs/2104.08663).
- **[S3] Gao và cộng sự (EMNLP 2023), ALCE.** Nguồn đánh giá sinh câu trả lời có trích dẫn, phân biệt correctness và citation quality. **Suy luận cho project:** tìm đúng nguồn chưa đủ để xác nhận chất lượng câu trả lời; rubric VI/EN cần người kiểm tra, không mặc định automatic judge đã được xác thực cho SOP. [Paper ALCE](https://aclanthology.org/2023.emnlp-main.398/).
- **[S4] Rajpurkar, Jia và Liang (ACL 2018), Know What You Don't Know: Unanswerable Questions for SQuAD.** Nguồn đưa câu không trả lời được nhưng gần chủ đề vào đánh giá đọc hiểu. **Suy luận cho project:** unanswerable cần đủ khó để tránh chỉ nhận diện lệch chủ đề. Bối cảnh SQuAD là đọc hiểu đoạn cho trước, không đồng nhất với tìm kiếm toàn corpus; SOPilot phải định nghĩa lại answerability theo corpus và quyền truy cập. [Paper SQuAD 2.0](https://aclanthology.org/P18-2124/).

Bản khảo sát ngày 18/10 chỉ đọc mã/tài liệu và nguồn công khai rồi tạo file bàn giao. Cập nhật ngày 19/10 ghi nhận quyết định owner ở §8.3 và kiểm tra nguồn corpus ở §8.4. Không tải/chạy model, chạy benchmark hoặc full stack, gọi API có key, đọc `.env`, sửa tiến độ, commit/push hay deploy. Chưa có bằng chứng để kết luận H1–H5 đúng, hệ thống đạt NFR hoặc dữ liệu đã được người duyệt; phạm vi mới được chốt một phần như nhật ký, chưa khóa corpus.

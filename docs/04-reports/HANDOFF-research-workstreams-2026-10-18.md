---
id: HANDOFF-research-workstreams-2026-10-18
title: "Sáu nhóm công việc nghiên cứu SOPilot và prompt cho session tiếp theo"
status: final
type: handoff
scope: research
created: 2026-10-18
updated: 2026-10-18
author: "Owner"
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/03-plans/PLAN-V2-sopilot-mvp.md
  - docs/04-reports/AUDIT-retrieval-stack-research-2026-10-18.md
---

# Sáu nhóm công việc nghiên cứu SOPilot

## Bối cảnh và cách sử dụng

Ưu tiên hiện tại của owner là hoàn thiện nghiên cứu khoa học và báo cáo, trước khi tối ưu deploy/free tier. Mục tiêu của các session dưới đây là tìm hiểu sâu, xác định các bước nhỏ và đầu ra cần có cho từng nhóm. Đây là bản bàn giao định hướng, không phải PLAN triển khai, không tạo ticket và không thay nguồn tiến độ trong `docs/03-plans/`.

Lý do cần đánh giá lại embedding: BGE-M3 ban đầu được cân nhắc để tận dụng dense và sparse của cùng model, nhưng cấu hình hiện nay dùng nhánh lexical riêng. Trong thí nghiệm dense + BM25, phải đánh giá BGE-M3 như một dense retriever; sparse/ColBERT chưa được dùng không phải lợi ích đã chứng minh. Khuyến nghị stack trong báo cáo retrieval ngày 18/10 là đề xuất có điều kiện, không phải kết quả chọn model từ thực nghiệm. Việc chọn model được mở lại theo chất lượng SOP, đóng góp cho hybrid và chi phí CPU.

| Nhóm | Công việc lớn | Đầu ra mong đợi |
|---|---|---|
| 1 | Chốt phạm vi và câu hỏi nghiên cứu | Mục tiêu, RQ chính/phụ, giả thuyết, giới hạn và tiêu chí kết luận |
| 2 | Xây dựng bộ dữ liệu đánh giá đáng tin cậy | Thiết kế corpus, câu hỏi, nhãn bằng chứng, quy trình người duyệt và chia tập |
| 3 | Thiết kế phương pháp thực nghiệm và shortlist model | Baseline, model ứng viên, metrics, biến kiểm soát và quy tắc chọn cấu hình |
| 4 | Hoàn thiện công cụ và pipeline phục vụ thí nghiệm | Đặc tả các thay đổi cần thiết để chạy đúng, ghi đủ bằng chứng và tái lập |
| 5 | Chạy thí nghiệm, phân tích và chọn stack | Trình tự chạy, cách đọc kết quả, phân tích lỗi và phương pháp ra quyết định |
| 6 | Kiểm chứng hệ thống và hoàn thiện báo cáo khoa học | Kiểm chứng RAG cuối, cấu trúc bài báo/báo cáo, giới hạn và gói tái lập |

Thứ tự: nhóm 1 trước; nhóm 2 và 3 điều chỉnh qua lại; nhóm 4 dựa trên thiết kế đã chốt; nhóm 5 dùng dữ liệu/công cụ đủ điều kiện; nhóm 6 tổng hợp kết quả và kiểm chứng hệ thống. Có thể tìm hiểu nhóm sau từ sớm, nhưng phải ghi rõ đầu vào chưa có thay vì giả định đã hoàn thành.

## Quy tắc chung cho session mới

- Workspace: `C:\Users\Tien\Workspace\Personal\SOPilot`. Đọc AGENTS.md và kiểm tra Git trước; giữ nguyên các thay đổi đang có, không đọc `.env`.
- Đọc tài liệu thượng nguồn theo `refs` và kiểm tra trạng thái hiện tại. PRD/ADR/PLAN V2 đang là draft tại thời điểm bàn giao; không tự coi đã được duyệt.
- Đầu ra của mỗi prompt là tài liệu phân tích có các bước nhỏ, phụ thuộc, tiêu chí hoàn thành, lựa chọn cần owner chốt và bằng chứng cần thu thập. Chưa triển khai code, tải model, chạy thí nghiệm dài, gọi API có phí, commit/push hoặc deploy theo các prompt này.
- Dùng nguồn chính thức/paper gốc khi cần tra cứu; phân biệt kết quả nguồn, suy luận, giả thuyết và phép đo của project. Không coi leaderboard tổng là bằng chứng model tốt nhất trên SOP.
- Lưu kết quả tìm hiểu vào một file `RESEARCH-0N-<topic>.md` trong `docs/04-reports/`, có frontmatter theo docs/README.md. Kiểm tra file đã tồn tại trước; kế thừa quyết định owner đã chốt, giữ nội dung còn giá trị. Không sửa PRD/ADR/PLAN/ticket khi chưa được yêu cầu.
- Tài liệu tìm hiểu không là nguồn trạng thái thực thi. Kết thúc session nêu rõ điều đã xác minh, điều chưa biết, các bước nhỏ đề xuất và đầu vào cho nhóm sau. `final` chỉ kết thúc tài liệu bàn giao, không chứng nhận thí nghiệm hay nghiệm thu.

## Nhóm 1 — Phạm vi và câu hỏi nghiên cứu

Đầu ra đề nghị: `docs/04-reports/RESEARCH-01-scope-and-rqs.md`.

```text
Tôi muốn tìm hiểu sâu nhóm 1: Chốt phạm vi và câu hỏi nghiên cứu SOPilot.

Đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md, áp dụng quy tắc chung trong đó. Đọc PRD-V2 và các RQ/giới hạn liên quan; kiểm tra quyết định mới hơn nếu có.

Giúp tôi xác định vấn đề nghiên cứu, đóng góp dự kiến, RQ chính/phụ, giả thuyết và những gì nằm ngoài phạm vi. Đánh giá tính khả thi trên máy CPU không GPU, phân biệt câu hỏi về embedding, hybrid, rerank, refusal với yêu cầu kỹ thuật hệ thống. Chưa chốt model hoặc thiết kế toàn bộ thí nghiệm chi tiết.

Đề xuất phạm vi tối thiểu đủ giá trị khoa học, các bước nhỏ để chốt nhóm này, tiêu chí hoàn thành và những lựa chọn thực sự cần tôi quyết định. Lưu phân tích vào file đầu ra của nhóm 1 được chỉ định trong tài liệu bàn giao; chưa tạo PLAN/ticket hay sửa code.
```

## Nhóm 2 — Bộ dữ liệu đánh giá

Đầu ra đề nghị: `docs/04-reports/RESEARCH-02-dataset-and-labeling.md`.

```text
Tôi muốn tìm hiểu sâu nhóm 2: Xây dựng bộ dữ liệu đánh giá đáng tin cậy cho SOPilot.

Đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md, áp dụng quy tắc chung trong đó. Đọc kết quả nhóm 1 nếu đã có; nếu chưa, ghi rõ các giả định còn mở. Kiểm tra định dạng dữ liệu và dataset hiện có trong eval/ trước khi đề xuất.

Phân tích cách xây corpus SOP, chọn nguồn/giấy phép, thiết kế câu hỏi VI→VI, EN→EN, VI→EN, EN→VI, câu không trả lời được, hard negatives và câu cần nhiều đoạn bằng chứng. Làm rõ đơn vị relevance: tài liệu, trang hay chunk; quy trình người duyệt và chia dev/test để hạn chế rò rỉ/near-duplicates.

Đề xuất quy mô khả thi có lý do, các bước nhỏ xây và kiểm tra dữ liệu, tiêu chí chất lượng, rủi ro thiên lệch và công việc người cần làm. Lưu vào file đầu ra nhóm 2. Chưa tự sinh hàng loạt nhãn hoặc coi dữ liệu LLM sinh là đã được người duyệt.
```

## Nhóm 3 — Phương pháp thực nghiệm và model

Đầu ra đề nghị: `docs/04-reports/RESEARCH-03-methods-and-models.md`.

```text
Tôi muốn tìm hiểu sâu nhóm 3: Thiết kế phương pháp thực nghiệm và shortlist model cho SOPilot.

Đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md, áp dụng quy tắc chung. Đọc kết quả nhóm 1–2 nếu có và báo cáo retrieval ngày 18/10; các khuyến nghị model trước đây là giả thuyết cần kiểm chứng.

Thiết kế cách so embedding đúng vai trò dense trong pipeline có BM25: dense riêng, BM25 riêng, hybrid RRF, rồi rerank bật/tắt. Đề xuất shortlist nhỏ có lý do từ nguồn gốc, xét VI/EN/cross-lingual, khả năng bổ sung cho BM25 và chi phí CPU. Định nghĩa metrics chính/phụ, relevance, ngân sách candidates, instruction/tokenizer/truncation, biến kiểm soát, dev/test và cách đánh giá bất định. Tách thay model khỏi thay chunking/scorer/reranker.

Đưa ra ma trận tối thiểu khả thi, các bước nhỏ, tiêu chí hoàn thành và quy tắc chọn cấu hình trước khi thấy kết quả test. Lưu vào file đầu ra nhóm 3; chưa chạy benchmark hay mặc định model nào thắng.
```

## Nhóm 4 — Công cụ và pipeline thí nghiệm

Đầu ra đề nghị: `docs/04-reports/RESEARCH-04-experiment-tooling.md`.

```text
Tôi muốn tìm hiểu sâu nhóm 4: Hoàn thiện công cụ và pipeline phục vụ thí nghiệm SOPilot.

Đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md, áp dụng quy tắc chung. Đọc kết quả nhóm 1–3 nếu có. Đối chiếu yêu cầu thí nghiệm với code eval/ và đường retrieval/rerank thực tế, không mặc định scaffold đã được nối.

Xác minh các điểm đã ghi nhận: runtime bm25_search dùng ts_rank còn eval dùng BM25; embedding eval bị giới hạn 512 tokens; instruction/revision/cache provenance; reranker chưa được inject vào chat mặc định và điểm retrieval/rerank bị trộn. Phân loại thay đổi cần cho nghiên cứu độc lập, cho so sánh công bằng và cho kiểm chứng hệ thống.

Đề xuất các bước nhỏ với file/phạm vi dự kiến, phụ thuộc, đầu ra run artifacts, kiểm thử cần thiết và tiêu chí hoàn thành. Lưu vào file đầu ra nhóm 4. Session này chỉ khảo sát và đặc tả công việc, chưa sửa code hoặc chạy full stack.
```

## Nhóm 5 — Chạy, phân tích và chọn stack

Đầu ra đề nghị: `docs/04-reports/RESEARCH-05-runs-and-analysis.md`.

```text
Tôi muốn tìm hiểu sâu nhóm 5: Chạy thí nghiệm, phân tích và chọn stack SOPilot.

Đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md, áp dụng quy tắc chung. Kiểm tra đầu ra nhóm 1–4, dataset, config và bằng chứng test/run hiện có. Ghi rõ gate chưa đạt; không giả định dữ liệu hay công cụ đã sẵn sàng.

Giúp tôi thiết kế trình tự smoke → dev → test, ngân sách thời gian/RAM trên CPU, cách cache và ghi model/config/hardware, cách đo latency và chất lượng, phân tích paired differences/khoảng tin cậy nếu phù hợp. Thiết kế phân tích lỗi theo ngôn ngữ, loại câu hỏi và bước gây mất bằng chứng; cách chọn model theo chất lượng–tài nguyên thay vì leaderboard hoặc tiện deploy.

Lưu các bước nhỏ, tiêu chí quyết định, bảng kết quả cần có và xử lý trường hợp kết quả không ủng hộ giả thuyết vào file đầu ra nhóm 5. Đây là session tìm hiểu quy trình, chưa tải model hoặc chạy các lượt benchmark dài.
```

## Nhóm 6 — Kiểm chứng và báo cáo khoa học

Đầu ra đề nghị: `docs/04-reports/RESEARCH-06-validation-and-paper.md`.

```text
Tôi muốn tìm hiểu sâu nhóm 6: Kiểm chứng hệ thống và hoàn thiện báo cáo khoa học SOPilot.

Đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md, áp dụng quy tắc chung. Đọc kết quả nhóm 1–5 nếu có; đối chiếu các kết luận với artifacts thực tế. Nếu chưa có kết quả, chỉ thiết kế nội dung và yêu cầu bằng chứng, không điền số liệu giả định.

Phân tích cách kiểm chứng cấu hình đã chọn trong RAG: chất lượng câu trả lời, citation, refusal, latency và tenant isolation; phân biệt đóng góp của retriever, reranker và LLM. Đề xuất bố cục báo cáo khoa học, bảng/hình cần có, ablation, threats to validity, giới hạn mẫu và gói tái lập. Giữ deploy/free tier là phần phụ phù hợp phạm vi đã chốt.

Lưu các bước nhỏ, tiêu chí hoàn thành và bản đồ RQ → thí nghiệm → bằng chứng → kết luận vào file đầu ra nhóm 6. Chưa viết kết quả như đã nghiệm thu, chưa triển khai hay sửa tiến độ ticket.
```

## Prompt mở nhanh cho bất kỳ nhóm nào

```text
Trong repo SOPilot, đọc AGENTS.md và docs/04-reports/HANDOFF-research-workstreams-2026-10-18.md. Thực hiện prompt của nhóm [1–6] trong tài liệu, với mục tiêu tìm hiểu sâu và chia thành các bước nhỏ trước khi triển khai. Kế thừa quyết định owner đã chốt trong các đầu ra liên quan; ghi rõ đầu vào chưa có. Lưu kết quả vào file bàn giao được chỉ định cho nhóm đó.
```

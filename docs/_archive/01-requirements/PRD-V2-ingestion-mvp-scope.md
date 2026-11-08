---
id: PRD-V2-INGESTION-MVP-SCOPE
title: "Phạm vi ingestion đề xuất cho MVP một người phát triển"
status: superseded
created: 2026-10-20
updated: 2026-10-21
milestone: "V2: SOPilot MVP"
priority: P0
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/04-reports/AUDIT-ingestion-business-cases-2026-10-20.md
---

# Phạm vi ingestion MVP

> **`superseded` 2026-10-21.** Toàn bộ yêu cầu đã hợp nhất vào [PRD-V2](PRD-V2-sopilot-mvp.md) FR-06, FR-07, FR-08, FR-09, FR-30, FR-31 và UC-12; PRD-V2 là nguồn yêu cầu duy nhất. Hai điểm dưới đây đã thay đổi so với thân tài liệu: TXT bị bỏ khỏi MVP (ING-03), hạn mức tài liệu mặc định 50 tài liệu/200 MB thay vì tắt (ING-02). Thân bài giữ nguyên để làm lịch sử quyết định; không dùng làm tiêu chí nghiệm thu. Lý do: [AUDIT-markdown-normalization](../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md).

> **Owner duyệt 2026-10-20** theo khuyến nghị, kèm quyết định ưu tiên nghiên cứu: hạn mức thương mại tạm tắt (PRD-V2 FR-09, §8.10). Hai thay đổi sản phẩm ở §5 đã đồng bộ vào PRD-V2 (FR-07, FR-30), TECH-V2-core-api §3.3/§5.5, V2-12 và V2-15.

Bộ quyết định phạm vi ingestion cho solo dev, bổ sung PRD-V2.

## 1. Vấn đề và mục tiêu

Cần nạp kho tài liệu hiện có theo đợt, sau đó thêm hoặc thay từng file. MVP phải vận hành được với công sức một người; không cần tối ưu mọi trường hợp quy mô lớn. Các kịch bản khảo sát là giả định để quyết định phạm vi, chưa phải benchmark hay kết quả phỏng vấn khách hàng.

Hạn mức tài liệu cấu hình được nhưng tạm tắt trong giai đoạn nghiên cứu (PRD-V2 FR-09). Không cam kết năng lực xử lý hàng nghìn tài liệu khi chưa đo trên máy mục tiêu.

## 2. Người dùng và use case

- OWNER/ADMIN của workspace, kể cả cá nhân có role OWNER: chọn tài liệu đã được phép đưa vào kho hỏi đáp, upload, thay bản và xử lý lỗi.
- MEMBER: hỏi đáp trên tài liệu mình có quyền đọc.
- Nạp lần đầu: chọn tối đa 10 file một lượt; theo dõi từng file; tiếp tục lượt sau.
- Cập nhật: chọn một tài liệu hiện có rồi tải bản thay thế. Người dùng xác định quan hệ thay thế; hệ thống không suy đoán bằng ngữ nghĩa.
- Lỗi: xem lý do, thử lại nếu lỗi xử lý tạm thời; file cần sửa thì upload lại bản đã sửa. Các tài liệu thành công không chạy lại.

## 3. Yêu cầu chức năng đề xuất

- [ ] **ING-01 — Nhiều file, mức tối thiểu:** chọn tối đa 10 file/lượt trên giao diện, gửi bằng các yêu cầu upload từng file hiện có. Không có transaction thành công/thất bại toàn đợt. Mỗi file có tên, trạng thái và lý do lỗi; không cần bảng/job quản lý batch riêng. Số 10 là giới hạn sản phẩm khởi đầu, không phải mức đã đo tối ưu.
- [ ] **ING-02 — Quota:** giữ giới hạn kỹ thuật 20 MB/file. Hạn mức tài liệu/dung lượng mỗi workspace mặc định tắt (PRD-V2 FR-09); khi bật lại, kiểm tra ở backend, lượt upload có thể thành công một phần khi hết quota, và thay phiên bản không tăng số tài liệu.
- [ ] **ING-03 — Định dạng:** giữ phạm vi mới nhất trên disk: PDF có lớp chữ, MD, TXT. DOCX hoãn sau MVP; hướng dẫn người dùng xuất PDF có lớp chữ. Không OCR hoặc chuyển Word sang PDF trên server.
- [ ] **ING-04 — Bản được phép sử dụng:** người quản lý chịu trách nhiệm chọn file đã được phép dùng trong workspace; READY là đã xử lý và sẵn sàng hỏi đáp. Không có workflow duyệt, trạng thái bản nháp hoặc lịch hiệu lực riêng trong MVP.
- [ ] **ING-05 — Cập nhật nội dung:** mọi file thay thế khác bytes được trích xuất và chia chunk lại ở cấp file. Không phân loại minor/major, không so khác biệt ngữ nghĩa hoặc xử lý tăng dần theo đoạn. Chunk có cùng đầu vào embedding/model/revision được dùng cache như V2 hiện có; không đặt tỷ lệ hit bắt buộc.
- [ ] **ING-06 — Trùng chính xác:** tạo tài liệu khác có cùng SHA-256 trong workspace thì báo trùng theo PRD. Đề xuất bổ sung: upload bản thay thế có cùng SHA-256 với bản hiện hành READY thì trả "Nội dung file không thay đổi", không tạo version/job mới. File khác bytes vẫn được xử lý dù văn bản gần giống hoặc trùng sau parse.
- [ ] **ING-07 — Thay bản an toàn:** bản cũ phục vụ đến khi bản mới thành công; bản mới lỗi không làm mất khả năng hỏi đáp theo bản cũ. Không bổ sung lịch sử phiên bản trên UI, rollback hoặc so sánh version ở đề xuất này. Khi cần ngừng dùng tài liệu, dùng chức năng xóa hiện có; chưa thêm trạng thái thu hồi riêng.
- [ ] **ING-08 — Chống lặp thao tác nền:** giữ cơ chế idempotent job và retry/outbox đã có trong V2. Không xây thêm nền tảng đồng bộ nguồn hoặc cơ chế chống lạm dụng phức tạp để phục vụ các kịch bản chưa xác nhận.

## 4. Yêu cầu phi chức năng

Giữ phân quyền workspace/phòng ban. Các file được xử lý độc lập; thành công của file này không bị hủy bởi file khác lỗi. Không hứa thời gian hoàn tất cả lượt hoặc throughput quy mô lớn khi chưa đo trên máy mục tiêu. Giao diện phải phân biệt đang upload, xử lý, sẵn sàng và lỗi.

## 5. Phạm vi và thay đổi so với V2

Giữ: upload/thay/xóa từng file, hàng đợi bền, SHA-256, cache embedding, xử lý có cấu trúc, bản cũ phục vụ khi bản mới chưa READY.

Hai thay đổi sản phẩm cần đồng bộ vào PRD chính và V2-12/V2-15 nếu áp dụng:

1. Cho chọn nhiều file với kết quả độc lập, thay cho việc loại toàn bộ nhu cầu nạp nhiều file dưới nhãn "import hàng loạt". Import ZIP/thư mục, dashboard migration và connector vẫn ngoài MVP.
2. Bản thay thế trùng bytes bản hiện hành trở thành no-op rõ ràng. Đây là điều chỉnh tiêu chí V2-12 đang cho phép tạo bản mới giống bản cũ, không được trình bày là hành vi đã được duyệt từ trước. Bản khác bytes không bị bỏ chỉ vì gần giống bản cũ.

Hoãn: đồng bộ Drive/SharePoint/wiki/Git, incremental theo đoạn, semantic dedup, tự nhận quan hệ version, editor, duyệt nhiều bước, hẹn hiệu lực, phục hồi phiên bản, OCR, DOCX và tự động chuyển định dạng.

## 6. Tình huống nghiệm thu đề xuất

- [ ] Chọn 10 file: 8 thành công, 2 lỗi; xem được lỗi riêng và xử lý lại 2 file mà không nạp lại 8 file thành công.
- [ ] Trong kho 40 tài liệu, thay 1 tài liệu: chỉ xử lý file thay, không quét/ingest lại 39 file khác.
- [ ] Upload file giống hệt thành tài liệu mới: báo trùng. Upload lại vào chính tài liệu đang READY: báo không thay đổi, không tạo version/job.
- [ ] Sửa một câu quan trọng: file thay khác hash được tiếp nhận, bản mới thành công rồi mới thay nguồn hỏi đáp.
- [ ] Bản thay lỗi: bản cũ tiếp tục dùng được. Sửa tags không tạo job ingestion.
- [ ] (Chỉ khi bật hạn mức) Chạm quota giữa lượt: file bị từ chối có lý do; không mất các file đã tiếp nhận thành công.

Đây là acceptance scenarios để review yêu cầu; chưa chạy test hoặc triển khai. Không đặt điều kiện nghiệm thu theo mức tiết kiệm embedding chưa đo được.

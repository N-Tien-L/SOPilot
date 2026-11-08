---
id: AUDIT-ingestion-business-cases-2026-10-20
title: "Khảo sát sơ bộ nghiệp vụ nhập và cập nhật SOP trước khi thiết kế ingestion"
status: draft
created: 2026-10-20
updated: 2026-10-20
author: "Owner"
type: audit
scope: ingestion
verdict: needs-user-validation
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/03-plans/tickets/V2-19-sop-extraction-corpus.md
  - docs/04-reports/AUDIT-ingestion-sop-data-2026-10-19.md
---

# Khảo sát nghiệp vụ ingestion SOP

> **Ghi chú 2026-10-21:** các quyết định phạm vi rút ra từ khảo sát này đã nằm trong PRD-V2 (FR-06..FR-09, FR-30, FR-31, UC-12); xem [AUDIT-markdown-normalization](AUDIT-markdown-normalization-and-preview-2026-10-21.md). Thân báo cáo giữ nguyên; các câu hỏi khách hàng ở §7 vẫn chưa được xác minh.

## 1. Mục đích và giới hạn

Owner yêu cầu tìm hiểu cách sử dụng thực tế trước khi quyết định tối ưu ingestion. Đây là khảo sát tài liệu công khai, chưa phải phỏng vấn khách hàng hay đo workload. Không thay đổi PRD, TECH, PLAN hoặc kết luận rằng incremental ingestion là cần thiết.

Đã có các thay đổi staged ở hai TECH-V2 và PLAN/ticket V2-03 khi bắt đầu khảo sát; báo cáo này không sửa những file đó.

## 2. Bằng chứng đã đọc

### S1 — Quy trình thực tế tại Việt Nam

[Đại học Vinh, QT.HCTH.01, ban hành 20/09/2023](https://vinhuni.edu.vn/upload/files/hcth/quytrinhiso/qt10%20hcth1.pdf), mục 5.1, 5.2.4.4 và 5.2.7.2:

- Có bước đề xuất, soạn/sửa, kiểm tra, phê duyệt và phân phối.
- Thay nội dung thì tăng lần ban hành và cập nhật lịch sử thay đổi.
- Khi phân phối bản mới, có thu hồi bản cũ; bản giữ tham khảo được đánh dấu riêng.

Đây là quy trình của một trường đại học, không đại diện cho mọi doanh nghiệp Việt Nam.

### S2 — SOP vận hành cụ thể

[EPA Microbiology Laboratory, ADM-02-05, revised 04-10-13](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10106NT.txt), mục 12.1, 12.5–12.7:

- Mã SOP thể hiện danh tính và revision.
- Bản sửa qua review/approval rồi mới được phát hành; bản cũ rút khỏi lưu hành.
- Có trường hợp thu hồi SOP không còn dùng và phục hồi với revision thích hợp.

Đây là một quy trình phòng thí nghiệm cụ thể, không phải số liệu về tần suất upload.

### S3 — Hướng dẫn quản lý chất lượng

[WHO, Documents and records](https://www.who.int/tools/quality-management-system-for-non-laboratory-settings/pillar-5-documents-and-records): tài liệu cần được duyệt trước sử dụng, rà soát và cập nhật, loại bản lỗi thời khỏi lưu hành. SOP và hướng dẫn công việc ngắn gọn là những loại tài liệu riêng trong bảng hướng dẫn.

[WHO LQSI, Master SOP](https://extranet.who.int/lqsi/node/75): có ví dụ mã SOP kèm version và phân biệt tài liệu, biểu mẫu, phụ lục liên quan.

## 3. Suy luận nghiệp vụ cần kiểm chứng

Trong các tổ chức có kiểm soát tài liệu, có thể phân biệt nhiều lần lưu bản nháp với một lần ban hành chính thức. Nếu SOPilot chỉ nhận bản được phép đưa vào hỏi đáp, số lần ingest có thể khác xa số lần người soạn bấm Save. Chưa có bằng chứng xác nhận khách hàng mục tiêu thực hiện như vậy.

Độ lớn thay đổi không quyết định tầm quan trọng: thay một thời hạn hoặc một điều kiện vẫn có thể đổi câu trả lời nghiệp vụ. Cần xác định bản được phép dùng và nguồn trích dẫn trước khi bàn về tiết kiệm embedding.

## 4. Danh sách case để discovery

Các case dưới đây là câu hỏi khảo sát, không phải hành vi đã được quan sát tại khách hàng SOPilot. S1–S3 hỗ trợ vòng đời ban hành/sửa/thu hồi; các thao tác upload là giả thuyết sản phẩm.

| Case | Tình huống cần hỏi hoặc quan sát | Điều cần chốt với người dùng |
|---|---|---|
| C01 | Đưa kho SOP hiện hành vào lần đầu | Bao nhiêu file, trang/file, định dạng, có trộn bản cũ/nháp không? |
| C02 | Thêm SOP vừa ban hành | Ai upload, bằng cách nào xác nhận đúng tài liệu? |
| C03 | Sửa một điều kiện, thời hạn hoặc người chịu trách nhiệm | Bản mới thay bản nào, khi nào được dùng trả lời? |
| C04 | Đổi nhiều bước hoặc tổ chức lại SOP | Vẫn cùng mã SOP hay là tài liệu mới? |
| C05 | Chỉ đổi bìa, logo, chữ ký, ngày rà soát hoặc bố cục | Có tăng lần ban hành không; cần cập nhật file/nguồn trích dẫn thế nào? |
| C06 | Cùng bản ban hành có cả Word và PDF | Bản nào là nguồn chính; có cần giữ cả hai không? |
| C07 | Người khác upload lại cùng file, hoặc retry sau mất mạng | Muốn trỏ tới tài liệu đã có hay tạo bản mới; có biết lần trước thành công không? |
| C08 | Upload nhầm bản cũ hoặc nhầm tài liệu để thay thế | Người dùng nhận biết và sửa sai thế nào? |
| C09 | Thu hồi SOP hoặc có bản mới chưa tới ngày hiệu lực | Khi nào ngừng trả lời theo bản cũ; có cần hẹn hiệu lực không? |
| C10 | Biểu mẫu/phụ lục thay đổi riêng | Quản lý như tài liệu độc lập hay một phần SOP? |
| C11 | Chỉ sửa category, tags, mô tả hoặc phạm vi đọc | Có thay file nội dung không; ai được phép sửa? |
| C12 | Nhiều SOP dùng chung template | Có bị nhầm là cùng tài liệu; người quản lý dựa vào mã, tên hay nội dung? |

## 5. Thông tin cần thu thập trước quyết định kỹ thuật

Phỏng vấn người giữ tài liệu và người sử dụng; xin xem một lần cập nhật gần nhất từ bản cũ đến bản mới. Với mỗi ví dụ, ghi người thực hiện, trigger, file đầu vào, mã/lần ban hành, thời điểm hiệu lực và kết quả mong muốn. Không chỉ hỏi người dùng có muốn tính năng hay không.

Thu thập số liệu thực: số tài liệu hiện hành, kích thước và số trang, số lần cập nhật theo khoảng thời gian, số người upload đồng thời, thời gian chờ chấp nhận được. Không suy ra workload từ chu kỳ review quy định trong hướng dẫn.

V2-19 hiện đo cấu trúc trích xuất từng file. Để khảo sát cập nhật, cần thêm các cặp bản cũ/bản mới thực và lý do thay đổi; việc này chưa được coi là thay đổi acceptance criteria đã duyệt. Bản tạo bằng cách cố ý sửa file phải gắn nhãn synthetic, không trình bày là lịch sử vận hành thật.

## 6. Hạn mức và lý do đầu tư tối ưu

Quota có thể giới hạn tổng tài nguyên của khách hàng. Việc trả tiền tạo động lực dùng hợp lý nhưng không chứng minh không có thao tác nhầm hoặc retry; chi phí nhà cung cấp còn phụ thuộc mô hình giá và tài nguyên dùng chung.

Không dùng các giả thuyết lạm dụng làm lý do mặc định xây pipeline phức tạp. Chỉ cân nhắc tối ưu thêm khi case hợp lệ đã được xác nhận và phép đo cho thấy thời gian chờ/chi phí vượt mức chấp nhận. Cache embedding đang có trong thiết kế V2; báo cáo này chưa đánh giá hiệu quả hoặc đề nghị bỏ/thêm cache.

## 7. Các câu hỏi mở

1. Nhóm khách hàng đầu tiên là ai, ai đang giữ kho SOP?
2. SOPilot nhận bản đã ban hành hay tham gia cả soạn/sửa/duyệt?
3. Phần nào bắt buộc có ở V2: thay bản ngay, ngày hiệu lực, thu hồi, lịch sử hoặc phục hồi?
4. Có thể xem những cặp SOP trước/sau thực tế nào, và số liệu cập nhật trong thời gian gần đây?

Chỉ chuyển các kết luận đã xác nhận thành đề xuất sửa PRD rồi mới điều chỉnh TECH/ticket. Nghiên cứu bàn giấy hiện chưa đủ để chốt thiết kế ingestion theo workload khách hàng.

## 8. Mô phỏng đa quy mô theo yêu cầu owner

Owner yêu cầu khảo sát nhiều quy mô. Các số bên dưới là kịch bản giả định để kiểm tra nghiệp vụ, không phải thống kê thị trường hoặc benchmark đã chạy. Số người chỉ mô tả bối cảnh; số file, độ dài và nhịp thay đổi mới trực tiếp tạo tải ingestion.

### 8.1 Các pha tải

1. Nạp kho ban đầu: lựa chọn nguồn hiện hành, đưa vào theo một hoặc nhiều đợt.
2. Vận hành thường ngày: thêm tài liệu, thay bản, sửa metadata, thu hồi.
3. Đợt thay đổi tập trung: mở phòng ban/chi nhánh, đổi template, rà soát chính sách; có thể lớn sau onboarding.
4. Xử lý ngoại lệ: file lỗi, upload nhầm, gửi lại do mất mạng.

Phải phân biệt xử lý phần tài liệu mới/đổi trong kho với chỉ xử lý những chunk đổi trong một file. Hai mức tối ưu khác nhau; cần thứ nhất không tự động chứng minh cần thứ hai.

### 8.2 Bốn kịch bản giả định

| Kịch bản | Kho ban đầu | Một tháng vận hành giả định | Đợt đặc biệt | Nhu cầu cần kiểm chứng |
|---|---|---|---|---|
| A: cá nhân, 1 người | 20 file MD/PDF, khoảng 100 trang tương đương | Thêm 2 file, thay 3 file | Chuyển thêm một thư mục tài liệu | Thao tác đơn giản, nhận biết file lỗi và trùng |
| B: nhóm wiki, 10 người | 80 trang/file Markdown, khoảng 240 trang tương đương | Thêm 4 file, 20 lần cập nhật trên 10 file | Đổi cấu trúc wiki, đường dẫn hoặc heading của nhiều trang | Mốc nội dung được công bố; cách chọn file thay; có thực sự cần kết nối nguồn không? |
| C: doanh nghiệp Word/PDF, 80 người | 400 tài liệu hiện hành, khoảng 3.200 trang | Thêm 5 file, thay 8 file | Thay logo/template của 100 file | Tiến độ theo file, phân biệt bản nguồn, giữ bản dùng được khi bản mới lỗi |
| D: tổ chức nhiều đơn vị, 500 người | 1.500 tài liệu, khoảng 15.000 trang | Thêm 15 file, thay 30 file | Thêm đơn vị với 200 tài liệu, hoặc sửa chính sách hàng loạt | Phân đợt nhập, phòng ban/quyền, khả năng vận hành trong lúc nạp |

Không dùng các mức giả định này để định giá hoặc cam kết hiệu năng. Với B, 20 lần cập nhật có thể tạo 20 lần ingest nếu công bố từng lần, hoặc ít hơn nếu bản nháp được gộp trước công bố. Chưa mặc định debounce, tự đồng bộ wiki, webhook hoặc đồng bộ thư mục là tính năng V2.

### 8.3 Diễn tập cụ thể cho C

- Trước nạp: quản lý chọn 400 tài liệu hiện hành từ kho nguồn. Kho nguồn có thể lớn hơn; chọn bản hiện hành là bước nghiệp vụ, không thể chỉ giải quyết bằng hash.
- Đợt đầu: gửi 400 file theo nhiều lượt. Giả sử 390 thành công, 10 lỗi định dạng/scan: hiển thị kết quả từng file; sau khi khắc phục chỉ gửi lại 10 file. Không bắt đầu lại 390 file thành công. Đây là nhu cầu đề xuất, chưa phải xác nhận UI V2 có nhập hàng loạt.
- Tuần sau: thêm 2 SOP, thay 1 SOP từ thời hạn 3 ngày thành 5 ngày, sửa tags của 5 tài liệu và thu hồi 1 SOP. Chỉ 3 đầu vào file mới cần xử lý nội dung; tags và thu hồi là thao tác quản lý. Trong V2 hiện tại, thu hồi có thể phải thực hiện qua xóa; trạng thái thu hồi riêng chưa được chốt.
- Với SOP được thay: bản cũ phục vụ đến khi bản mới xử lý thành công; cần kiểm chứng xem người dùng muốn kích hoạt ngay hay theo ngày hiệu lực. Trạng thái READY kỹ thuật không tự chứng minh văn bản đã có hiệu lực nghiệp vụ.
- Nếu file 2 trang có câu sửa quan trọng, ưu tiên trả lời đúng bản. Nếu phải xử lý lại cả 2 trang mà thời gian chờ chấp nhận được, chưa có lý do nghiệp vụ để xây incremental chunking.
- Nếu 100 file chỉ đổi template, cần đo chi phí và độ trễ của đợt đó. Dù phần trả lời giữ nguyên, file mới có thể đổi vị trí trang, nên không mặc định tái sử dụng mọi vị trí trích dẫn cũ.

### 8.4 Ba dạng gửi lại cần tách biệt

| Dạng | Ý nghĩa | Kết quả nghiệp vụ đề xuất để xác minh |
|---|---|---|
| Gửi lại cùng yêu cầu do timeout/mạng | Một thao tác bị lặp | Trả kết quả/trạng thái thao tác trước, tránh nhân đôi job |
| Tạo tài liệu mới bằng file đã có | Có thể thao tác nhầm | Báo tài liệu đã tồn tại theo chính sách SHA-256 trong workspace |
| Chủ động thay phiên bản của tài liệu | Hành động nghiệp vụ mới | Không chặn revision có ý nghĩa chỉ vì gần giống; upload y hệt có cần tạo revision hay báo không đổi cần xác minh |

V2-12 hiện cho phép bản mới cùng tài liệu giống bản cũ. Đây là mô tả phạm vi hiện có, không phải bằng chứng khách hàng cần tạo revision cho mọi lần upload y hệt.

### 8.5 Ví dụ định lượng để thấy hai mức tối ưu

Giả sử kho có 400 file, mỗi file 20 chunk, và một đợt chỉ thay 3 file. Để minh họa, giả sử sau chia lại mỗi file vẫn có 20 chunk và cache trống ở các chunk thay đổi:

- Nạp lại toàn kho: 8.000 chunk được xét nếu pipeline cho phép thao tác đó.
- Chỉ nạp 3 file được chọn thay: 60 chunk được xét; không đụng 397 file khác.
- Trong 60 chunk, nếu đo thấy 54 có cùng đầu vào embedding/model/revision và còn cache thì chỉ tính 6 vector mới; nếu không có cache hit thì tính 60.

Không dự đoán tỷ lệ hit 90%; 54/60 chỉ là nhánh minh họa. Chưa có thời gian xử lý, chi phí, RAM hoặc kết quả so sánh file thật. Tiết kiệm ở mức chọn file thay đã có ích ngay cả khi không có tái sử dụng embedding trong file.

### 8.6 Đối chiếu phạm vi V2

PRD FR-09 mặc định giới hạn 50 tài liệu/200 MB mỗi workspace, có cấu hình. PRD §5 ghi import hàng loạt ngoài phạm vi. Vì vậy B/C/D là kịch bản khám phá sản phẩm; không thể tuyên bố V2 đã đáp ứng nhập kho quy mô đó hoặc có nút upload thư mục. Tăng quota không tự cung cấp luồng nhập hàng loạt, thời gian xử lý hoặc năng lực máy.

Đề xuất BA cần xem xét tiếp: có cho người dùng chọn nhiều file, chia đợt theo quota và xem lỗi từng file ở V2 không? Đây là khoảng lệch giữa nhu cầu onboarding đang khảo sát và scope hiện tại, cần quyết định sản phẩm trước khi sửa TECH.

## 9. Nguồn bổ sung và việc còn thiếu

[GitLab, Editing the Handbook](https://handbook.gitlab.com/handbook/about/editing-handbook/) mô tả cách đề xuất, review và merge thay đổi handbook; [Handbook Development](https://handbook.gitlab.com/docs/development/) mô tả nguồn Markdown. Điều này hỗ trợ phân biệt commit/lưu nháp với nội dung được công bố, không chứng minh nhịp cập nhật của nhóm nhỏ.

[Microsoft, File share migration](https://learn.microsoft.com/en-us/sharepointmigration/mm-fileshare-copy-to-migrations) mô tả các lượt migration và incremental cho file share. Đây là ví dụ công cụ chuyển kho có nhiều lượt, không phải bằng chứng SOPilot cần đồng bộ tự động hoặc cập nhật theo chunk.

Cần bổ sung quan sát khách hàng, các cặp file revision thật và phép đo trên máy mục tiêu. Chưa có căn cứ để chốt throughput, quota mới, connector nguồn hoặc incremental ingestion trong tài liệu.

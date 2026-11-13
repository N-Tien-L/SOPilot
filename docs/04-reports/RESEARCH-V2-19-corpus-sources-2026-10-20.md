---
id: RESEARCH-V2-19-CORPUS-SOURCES-2026-10-20
title: "Nguồn đề xuất cho corpus trích xuất SOP V2-19"
status: final
created: 2026-10-20
updated: 2026-10-20
author: "Owner"
type: research
scope: "V2-19: lựa chọn nguồn corpus"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-19-sop-extraction-corpus.md
  - docs/04-reports/AUDIT-ingestion-sop-data-2026-10-19.md
  - docs/archive/01-requirements/PRD-V2-ingestion-mvp-scope.md
---

# Nguồn corpus V2-19

## 1. Khuyến nghị

Ưu tiên **PDF ISO của cơ quan Việt Nam + SOP EPA + Markdown có license rõ**. Thêm TXT thực tế và PDF scan cho các ca biên. Chọn tài liệu theo độ phủ cấu trúc, không chỉ theo chủ đề hoặc số lượng. Đây là nghiên cứu lựa chọn nguồn; chưa thu thập corpus, gán nhãn hay nghiệm thu ticket.

Phạm vi theo ticket hiện tại: VI/EN, PDF có lớp chữ, MD, TXT; 20–50 file, ít nhất 5 họ tài liệu, thêm 2–3 PDF scan kiểm tra từ chối. DOCX ngoài MVP. Bộ này tách khỏi RQ1–RQ5 và corpus retrieval GitLab đã thiết kế trước đó.

## 2. PDF ISO tiếng Việt: đáng lấy đầu tiên

Các URL dưới đây đã mở dưới dạng PDF bằng công cụ web ngày 20/10/2026 và trả được nội dung chữ. **Điều này chưa chứng minh PDF có text layer nguyên bản** vì dịch vụ web có thể xử lý tài liệu trước khi trả kết quả. Khi acquisition cần đo bằng parser local không OCR, kiểm tra Unicode và xem trang thật trước khi chốt gold. Số trang dưới đây là số trang PDF do công cụ web báo, không phải số in ở footer.

| Ưu tiên | Tài liệu / nguồn trực tiếp | Trang PDF | Giá trị cho corpus |
|---|---|---:|---|
| A | [Sở Xây dựng Ninh Bình — QT-01 kiểm soát thông tin](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-01_kiem_soat_thong_tin_lap_van_ban.pdf) | 14 | Heading nhiều cấp; bảng quy trình có bảng lồng; header metadata; phụ lục. |
| A | [SXD Ninh Bình — QT-02 rủi ro và cơ hội](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-02_quy_trinh_quan_ly_rui_ro_va_co_hoi.pdf) | 10 | Bổ sung mẫu cùng cơ quan; cần rà trang và nhãn bảng khi acquisition. |
| A | [SXD Ninh Bình — QT-03 đánh giá nội bộ](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-03__quy_trinh_danh_gia_noi_bo_he_thong_qlcl.pdf) | 13 | Đối chiếu với SOP đánh giá nội bộ của cơ quan khác. |
| A | [SXD Ninh Bình — QT-04 sự không phù hợp và khắc phục](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-04_quy_trinh_kiem_soat_skph_va_hdkp.pdf) | 7 | Mẫu ngắn hơn, giảm công gán nhãn ban đầu. |
| A | [Cảng vụ Thái Bình — QT.01 kiểm soát tài liệu](https://cangvuhanghaithaibinh.gov.vn/images/uploads/attach/QT.01%20Quy%20tr%C3%ACnh%20ki%E1%BB%83m%20so%C3%A1t%20th%C3%B4ng%20tin%20d%E1%BA%A1ng%20v%C4%83n%20b%E1%BA%A3n%20%28t%C3%A0i%20li%E1%BB%87u%2C%20h%E1%BB%93%20s%C6%A1%29%20%28Repaired%29-converted.pdf) | 10 | Mục lục, bảng phê duyệt/sửa đổi, heading sâu; có đoạn mô tả bố cục SOP dễ bị nhận nhầm thành heading thật. |
| A | [Cảng vụ Thái Bình — QT.03 đánh giá nội bộ](https://cangvuhanghaithaibinh.gov.vn/images/uploads/attach/QT.03%20Quy%20tr%C3%ACnh%20%C4%90%C3%A1nh%20gi%C3%A1%20n%E1%BB%99i%20b%E1%BB%99-converted.pdf) | 13 | Bổ sung template khác; không coi cùng tên quy trình là cùng file. |
| A | [Cảng vụ Thái Bình — QT.05 xem xét lãnh đạo](https://cangvuhanghaithaibinh.gov.vn/images/uploads/attach/QT.05%20Quy%20tr%C3%ACnh%20Xem%20x%C3%A9t%20l%C3%A3nh%20%C4%91%E1%BA%A1o-converted.pdf) | 11 | Bảng bước kéo qua nhiều trang; header chen giữa nội dung bảng; metadata lặp. |
| A | [Thanh tra Ninh Bình — QT 06/TTr tổ chức cuộc thanh tra](https://thanhtra.ninhbinh.gov.vn/public/userfiles/3541.pdf) | 17 | Bảng bước và mẫu kèm theo; phân biệt trang vật lý với footer dạng 1/7. |

[Trang danh mục SXD Ninh Bình](https://soxaydung.ninhbinh.gov.vn/tieu-chuan-iso/quy-trinh-co-ban-theo-tieu-chuan-iso-90012015-14.html) liên kết trực tiếp bốn PDF trên. Danh mục Cảng vụ từng trả 503, nhưng ba PDF trực tiếp mở được. Các PDF Quảng Ninh tìm được qua search chưa mở thành công nên chỉ là nguồn dự phòng, chưa đưa vào danh sách ưu tiên.

**Quyền sử dụng:** chưa xác minh được giấy phép tái phân phối riêng cho tám PDF ISO này. Không gắn nhãn CC hoặc public domain từ tên miền `.gov.vn`. Khởi đầu bằng manifest và script tải; quyền dùng và quyền phân phối file cần được ghi riêng. Manifest/script không tự tạo quyền sử dụng nếu nguồn có hạn chế. Không thu nguyên văn tiêu chuẩn ISO thương mại chỉ vì SOP có dẫn chiếu tiêu chuẩn đó.

## 3. Hành chính: NĐ 30 là mốc tham chiếu, cần chọn đúng bản PDF

[Trang Chính phủ của NĐ 30/2020/NĐ-CP](https://vanban.chinhphu.vn/default.aspx?docid=199378&pageid=27160) xác nhận ngày ban hành 05/03/2020 và liên kết [PDF ký số chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30.signed.pdf). Công cụ web mở PDF 76 trang nhưng trả **0 dòng chữ**. Chưa đủ bằng chứng kết luận toàn file là scan; cũng chưa thể xếp vào nhóm PDF text thành công. Cần parser local kiểm tra từng trang; nếu ảnh thuần thì dùng làm ứng viên kiểm tra từ chối.

Trang Chính phủ yêu cầu ghi nguồn khi phát hành lại thông tin; đây không phải tuyên bố CC cho mọi tài sản liên kết. Lưu điều kiện nguồn và quyền của file cụ thể khi acquisition.

Để đo Chương/Điều/Khoản, cần bổ sung 2–3 **PDF text thật** chứa quy chế/quy định hành chính; bản HTML trên cổng văn bản chỉ giúp đối chiếu nội dung. Không in HTML ra PDF rồi gọi đó là PDF gốc thực tế. Không cần tài liệu còn hiệu lực để đo layout, nhưng phải ghi phiên bản/ngày và không dùng corpus này làm tư vấn quy định hiện hành.

## 4. Tiếng Anh và MD/TXT

Xem [nghiên cứu nguồn EN](RESEARCH-V2-19-english-sources-2026-10-20.md) để có URL file, license evidence và phần đã/chưa kiểm chứng.

- **EPA actual SOP:** ưu tiên Soil Sampling và Field Sampling Quality Control; dùng để đo heading đánh số, metadata revision/effective date và header/footer. EPA QA/G-6 là hướng dẫn viết SOP, phù hợp làm nguồn thiết kế nhãn hoặc một mẫu manual; không thay toàn bộ SOP thực tế bằng tài liệu hướng dẫn.
- **GitLab Handbook:** hợp miền tác nghiệp nhân viên và đã có nghiên cứu nội bộ tại [HANDOFF dataset](RESEARCH-02-dataset-and-labeling.md). Chọn vài file MD ở commit cố định; kiểm license nội dung, include và frontmatter. Nếu trùng nguồn retrieval, lưu ID/manifest riêng và không gộp kết quả đánh giá.
- **curl INSTALL.md / Kubernetes task Markdown:** mẫu kỹ thuật mở bổ sung heading, list, code và template. Chỉ lấy ít mẫu vì không đại diện SOP doanh nghiệp. Không loại shortcode trước khi đo rồi báo parser tự xử lý được shortcode.
- **curl RELEASE-NOTES:** ứng viên TXT tự nhiên, cấu trúc không theo SOP chuẩn. Lưu bytes gốc; nếu đổi tên thành `.txt`, ghi thao tác trong manifest. Không chuyển mọi MD thành TXT để tăng số tài liệu độc lập.

EPA là nguồn ưu tiên hơn GMP SOP thương mại ở bước này vì có SOP hoàn chỉnh công khai và thông tin kiểm soát tài liệu. Vẫn cần kiểm quyền từng file; không mặc định mọi tài liệu EPA là public domain. Các bộ benchmark layout tổng quát có thể tham khảo sau, nhưng không thay độ phủ SOP tiếng Việt của V2-19.

## 5. Phân bổ đề xuất: 24 file

Đây là **chỉ tiêu tuyển chọn**, chưa phải 24 file đã thu đủ hoặc đã xác minh quyền.

| Họ | Số file | Điều kiện chọn |
|---|---:|---|
| ISO Việt Nam | 8 | Danh sách §2, xác nhận text layer local trước khi nhận. |
| Hành chính VI | 3 | PDF text có Chương/Điều/Khoản, ít nhất hai bố cục; còn thiếu file đã chốt. |
| EPA SOP EN | 5 | Hai ứng viên đầu đã khảo sát; chọn thêm ba sau kiểm file thực tế. |
| Wiki/Markdown | 4 | Ưu tiên hai GitLab và hai mẫu kỹ thuật, tránh tất cả đều cùng template. |
| Không theo chuẩn / TXT | 2 | Một TXT kỹ thuật; một tài liệu VI thực tế do owner chọn hoặc cho phép dùng. |
| Scan để từ chối | 2 | File ảnh thuần đã xác nhận; ứng viên NĐ 30 cần kiểm chứng. |
| **Tổng** | **24** | 22 mẫu xử lý thành công dự kiến + 2 mẫu từ chối. |

Phải đo từng họ thay vì chỉ trung bình toàn corpus. Giữ các tài liệu cùng template trong cùng nhóm khi chia dev/holdout để tránh học thuộc bố cục. Mẫu biến đổi nhân tạo (xóa text layer, chuyển MD→TXT) được phép làm fixture bổ sung có provenance, không tính như tài liệu thật độc lập để lấp đủ 20 file.

## 6. Những việc cần làm khi triển khai ticket

1. Chốt danh sách cụ thể và owner chọn các nguồn còn thiếu; chưa thay đổi trạng thái V2-19 trong lần nghiên cứu này.
2. Lập `datasets/extraction/SOURCES.md`: ID, source/landing/download URL, đơn vị phát hành, ngôn ngữ/họ/định dạng, license và evidence URL, quyền tái phân phối, retrieved_at UTC, SHA-256, số trang vật lý, text-layer probe, biến đổi, trạng thái owner review.
3. Với web/git: ghim commit hoặc lưu snapshot/hash; ngày truy cập và URL nhánh động chưa đủ tái lập. Với PDF: lưu hash bytes, đừng lấy filename làm revision.
4. Gán gold từ trang gốc đã xem: heading có cấp/thứ tự; bảng có vị trí/cột; phần khung cần bỏ; metadata có evidence. Phân biệt ngày ban hành với ngày hiệu lực; không điền ngày hiệu lực chỉ vì có ngày trên header.
5. Với scan, gold là quyết định từ chối và lý do. Không tính heading/table F1 bằng 0 của scan vào chất lượng xử lý PDF text.
6. Owner duyệt từng nhãn theo acceptance criteria. Nghiên cứu này chưa có nhãn vàng, benchmark parser hoặc bằng chứng nghiệm thu V2-19.

## 7. Giới hạn xác minh

Đã đọc ticket, scope MVP và audit liên quan; đã mở các nguồn chính thức nêu trên qua web. Chưa tải bytes vào corpus, chưa chạy parser không OCR, chưa xác minh layout bằng ảnh trang cho các PDF ISO, chưa chốt quyền sử dụng từng PDF, chưa chọn đủ file hành chính/TXT VI/scan. Các nhận xét layout ISO dựa trên nội dung web trả theo trang và cần xác nhận trực quan trước gán nhãn. Không sửa ticket/PLAN hay các file đang có thay đổi của owner. Không chạy build/test vì chỉ thêm báo cáo nghiên cứu.

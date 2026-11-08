---
id: RESEARCH-V2-19-english-sources-2026-10-20
title: "Nguồn tiếng Anh cho corpus trích xuất V2-19"
status: final
created: 2026-10-20
updated: 2026-10-20
author: "Owner"
type: research
scope: tests
refs:
  - docs/03-plans/tickets/V2-19-sop-extraction-corpus.md
---

# Khuyến nghị

Ưu tiên EPA LSASD cho SOP PDF thật, curl cho Markdown dễ dùng và văn bản thuần, Kubernetes cho Markdown có cấu trúc phức tạp. Đây là danh sách ứng viên đã kiểm tra trực tuyến ngày 2026-10-20; chưa tải corpus, chạy extractor hay duyệt nhãn vàng. Không thay đổi trạng thái V2-19.

## 1. EPA LSASD: SOP PDF ứng viên

[Danh mục chính thức](https://www.epa.gov/quality/quality-system-and-technical-procedures-lsasd-field-branches) tập hợp quy trình lấy mẫu, đo hiện trường và quản lý chất lượng. Tài liệu tải về là bản không được kiểm soát; nguồn có thể được cập nhật. Corpus cần giữ ngày tải, mã tài liệu, revision, effective date và SHA-256.

| Ứng viên | Bằng chứng đã đọc từ PDF | Giá trị cho V2-19 |
|---|---|---|
| [Soil Sampling PDF](https://www.epa.gov/sites/default/files/2015-06/documents/Soil-Sampling.pdf) | 30 trang; LSASDPROC-300-R5; hiệu lực 2023-04-22 | Heading đánh số nhiều cấp, TOC, bảng tóm tắt phương pháp, hình, revision history và header/footer lặp |
| [Field Sampling Quality Control PDF](https://www.epa.gov/sites/default/files/2017-07/documents/field_sampling_quality_control011_af.r5.pdf) | 23 trang; nội dung là LSASDPROC-011-R7; hiệu lực 2023-04-22 | Heading sâu, metadata, TOC, các khối phê duyệt và revision history |

Web parser đã trả được nội dung và phân trang của cả hai PDF. Cần kiểm tra bytes bằng parser local không OCR để xác nhận lớp chữ nguyên bản; chưa có kết quả chất lượng của extractor SOPilot. Đặc biệt, filename PDF thứ hai có `r5` nhưng nội dung là `R7`: phải lấy revision từ tài liệu. [Trang công bố QC](https://www.epa.gov/quality/field-sampling-quality-control) cũng ghi R7.

Quyền: chưa gắn nhãn `public-domain` hoặc open license cho hai file. [EPA Disclaimers](https://www.epa.gov/web-policies-and-procedures/epa-disclaimers) có nội dung cho phép dùng/phân phối cho một số mục đích phi thương mại, khoa học, giáo dục, nhưng ngay đầu trang nói các disclaimer là danh mục và không tự động áp dụng cho mọi tài liệu. Trang cũng lưu ý từng tài liệu có thể có điều kiện riêng. Khuyến nghị ban đầu: **manifest + script tải**, ghi `license_status: needs-document-level-review`; quyết định quyền cần dựa vào tài liệu/tuyên bố thực sự áp dụng. Public access không đồng nghĩa giấy phép mở.

Nguồn dự phòng: [Document Control](https://www.epa.gov/quality/technical-procedures-laboratory-services-and-applied-science-division-field-quality-system) công bố LSASDDPROC-1000-R3 ngày 2024-01-08, nhưng PDF không fetch được trong lần kiểm tra này; chưa đưa vào bộ ưu tiên. Một số URL Sediment Sampling trả 502; không dùng như nguồn đã xác minh bytes.

## 2. curl: Markdown và văn bản thuần có giấy phép rõ

| Ứng viên | Dạng thật | Giá trị |
|---|---|---|
| [docs/INSTALL.md](https://raw.githubusercontent.com/curl/curl/master/docs/INSTALL.md) | Markdown nguyên bản, khai báo `SPDX-License-Identifier: curl` trong file | Nhiều cấp heading, danh sách, code block, HTML details; quy trình cài đặt thật |
| [RELEASE-NOTES](https://raw.githubusercontent.com/curl/curl/master/RELEASE-NOTES) | Văn bản thuần nguyên bản, file upstream không có phần mở rộng | Mẫu không theo chuẩn SOP: nhãn section bằng văn bản, danh sách và thống kê; có thể lưu nguyên bytes thành `.txt`, ghi rõ đổi tên, không đổi nội dung |

[COPYING](https://raw.githubusercontent.com/curl/curl/master/COPYING) cho phép dùng, sao chép, sửa và phân phối, yêu cầu giữ thông báo bản quyền và permission notice. [REUSE.toml](https://raw.githubusercontent.com/curl/curl/master/REUSE.toml) chỉ rõ `RELEASE-NOTES` mang giấy phép `curl`. Có thể commit snapshot cùng các notice theo điều kiện giấy phép. Pin commit cụ thể trước khi tải; `master` chỉ là đường dẫn discovery. Nếu owner yêu cầu upstream phải có đuôi `.txt`, RELEASE-NOTES chưa đáp ứng điều kiện hẹp đó; không trình bày nó như một file `.txt` nguyên gốc.

## 3. Kubernetes: Markdown thực tế có shortcode

Chọn 1–2 file:

- [Safely Drain a Node — raw Markdown](https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/administer-cluster/safely-drain-node.md): YAML frontmatter, heading, bước thao tác, fenced code, Hugo shortcode và ghi chú.
- [Labels and Selectors — raw Markdown](https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/concepts/overview/working-with-objects/labels.md): tài liệu khái niệm để bổ sung biến thể wiki/docs.

[LICENSE của website repo](https://raw.githubusercontent.com/kubernetes/website/main/LICENSE) là CC-BY-4.0. Khi chia sẻ phải giữ attribution, thông báo/đường dẫn giấy phép và ghi thay đổi. Đây là giấy phép tài liệu website, không suy từ Apache license của Kubernetes code. [Hướng dẫn chính thức](https://kubernetes.io/docs/contribute/new-content/) xác nhận nguồn viết bằng Markdown và build bằng Hugo. Pin commit và giữ bản nguồn: nhãn heading phải phân biệt shortcode với heading thông thường, không âm thầm render thành HTML rồi gọi đó là Markdown gốc.

## 4. Cách dùng trong bộ nhỏ

Khởi đầu 2 PDF EPA + 1 MD curl + 1–2 MD Kubernetes + 1 TXT curl; mở rộng EPA sau khi kiểm tra từng file. Tập EN này chưa phủ ISO 9001 tiếng Việt, hành chính, PDF scan và các trường hợp chữ Việt. Đừng dùng nhiều SOP EPA cùng template để thay cho độ đa dạng cấu trúc. Nhãn phải do owner duyệt, không tự coi TOC là nhãn vàng vì TOC và nội dung có thể khác nhau.

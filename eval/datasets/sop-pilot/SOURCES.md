# Nguồn pilot truy xuất V2-06

Ngày chuẩn bị local: 2026-10-25. Đây là pilot bổ sung SOP VI vào nguồn GitLab đã nghiên cứu; chưa freeze corpus nghiên cứu cuối. Không dịch corpus EN sang VI để tăng số tài liệu.

## GitLab Handbook: text CC-BY-SA-4.0

Attribution: GitLab và các tác giả đóng góp GitLab Handbook. Nguồn nội dung handbook theo [External use](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook); bản raw bằng chứng ở cùng commit được tải và hash trong `acquisition.lock.json` (doc `gitlab-license`, không index). Giấy phép: [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/).

Commit chung: `4684d72f27f3401d3ae72a26d72ae46eaeaab929` (snapshot cố định, không tuyên bố mới nhất). Thay đổi: trích allowlist section, bỏ frontmatter/email template, NFC/LF; câu hỏi/đáp án VI và nhãn do Codex soạn, chưa được owner duyệt. Nội dung text trích và phần chuyển thể từ GitLab giữ CC-BY-SA-4.0; không dùng ảnh/logo hoặc nội dung nguồn bên thứ ba liên kết. Đây không phải thay giấy phép code SOPilot.

| Doc | Nguồn immutable | Raw SHA-256 |
|---|---|---|
| gitlab-buddies | [raw](https://gitlab.com/gitlab-com/content-sites/handbook/-/raw/4684d72f27f3401d3ae72a26d72ae46eaeaab929/content/handbook/people-group/general-onboarding/onboarding-buddies.md) | `436321d3da0cfe9b46644bce434e67faf3836eb1adcc48de8faaefd44a841adf` |
| gitlab-meetings | [raw](https://gitlab.com/gitlab-com/content-sites/handbook/-/raw/4684d72f27f3401d3ae72a26d72ae46eaeaab929/content/handbook/company/culture/all-remote/meetings.md) | `06ed4f5d6a6b025ba86e37e0da33b524f2e9a2d9ead42bd5e73bd4441f775ac3` |
| gitlab-license | [raw](https://gitlab.com/gitlab-com/content-sites/handbook/-/raw/4684d72f27f3401d3ae72a26d72ae46eaeaab929/content/handbook/about/handbook-usage.md) | `c34fd5a7218ee3314650af8d8ded55b67c386ad7a751ad317b2b9c8f9886dbe5` |

Allowlist: GitLab Buddies — `Buddy Responsibilities`, `Managers: Who should I pick as an Onboarding Buddy?`; Meetings — ba mục before/during/after. Giữ nguyên điều kiện/ngoại lệ; không lấy nội dung email mẫu và không mở link phụ để suy thêm quy tắc.

## SOP tiếng Việt: nhánh thử nghiệm trên nguồn thật

`nb-qt02` (Quản lý rủi ro và cơ hội) và `nb-qt03` (Đánh giá nội bộ hệ thống quản lý chất lượng), Sở Xây dựng Ninh Bình, phiên bản ngày ban hành 05/11/2020, lần ban hành 01. Nguồn và SHA-256 bytes PDF nằm trong [manifest extraction](../../../datasets/extraction/pilot/manifest.json) và [SOURCES extraction](../../../datasets/extraction/SOURCES.md). Canonical text dùng pypdf 6.21.0, không OCR, không phục hồi cấu trúc hoặc dịch. Chưa xác minh quyền tái phân phối từng PDF: raw/canonical đầy đủ chỉ lưu local, không commit; không mặc định `.gov.vn` là CC. Các nhãn/quote ngắn phục vụ đối chiếu, không cấp quyền phân phối lại toàn tài liệu.

Hash canonical, source mapping và phiên bản normalizer: [manifest](manifest.json), [page map](page-map.json). Canonical không chứa câu hỏi/gold/reference answer. Không trộn số đo extraction với RQ retrieval; reuse nguồn chỉ thông qua manifest riêng.

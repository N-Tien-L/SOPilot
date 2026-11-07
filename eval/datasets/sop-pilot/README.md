# Pilot V2-06: corpus thật VI/EN và 24 câu nháp

Đợt đầu để owner duyệt công gán nhãn: 4 tài liệu (2 PDF SOP VI, 2 trang Markdown GitLab EN), 12 ý / 24 câu, 16 span. Mọi câu là `draft`, toàn bộ thuộc **dev**. Có 20 câu answerable, 4 câu âm, 12 câu cross-lingual (cả VI→EN và EN→VI). Phủ cả 7 `query_types`. Chưa có test, gold được owner duyệt hoặc kết quả RQ.

Phạm vi này giữ yêu cầu corpus VI/EN của ticket hiện hành. Handoff GitLab cũ là phương án corpus EN với query EN/VI, không tự thay tiêu chí song ngữ của ticket. Pilot không chốt quy mô cuối 100/240 câu; sau khi duyệt mới ước lượng phần mở rộng trong khả năng owner. Hai câu dịch của một ý không được đếm là hai ý độc lập.

## Tái lập

Từ `eval/`, dùng pypdf **6.21.0** (phiên bản đã tạo canonical/hash/offset; không nâng âm thầm):

```powershell
./.venv/Scripts/python.exe -m sopilot_eval.acquire --sources ../datasets/extraction/pilot/sources.json
./.venv/Scripts/python.exe -m sopilot_eval.acquire --sources datasets/sop-pilot/sources.json
./.venv/Scripts/python.exe -m sopilot_eval.prepare_pilot --dataset datasets/sop-pilot --extraction-dataset ../datasets/extraction/pilot
./.venv/Scripts/python.exe -m sopilot_eval.dataset --dataset datasets/sop-pilot
./.venv/Scripts/python.exe -m sopilot_eval.dataset --dataset datasets/sop-pilot --require-reviewed
```

Lệnh cuối xanh từ 2026-11-01 (owner đã duyệt); nó phải đỏ lại nếu câu/span bị sửa mà chưa duyệt lại. Hai acquisition hỗ trợ `--offline` để kiểm cache/hash, không gọi mạng. Builder không ghi đè artifact đã bị sửa; khi sửa seed/nhãn cần cập nhật có chủ đích, không xóa review log để dựng lại draft. Không mở `.env` hoặc cần API key. GitLab pin cùng commit ở `sources.json`; nguồn PDF pin theo SHA-256 trong lock của extraction.

Canonical EN lấy nguyên các section allowlist, bỏ frontmatter và email template trong details, giữ caveat cùng danh sách, không mở nội dung các link phụ. Canonical VI là **text inventory pypdf được nối theo trang và chuẩn hóa NFC/whitespace**, không phải Markdown có cấu trúc từ Docling. `page-map.json` giữ trang vật lý và khoảng ký tự. Trước RQ chính thức phải rebase canonical/spans theo docproc V2-20/V2-22 và duyệt/version lại; không dùng output thăm dò này như chất lượng parser hoặc scorer span-aware hoàn chỉnh.

`expected` do builder suy ra từ `evidence_sets`; gold là span AND/OR, không duy trì doc/page thủ công. Câu âm có `evidence_sets=[]` và đáp án tham chiếu trống; `corpus_lang` của câu âm là hướng kiểm dự kiến, không khẳng định tồn tại bằng chứng. `negative-audit.draft.jsonl` chỉ là ghi chú agent tìm trên bốn tài liệu, owner còn phải kiểm ngữ nghĩa toàn corpus trước freeze. Khi mở rộng corpus phải audit lại câu âm.

## Duyệt

Mở [REVIEW.md](REVIEW.md): mỗi ý có VI/EN, hai đáp án nháp, quote, offset và nguồn/trang. 24 câu do Codex soạn, 0 câu bị loại ở giai đoạn tạo pilot; chưa dùng model đầu ra làm judge. **2026-11-01: owner duyệt 24/24 câu** qua `eval/review_ui/server.py` (0 loại, 0 sửa); `review.jsonl` có 24 bản ghi, `--require-reviewed` xanh. Không chỉnh `review_status` hoặc điền reviewer giả bằng tay; sửa câu/span phải duyệt lại.

Sau duyệt pilot: sửa/loại câu, chốt quy mô corpus thật, bổ sung đa dạng cấu trúc và câu hỏi; chia theo nhóm policy/evidence và giữ cặp VI/EN cùng split; chốt test trước chạy mô hình. Không dùng test chỉnh ngưỡng.

Quyền và attribution ở [SOURCES.md](SOURCES.md). Nội dung PDF VI canonical nằm local, bị gitignore vì quyền tái phân phối chưa được xác minh. Không force-add corpus đó. Các file GitLab text và dữ liệu chuyển thể từ chúng theo CC-BY-SA-4.0; code repo không đổi giấy phép.

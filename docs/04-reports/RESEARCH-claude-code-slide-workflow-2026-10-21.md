---
id: RESEARCH-claude-code-slide-workflow-2026-10-21
title: "Nghiên cứu Claude Code và PPT Master cho slide chuyên nghiệp"
status: final
created: 2026-10-21
updated: 2026-10-21
author: "Owner"
type: research
scope: presentation-tooling
verdict: recommended-for-pilot
---

# Claude Code và PPT Master: nghiên cứu và quy trình đề xuất

Ngày tra cứu: 2026-10-21. Đây là nghiên cứu tài liệu và trải nghiệm cộng đồng, chưa phải benchmark tự chạy hoặc kiểm định chất lượng của deck xuất thực tế. Không cài đặt công cụ trong lần nghiên cứu này. Các quy tắc thiết kế và prompt bên dưới là đề xuất biên tập của người nghiên cứu, không phải kết luận đồng thuận đã được đo lường.

## Kết luận

Nên thử PPT Master nếu cần bàn giao PowerPoint có thể chỉnh sửa. Không có đủ bằng chứng để gọi nó là công cụ đẹp nhất. Chất lượng nên được kiểm tra bằng một pilot gồm slide mở đầu, slide dữ liệu và slide sơ đồ, dùng cùng nội dung và reference trước khi làm cả bộ.

PPT Master hiện mô tả một pipeline đi từ vật liệu nguồn, kế hoạch, SVG tới DrawingML/PPTX; entry point được đọc có metadata.version 6.7.2. Nó có các route riêng cho Generate, Create Template và Edit Native PPTX. [Entry point](https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/SKILL.md).

## Bằng chứng cộng đồng

Đây là các lời kể của người dùng, không phải thử nghiệm đối chứng; một số chủ đề có ít phiếu và có thể có thiên lệch lựa chọn.

- Một thảo luận về slide cho công việc tư vấn đề xuất đưa ví dụ đẹp, xây design system từ slide tham chiếu và cho cả ví dụ cách viết câu. Có người dùng Slidev với Claude Code. [Thảo luận gốc](https://www.reddit.com/r/ClaudeAI/comments/1v7chdl/claude_how_to_make_better_slides_that_are_not_html/).
- Trong chủ đề về template doanh nghiệp, người dùng mô tả hiệu quả của việc cung cấp template có sẵn, giữ artifacts để sửa từng slide và cho agent nhìn output. Một người vẫn cần 2–3 vòng chỉnh để bám template và giảm vẻ AI. [Thảo luận gốc](https://www.reddit.com/r/ClaudeAI/comments/1udhonv/presentations_on_claude/).
- Một chủ đề khác phản ánh mức thiết kế chưa đạt mong muốn; một bình luận báo kết quả tốt hơn khi tái sử dụng template tự làm. [Thảo luận gốc](https://www.reddit.com/r/ClaudeCode/comments/1sliktl/anyone_been_able_to_create_strong_design_ppts/).

Suy luận thực hành: reference rõ, kiểm soát nội dung và vòng xem-sửa có ích hơn việc liên tục thêm tính từ như “premium”, “stunning”, “professional” vào prompt. Không thể suy từ các thread này ra tỷ lệ thành công chung.

## Đánh giá PPT Master

### Điểm phù hợp

Default Generate có bước xác nhận mục tiêu, khán giả, template, hướng thiết kế rồi mới author và kiểm tra. Với mục tiêu chất lượng cao, nên giữ quy trình này thay vì yêu cầu Quick một lần. [Generate workflow](https://github.com/hugohe3/ppt-master/blob/main/skills/ppt-master/workflows/generate-pptx.md).

Để dùng lại reference, cần phân biệt:

- Muốn giữ bộ slide có sẵn và thay nội dung: Edit Native PPTX.
- Muốn rút ra hệ thiết kế để tạo bộ mới: Create Template rồi Generate.

Đưa một file PPTX cùng nội dung mới có thể dẫn đến route sửa deck; cần yêu cầu rõ Create Template nếu muốn tạo hệ thiết kế tái sử dụng. [Getting Started](https://github.com/hugohe3/ppt-master/blob/main/docs/getting-started.md).

### Các giới hạn cần kiểm tra

- Chart/table mặc định có thể là shape. Muốn đối tượng Chart/Table có dữ liệu PowerPoint, yêu cầu xuất thêm bằng `--native-charts-and-tables`. [README](https://github.com/hugohe3/ppt-master#quick-start).
- Free-design/brand-only xuất theo cấu trúc flat. Muốn Master/Layout/placeholder tái sử dụng thực sự phải dùng workspace Deck/Layout hợp lệ; logo lặp lại không tự biến thành slide master. Một số hiệu ứng chỉ approximate hoặc phải rasterize. [Feature mapping](https://github.com/hugohe3/ppt-master/blob/main/docs/powerpoint-svg-mapping.md).
- Font trong thiết kế dùng px, PowerPoint hiển thị pt; ví dụ 24px thành 18pt. Text chỉnh sửa được chưa đồng nghĩa tự reflow: cần yêu cầu reflow khi muốn hành vi đó. Profile Image to PPTX hiện ghi hỗ trợ Codex, không hứa hỗ trợ Claude Code. [FAQ](https://github.com/hugohe3/ppt-master/blob/main/docs/faq.md).

Không đánh giá theo việc “mở được file” hoặc SVG trông ổn. Cần kiểm tra chỉnh sửa text, Edit Data, thay font, sửa câu dài và hiển thị trên ứng dụng dùng để thuyết trình.

## Chọn công cụ theo đầu ra

| Nhu cầu | Điểm xuất phát đề xuất |
|---|---|
| File PowerPoint bàn giao, sửa từng phần tử | PPT Master pilot |
| Tận dụng template PPTX đang dùng tốt | Edit Native PPTX hoặc skill PPTX chính thức của Anthropic |
| Talk kỹ thuật, code, tương tác và trình chiếu bằng browser | Claude Code + Slidev |

Skill PPTX chính thức của Anthropic mô tả tạo bằng PptxGenJS, sửa XML khi dùng template, render ảnh và kiểm tra trực quan. Đây là baseline hợp lý để đối chiếu, chưa có bằng chứng ở nghiên cứu này rằng nó đẹp hơn hoặc kém PPT Master. [Skill chính thức](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md).

Slidev hiện có `--format pptx-editable`, không chỉ xuất PPTX dạng ảnh. Tuy nhiên SVG, công thức và nhiều hiệu ứng vẫn thành ảnh, có thể fallback cả slide; font và wrap khác PowerPoint. Đừng chọn đường HTML rồi mặc định kỳ vọng chuyển sang PPTX hoàn hảo. [Slidev export](https://sli.dev/guide/exporting).

## Quy trình đề xuất để tránh AI slop

Các bước sau là khuyến nghị thực hành, không phải checklist bắt buộc của công cụ.

1. **Viết brief:** ai nghe, biết gì, thời lượng, cần nhớ/ra quyết định gì, trình chiếu hay đọc, có cần sửa PPTX hay không.
2. **Chuẩn bị 5–8 slide tham chiếu:** chọn cùng ngôn ngữ thị giác; ghi rõ thích typography, cách dùng ảnh, mật độ, chart hoặc nhịp bố cục nào. Dùng tài liệu có quyền sử dụng.
3. **Chốt story trước:** mỗi trang có thông điệp, bằng chứng, hình thức thể hiện và lời dẫn. Tiêu đề nói điều rút ra được thay vì chỉ tên chủ đề. Với bài giới thiệu, tiêu đề định hướng vẫn có thể phù hợp.
4. **Chốt hệ thiết kế:** font có dấu tiếng Việt, palette ít màu, lề, cấp chữ và phong cách ảnh/icon. Bố cục thay đổi theo nội dung, không ngẫu nhiên để tạo cảm giác đa dạng.
5. **Pilot ba trang:** opening, dữ liệu, sơ đồ. Đề nghị render bản PPTX; kiểm tra cả từng trang lẫn contact sheet. Chỉ mở rộng khi ba loại này đạt yêu cầu.
6. **Sản xuất và sửa cụ thể:** thay “làm đẹp hơn” bằng “slide 6 bỏ card nền, phóng chart, đưa chi tiết sang notes, làm rõ chênh lệch A/B”.
7. **QA:** đối chiếu số liệu với nguồn; kiểm tra tiếng Việt, crop, tương phản, tràn chữ; mở deck trên máy trình chiếu; giữ PDF dự phòng.

### Quy tắc thẩm mỹ gợi ý

- Mỗi slide có một điểm nhìn chính; người xem nhận ra ý chính trong vài giây.
- Dùng sơ đồ cho quan hệ/quy trình, chart cho dữ liệu, ảnh thật cho ngữ cảnh hoặc sản phẩm.
- Hạn chế card bo góc lặp lại, gradient mặc định, emoji và icon chỉ để lấp chỗ trống.
- Không cấm tuyệt đối hiệu ứng hoặc một màu cụ thể: chúng cần phục vụ nội dung và reference.
- Không giảm chữ đến mức khó đọc để giữ mọi chi tiết; ưu tiên rút gọn, notes hoặc appendix.
- Không đưa chỉ số chưa đo vào slide để bố cục trông thuyết phục hơn. Nhãn minh họa phải rõ.

## Prompt khởi đầu

```text
Dùng ppt-master theo Default workflow. Mục tiêu là deck trình chiếu trực tiếp
có PPTX chỉnh sửa được, reading mode presentation. Chưa tạo toàn bộ ngay.

Khán giả: [...]
Thời lượng: [...]
Sau buổi trình bày họ cần hiểu/quyết định: [...]
Thông điệp cốt lõi: [...]
Nguồn nội dung: [...]
Slide tham chiếu: [...]

Trước tiên, phân tích reference thành hệ thiết kế và đề xuất storyline.
Với từng slide, ghi thông điệp, bằng chứng, hình thức thể hiện và speaker notes.
Giữ đúng dữ kiện; không tự thêm số liệu hoặc kết luận chưa có nguồn.

Đề xuất hướng thiết kế phù hợp rồi làm pilot gồm một opening,
một slide dữ liệu và một slide sơ đồ trước khi mở rộng cả deck.
Nếu cần rút hệ thiết kế từ PPTX mẫu, dùng Create Template trước.

Ưu tiên typography và khoảng trắng. Tránh card/gradient/icon trang trí lặp lại.
Mỗi slide có một điểm nhìn chính. Chữ hỗ trợ đầy đủ tiếng Việt.
Chốt cỡ chữ theo pt trong PowerPoint và quy đổi đúng sang px của công cụ.
Đưa giải thích dài vào notes. Chọn hình thức theo thông tin, không dùng
một bố cục title + ba bullet cho cả bộ.

Xuất PPTX editable và bản xem trước. Chart cần Edit Data thì xuất thêm
native chart. Kiểm tra cả bản PPTX render, không chỉ SVG hoặc source code.
Nêu rõ những phần chưa xác minh thay vì báo hoàn tất mặc định.
```

## Cài đặt để thử sau

Trong Claude Code, README hiện hướng dẫn:

```text
/plugin marketplace add hugohe3/ppt-master
/plugin install ppt-master@ppt-master
```

Vẫn cần Python 3.10+ và Python dependencies trong `requirements.txt` tại thư mục skill đã cài. Chạy agent trong working folder có thể ghi, tách với cache plugin. [Hướng dẫn cài](https://github.com/hugohe3/ppt-master#3-set-up), [working folder](https://github.com/hugohe3/ppt-master/blob/main/docs/getting-started.md#set-up-the-installation-and-working-folders).

Không cần cài chồng nhiều skill làm slide để thử đầu tiên. Hãy đánh giá một pipeline trên brief/reference thật, rồi chỉ bổ sung công cụ khi xuất hiện hạn chế cụ thể.

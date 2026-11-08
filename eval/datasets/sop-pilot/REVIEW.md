# Phiếu duyệt pilot câu hỏi V2-06

**24 câu = 12 ý, mỗi ý một bản VI và EN. Cập nhật 2026-11-01: owner duyệt 24/24 câu, không loại/sửa câu nào (`review.jsonl`); các checkbox bên dưới giữ nguyên dạng phiếu gốc.** Có 20 câu answerable và 4 câu âm; 12 câu hỏi khác ngôn ngữ tài liệu. Tất cả thuộc dev; chưa tạo test chính thức, chưa freeze. Cỡ pilot không thay mục tiêu cuối của ticket.

Mỗi ý bên dưới cần kiểm: câu hỏi tự nhiên, bản VI/EN cùng nghĩa, bằng chứng đủ mọi điều kiện/ngoại lệ, đáp án không suy diễn. Các span trong cùng một evidence set phải có **đủ tất cả**. Với câu âm, đọc đủ bốn tài liệu đã chọn, không chỉ dựa trên search hoặc retriever.

Nguồn và phạm vi: [SOURCES.md](SOURCES.md); [manifest](manifest.json); [evidence](evidence.jsonl); [questions](questions.master.jsonl). Hai bản canonical PDF VI nằm local và không commit; tái tạo theo README. Đối chiếu câu VI với trang PDF gốc trong corpus extraction khi cần.

Các đề xuất sửa ở đây chưa phải review log. Sau khi có phán quyết của bạn mới ghi reviewer thật, thời gian, label/corpus version và audit câu âm vào `review.jsonl`.

## 1. risk-planning

Nhãn: `responsibility, number_deadline, multi_passage`; nguồn VI; trạng thái **draft**.

**VI:** Theo QT-02 của Sở Xây dựng Ninh Bình, ai lập kế hoạch phân tích bối cảnh và thực hiện vào thời điểm nào?

**EN:** Under Ninh Binh Department of Construction QT-02, who plans the context analysis and when?

**Đáp án VI nháp:** Ban chỉ đạo ISO; Quý I hằng năm hoặc đột xuất.

**Đáp án EN nháp:** The ISO steering committee; in the first quarter annually or on an ad hoc basis.

Bằng chứng `risk-plan-owner` — [nb-qt02](corpus/nb-qt02.md), trang PDF 4, offset [3005, 3078):

```text
Ban chỉ đạo ISO có trách nhiệm căn cứ tình hình chung về hoạt động của Sở
```

Bằng chứng `risk-plan-time` — [nb-qt02](corpus/nb-qt02.md), trang PDF 4, offset [3258, 3286):

```text
Quý I hàng năm hoặc đột xuất
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 2. risk-approval

Nhãn: `procedure, condition_exception, responsibility, number_deadline, multi_passage`; nguồn VI; trạng thái **draft**.

**VI:** QT-02 ghi ai xem xét phê duyệt kế hoạch, mốc thời gian nào, và nếu kế hoạch chưa phù hợp thì xử lý ra sao?

**EN:** In QT-02, who reviews and approves the plan, what timing is stated, and what happens if the plan is unsuitable?

**Đáp án VI nháp:** Lãnh đạo Sở xem xét, phê duyệt; mốc được ghi là sau 7 ngày tiếp nhận kế hoạch. Nếu chưa phù hợp, Ban chỉ đạo ISO điều chỉnh để làm rõ phân tích rủi ro, cơ hội và hành động giải quyết.

**Đáp án EN nháp:** Department leadership reviews and approves it; the stated timing is after 7 days of receiving the plan. If unsuitable, the ISO steering committee revises it to clarify risk and opportunity analysis and response actions.

Bằng chứng `risk-approval-owner` — [nb-qt02](corpus/nb-qt02.md), trang PDF 4, offset [3369, 3402):

```text
Lãnh đạo Sở xem xét và phê duyệt:
```

Bằng chứng `risk-approval-time` — [nb-qt02](corpus/nb-qt02.md), trang PDF 4, offset [3625, 3654):

```text
Sau 7 ngày tiếp nhận kế hoạch
```

Bằng chứng `risk-revision` — [nb-qt02](corpus/nb-qt02.md), trang PDF 4, offset [3486, 3612):

```text
- Ngược lại, Ban chỉ đạo ISO điều chỉnh phù hợp nhằm xác định rõ việc phân tích rủi ro, cơ hội và đưa ra hành động giải quyết.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 3. risk-team

Nhãn: `fact, number_deadline`; nguồn VI; trạng thái **draft**.

**VI:** Theo QT-02, mốc thời gian thành lập nhóm phân tích là bao lâu trước kế hoạch phân tích?

**EN:** Under QT-02, how far ahead of the analysis plan is the analysis team formed?

**Đáp án VI nháp:** Trước kế hoạch phân tích 3 ngày.

**Đáp án EN nháp:** 3 days before the analysis plan.

Bằng chứng `risk-team-time` — [nb-qt02](corpus/nb-qt02.md), trang PDF 4, offset [3955, 3986):

```text
Trước kế hoạch phân tích 3 ngày
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 4. audit-frequency

Nhãn: `comparison, condition_exception, number_deadline`; nguồn VI; trạng thái **draft**.

**VI:** Theo QT-03 của Sở Xây dựng Ninh Bình, tần suất đánh giá tối thiểu là bao nhiêu và trường hợp nào chu kỳ có thể ngắn hơn?

**EN:** Under Ninh Binh Department of Construction QT-03, what is the minimum audit frequency and when may the interval be shorter?

**Đáp án VI nháp:** Tối thiểu một lần mỗi năm; với yêu cầu quan trọng hoặc thường xảy ra sai lỗi, chu kỳ có thể ngắn lại.

**Đáp án EN nháp:** At least once a year; the interval may be shorter for important requirements or those with frequent errors.

Bằng chứng `audit-frequency` — [nb-qt03](corpus/nb-qt03.md), trang PDF 4, offset [2734, 2956):

```text
Hoạt động đánh giá phải thể hiện được tất cả các yêu cầu của hệ thống quản lý chất lượng, thực hiện tối thiểu một năm 01 lần. Đối với những yêu cầu quan trọng hoặc thường xảy ra sai lỗi thì chu kỳ đánh giá có thể ngắn lại.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 5. audit-preparation

Nhãn: `procedure, responsibility, number_deadline, multi_passage`; nguồn VI; trạng thái **draft**.

**VI:** Trong QT-03, đoàn đánh giá được thành lập trước bao nhiêu ngày và ai phải gửi thông báo chương trình trước ít nhất một tuần?

**EN:** In QT-03, how many days before the planned audit is the team formed, and who must send the programme notice at least one week beforehand?

**Đáp án VI nháp:** Đoàn được thành lập trước đánh giá theo kế hoạch 10 ngày; Trưởng đoàn đánh giá được chỉ định lập và gửi thông báo trước ít nhất một tuần.

**Đáp án EN nháp:** The team is formed 10 days before the planned audit; the appointed audit team leader prepares and sends the programme notice at least one week beforehand.

Bằng chứng `audit-team-time` — [nb-qt03](corpus/nb-qt03.md), trang PDF 4, offset [3221, 3257):

```text
Trước đánh giá theo kế hoạch 10 ngày
```

Bằng chứng `audit-notice` — [nb-qt03](corpus/nb-qt03.md), trang PDF 4, offset [3343, 3517):

```text
Trưởng đoàn đánh giá được chỉ định có trách nhiệm lập thông báo về chương trình và nội dung đánh giá và gửi trước đến các phòng được đánh giá trước thời gian ít nhất 01 tuần.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 6. risk-travel-allowance

Nhãn: `number_deadline`; nguồn VI; trạng thái **draft**.

**VI:** Theo bộ tài liệu pilot, người của nhóm phân tích rủi ro được hưởng mức phụ cấp đi công tác bao nhiêu tiền mỗi ngày?

**EN:** According to this pilot corpus, how much daily travel allowance is paid to a risk-analysis team member?

**Đáp án VI nháp:** Không đủ thông tin trong corpus pilot; cần audit câu âm.

**Đáp án EN nháp:** Insufficient information in the pilot corpus; negative audit pending.

Kiểm tra nháp: [negative-audit.draft.jsonl](negative-audit.draft.jsonl). Audit này do agent tạo, chưa thay thế người duyệt.

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 7. buddy-first-call

Nhãn: `procedure`; nguồn EN; trạng thái **draft**.

**VI:** Theo hướng dẫn GitLab, việc đầu tiên quan trọng nhất onboarding buddy nên làm là gì, và nên cân nhắc thời điểm nào trong ngày đầu?

**EN:** According to GitLab, what is the first and most important task for an onboarding buddy, and what time on the first day should they consider?

**Đáp án VI nháp:** Lên lịch cuộc gọi với thành viên mới; cân nhắc cuối ngày làm việc đầu tiên để họ có thời gian đọc nội dung onboarding và chuẩn bị câu hỏi.

**Đáp án EN nháp:** Schedule a call with the new team member; consider toward the end of the first day so they can digest onboarding material and bring questions.

Bằng chứng `buddy-first` — [gitlab-buddies](corpus/gitlab-buddies.md), offset [27, 776):

```text
1. **The first and most important thing a buddy should do is schedule a call with the GitLab team-member.** You can do this in the days leading up to a new team member starting at GitLab by asking their manager for the new starter's personal email address. Introduce yourself and ask them when a good time to schedule an initial coffee chat would be. Consider picking a time towards the end of their first day so they have time to digest some of the onboarding issue and can come to the coffee chat with questions. We attempt to match (as best as possible, anyway) time zones between the GitLab team-member and their buddy so that as soon as the GitLab team-member logs on, you, the buddy, can be there ready and waiting to welcome them to the team.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 8. buddy-call-frequency

Nhãn: `comparison, number_deadline, condition_exception`; nguồn EN; trạng thái **draft**.

**VI:** GitLab hướng dẫn buddy lên lịch cuộc gọi tiếp theo thế nào trong tuần sau ngày bắt đầu so với phần còn lại của tháng đầu?

**EN:** How does GitLab compare the follow-up call schedule for the week after the start date with the rest of the first month?

**Đáp án VI nháp:** Ít nhất hai cuộc gọi trong tuần sau ngày bắt đầu và ít nhất một cuộc gọi cho phần còn lại của tháng đầu; có thể hỏi người mới muốn gọi thường xuyên hơn hay ít hơn.

**Đáp án EN nháp:** At least two follow-up calls for the week after the start date and at least one for the rest of the first month; ask whether the person prefers more or less frequent calls.

Bằng chứng `buddy-followups` — [gitlab-buddies](corpus/gitlab-buddies.md), offset [4367, 4841):

```text
1. **Check in regularly.** You may very well be the first friend the new GitLab team-member makes on the team. Checking in with them regularly will help them feel welcome and supported. Reach out via Slack, and schedule at least two follow-up calls for the week after their start date, and at least one follow-up call for the rest of the first month. But since it differs from one person to another, you may also ask them if they prefer more or less frequent calls per week.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 9. buddy-selection

Nhãn: `fact, responsibility`; nguồn EN; trạng thái **draft**.

**VI:** Theo GitLab, một onboarding buddy lý tưởng nên có các đặc điểm gì?

**EN:** According to GitLab, what characteristics should an ideal onboarding buddy have?

**Đáp án VI nháp:** Đã ở GitLab hơn 3 tháng, cùng phòng ban hoặc khối, múi giờ tương tự, sẵn sàng trong hai tuần đầu và có thể hỗ trợ thích nghi cùng các công cụ cần dùng. Đây là đặc điểm lý tưởng, không phải điều kiện luôn đạt được.

**Đáp án EN nháp:** More than 3 months at GitLab, the same department or division, a similar time zone, availability during the first two weeks, and the ability to support adjustment and relevant tools. These are ideal guidelines rather than conditions always met.

Bằng chứng `buddy-criteria` — [gitlab-buddies](corpus/gitlab-buddies.md), offset [5688, 6318):

```text
Ideally an onboarding buddy:

- has been at GitLab longer than 3 months
- shares the same department or division with the onboarding team member
- shares a similar timezone
- available during the first two weeks (no major PTO events or leave)
- is someone who can support the adjustment to GitLab and knows a bit about the applications / tools the new team member may be using in the course of their role

These guidelines have been developed from the feedback we receive in the Onboarding Survey and feedback from onboarding buddies. It is not always possible to achieve all of these guidelines depending on the team or location.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 10. meeting-before

Nhãn: `procedure, number_deadline, multi_passage`; nguồn EN; trạng thái **draft**.

**VI:** Trước cuộc họp GitLab, thư mời và agenda nên được gửi trước bao lâu, và agenda cần được liên kết ở đâu?

**EN:** Before a GitLab meeting, how far ahead should the invite and agenda be shared, and where should the agenda be linked?

**Đáp án VI nháp:** Khuyến nghị 72 giờ, tối thiểu 24 giờ, cho cả thư mời và agenda; đặt liên kết tài liệu agenda trong thư mời.

**Đáp án EN nháp:** 72 hours is recommended, with a minimum of 24 hours, for both invite and agenda; link the agenda document in the invite.

Bằng chứng `meeting-invite` — [gitlab-meetings](corpus/gitlab-meetings.md), offset [1080, 1450):

```text
1. **Send the meeting invite with proper advance notice.**  A meeting with team members will usually traverse multiple time zones. We recommend you send meeting invites 72 hours (minimum 24 hours) in advance of the meeting to give people time to respond to the invite. In addition, consider who is required in the meeting and mark non-essential participants as optional.
```

Bằng chứng `meeting-agenda` — [gitlab-meetings](corpus/gitlab-meetings.md), offset [1451, 1956):

```text
1. **Include a link to an agenda document in the invite.** Team members should be able to get context before the meeting through reviewing agendas, supporting materials, etc. [Meeting agendas](meetings/#4-all-meetings-must-have-an-agenda) should be shared 72 hours (minimum 24 hours) in advance of the meeting. Team members will need to know what is being discussed to decide if their participation is needed or [whether their meeting attendance is optional](meetings/#1-make-meeting-attendance-optional).
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 11. meeting-after

Nhãn: `condition_exception, number_deadline, multi_passage`; nguồn EN; trạng thái **draft**.

**VI:** Theo GitLab, sau cuộc họp nằm ngoài múi giờ của một số người, nên cân nhắc xác nhận quyết định trong khoảng nào; nếu có ghi hình thì thêm liên kết và mật khẩu vào agenda trong bao lâu?

**EN:** According to GitLab, after a meeting outside some participants' time zones, what decision-confirmation window should be considered, and how soon should a recording link and password be added to the agenda if recorded?

**Đáp án VI nháp:** Cân nhắc xác nhận quyết định và hành động trong 24–48 giờ; nếu có ghi hình, thêm liên kết và mật khẩu vào agenda trong vòng 12 giờ sau cuộc họp.

**Đáp án EN nháp:** Consider confirming decisions and actions for 24–48 hours; if recorded, add the recording link and password to the agenda within 12 hours after the meeting.

Bằng chứng `meeting-decisions` — [gitlab-meetings](corpus/gitlab-meetings.md), offset [7187, 7413):

```text
1. **Consider important decisions.**  When the meeting takes place outside of some participants' time zones, consider confirming decisions and actions for 24-48 hours. This will allow participants to contribute asynchronously.
```

Bằng chứng `meeting-recording` — [gitlab-meetings](corpus/gitlab-meetings.md), offset [7414, 7709):

```text
1. **Upload recording.** When the meeting is recorded, add the recording link and password in the agenda with in 12 hours after the meeting to allow for async consumption for people in different time zones. Also consider uploading to YouTube if it can be done so consistent with SAFE guidelines.
```

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).

## 12. buddy-bonus

Nhãn: `fact, number_deadline`; nguồn EN; trạng thái **draft**.

**VI:** Theo bộ tài liệu pilot, GitLab trả thưởng bao nhiêu tiền cho buddy với mỗi nhân viên mới được hỗ trợ?

**EN:** According to this pilot corpus, how much cash bonus does GitLab pay a buddy for each new hire supported?

**Đáp án VI nháp:** Không đủ thông tin trong corpus pilot; cần audit câu âm.

**Đáp án EN nháp:** Insufficient information in the pilot corpus; negative audit pending.

Kiểm tra nháp: [negative-audit.draft.jsonl](negative-audit.draft.jsonl). Audit này do agent tạo, chưa thay thế người duyệt.

- [ ] Duyệt hoặc ghi rõ cần sửa/loại ý này (cả hai ngôn ngữ).


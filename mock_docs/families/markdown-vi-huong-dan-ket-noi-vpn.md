# Hướng dẫn kết nối VPN công ty

Tài liệu giúp nhân viên cài đặt và kết nối mạng riêng ảo (VPN) để truy cập hệ thống nội bộ khi làm việc ngoài văn phòng. Hướng dẫn áp dụng cho Windows 11 và macOS.

## Giới thiệu

VPN mã hóa toàn bộ lưu lượng giữa máy của bạn và mạng công ty, giúp bạn truy cập cổng thông tin nhân sự, kho mã nguồn và thư mục chia sẻ như đang ngồi tại văn phòng. Công ty dùng ứng dụng khách WireGuard, được cấu hình sẵn cho từng nhân viên.

Bạn cần có tài khoản công ty đang hoạt động và đã bật xác thực hai lớp. Nếu chưa bật, hãy làm theo hướng dẫn trên trang bảo mật tài khoản trước.

## Cài đặt trên Windows

Tải trình cài đặt từ cổng phần mềm nội bộ, mục Công cụ mạng. Chạy tệp cài đặt với quyền quản trị, chọn các tùy chọn mặc định và nhấn Hoàn tất. Sau khi cài xong, biểu tượng WireGuard xuất hiện ở khay hệ thống.

Mở ứng dụng, chọn Nhập đường hầm từ tệp, rồi chọn tệp cấu hình có đuôi `.conf` mà Phòng Công nghệ thông tin đã gửi qua email riêng. Không chuyển tiếp tệp này cho bất kỳ ai, vì nó chứa khóa riêng của bạn.

## Cài đặt trên macOS

Mở App Store, tìm WireGuard và cài đặt. Mở ứng dụng, chọn Nhập đường hầm từ tệp và chọn tệp cấu hình. Macos sẽ hỏi quyền thêm cấu hình VPN, hãy chọn Cho phép và nhập mật khẩu máy khi được yêu cầu.

## Kết nối và ngắt kết nối

Để kết nối, mở WireGuard, chọn đường hầm `alpha-office` và nhấn Kích hoạt. Trạng thái chuyển sang màu xanh và hiển thị lượng dữ liệu đã truyền. Hãy thử mở trang `intranet.alpha.example` để kiểm tra.

Khi xong việc, nhấn Ngừng kích hoạt. Không nên để VPN chạy qua đêm nếu không cần thiết, vì các thiết bị được tính vào giới hạn 500 kết nối đồng thời của công ty.

## Câu hỏi thường gặp

**Tôi kết nối được nhưng không vào được trang nội bộ.** Kiểm tra bạn đã nhập đúng địa chỉ và thử xóa bộ nhớ đệm DNS. Trên Windows, chạy `ipconfig /flushdns` trong cửa sổ lệnh.

**Kết nối chậm hoặc hay bị ngắt.** Thử chuyển từ Wi-Fi sang cáp mạng, hoặc đổi sang máy chủ dự phòng bằng cách nhập tệp cấu hình `alpha-backup.conf`. Nếu vẫn lỗi, ghi lại thời điểm xảy ra và gửi yêu cầu hỗ trợ.

**Tôi đổi điện thoại hoặc máy tính thì sao.** Mỗi thiết bị cần một tệp cấu hình riêng. Gửi yêu cầu cấp cấu hình mới trên cổng hỗ trợ và ghi rõ thiết bị cũ cần thu hồi.

**Tôi có thể dùng VPN cho việc cá nhân không.** Không. VPN công ty chỉ dành cho công việc, và việc sử dụng được ghi nhật ký theo chính sách bảo mật.

## Liên hệ hỗ trợ

Gửi yêu cầu trên cổng hỗ trợ hoặc gọi số nội bộ 1234 trong giờ hành chính. Ngoài giờ, chỉ các sự cố ảnh hưởng đến nhiều người dùng mới được xử lý theo ca trực.

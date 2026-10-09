SilenceTrim 2.2 hiển thị phiên bản trên tiêu đề cửa sổ và thông báo khi có bản mới trên GitHub Releases.

- Tiêu đề trên cả macOS và Windows: **SilenceTrim v2.2**.
- Kiểm tra release chính thức khi mở app và mỗi giờ trong lúc app còn chạy. Chỉ hiển thị banner nếu phiên bản mới hơn bản đang dùng.
- Banner có nút **Xem & tải bản mới** mở GitHub Releases và nút **Ẩn** cho phiên mở app hiện tại.
- Kiểm tra chạy nền, có timeout; mất mạng hoặc lỗi GitHub không ảnh hưởng việc phân tích/cắt nhạc. Chỉ đọc thông tin release công khai, không gửi file nhạc.
- Giữ cảnh báo im lặng dài bất thường và giao diện bảng gọn của v2.1.

- **macOS Universal**: một app cho cả Apple Silicon và Intel, macOS 13 trở lên.
- **Windows x64**: giao diện Qt và CLI đóng gói sẵn, không cần cài Python.
- Giữ luồng phân tích trước, chọn bài cần xuất, cắt lossless/stream copy, kiểm tra đầu ra, báo cáo JSON và nút dừng.
- Build và kiểm thử cả hai nền tảng bằng GitHub Actions; kèm checksum SHA-256.

**Cần FFmpeg và FFprobe có sẵn trên máy; Windows tìm qua PATH.** Không đóng gói FFmpeg vào các gói tải.

Mac: giải nén rồi mở `SilenceTrim.app`. Windows: giải nén toàn bộ thư mục rồi mở `SilenceTrim/SilenceTrim.exe`; giữ nguyên `_internal` bên cạnh file EXE. Dùng `SilenceTrim-CLI.exe` nếu chạy batch trên Windows.

Các bản build chưa có chữ ký phân phối Apple Developer/Windows Authenticode. Xem README để biết cách mở trên macOS và cách sử dụng.

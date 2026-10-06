SilenceTrim 2.0 hỗ trợ macOS và Windows, dùng cùng logo và giao diện tiếng Việt.

- **macOS Universal**: một app cho cả Apple Silicon và Intel, macOS 13 trở lên.
- **Windows x64**: giao diện Qt và CLI đóng gói sẵn, không cần cài Python.
- Giữ luồng phân tích trước, chọn bài cần xuất, cắt lossless/stream copy, kiểm tra đầu ra, báo cáo JSON và nút dừng.
- Sửa xử lý đường dẫn qua symlink và tên tiếng Việt; giữ đúng cấu trúc thư mục con, loại trừ thư mục kết quả khỏi lần quét.
- Build và kiểm thử cả hai nền tảng bằng GitHub Actions; kèm checksum SHA-256.

**Cần FFmpeg và FFprobe có sẵn trên máy; Windows tìm qua PATH.** Không đóng gói FFmpeg vào các gói tải.

Mac: giải nén rồi mở `SilenceTrim.app`. Windows: giải nén toàn bộ thư mục rồi mở `SilenceTrim/SilenceTrim.exe`; giữ nguyên `_internal` bên cạnh file EXE. Dùng `SilenceTrim-CLI.exe` nếu chạy batch trên Windows.

Các bản build chưa có chữ ký phân phối Apple Developer/Windows Authenticode. Xem README để biết cách mở trên macOS và cách sử dụng.

SilenceTrim 2.1 thêm cảnh báo bài có khoảng im lặng dài bất thường ở đầu hoặc cuối trên macOS và Windows.

- Tô đỏ bài khi im lặng gốc ở đầu **hoặc** cuối dài hơn ngưỡng cảnh báo; hiển thị lời nhắc kiểm tra trong cột Trạng thái và số bài cần kiểm tra phía trên bảng.
- Ngưỡng mặc định **5 giây**, có lựa chọn **10 giây** hoặc tự nhập số giây lớn hơn 0. Đổi ngưỡng cập nhật ngay, không cần phân tích lại.
- Rê chuột lên bài để xem số giây im lặng ở mỗi đầu và lời nhắc. Bỏ dòng chi tiết/cảnh báo dưới bảng để giao diện gọn hơn.
- Cảnh báo dựa trên im lặng của file gốc, độc lập với lượng cắt và vẫn hiển thị sau khi xuất.

- **macOS Universal**: một app cho cả Apple Silicon và Intel, macOS 13 trở lên.
- **Windows x64**: giao diện Qt và CLI đóng gói sẵn, không cần cài Python.
- Giữ luồng phân tích trước, chọn bài cần xuất, cắt lossless/stream copy, kiểm tra đầu ra, báo cáo JSON và nút dừng.
- Build và kiểm thử cả hai nền tảng bằng GitHub Actions; kèm checksum SHA-256.

**Cần FFmpeg và FFprobe có sẵn trên máy; Windows tìm qua PATH.** Không đóng gói FFmpeg vào các gói tải.

Mac: giải nén rồi mở `SilenceTrim.app`. Windows: giải nén toàn bộ thư mục rồi mở `SilenceTrim/SilenceTrim.exe`; giữ nguyên `_internal` bên cạnh file EXE. Dùng `SilenceTrim-CLI.exe` nếu chạy batch trên Windows.

Các bản build chưa có chữ ký phân phối Apple Developer/Windows Authenticode. Xem README để biết cách mở trên macOS và cách sử dụng.

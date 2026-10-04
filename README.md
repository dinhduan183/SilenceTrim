# SilenceTrim

Ứng dụng macOS có giao diện tiếng Việt để cắt khoảng im lặng ở đầu và cuối nhiều bài nhạc trong một thư mục. Mặc định giữ lại tối đa **0,5 giây mỗi phía**, với ngưỡng im lặng **−60 dB**.

## Tính năng

- Chọn hoặc kéo thư mục nhạc vào cửa sổ; tùy chọn xử lý cả thư mục con.
- Phân tích trước khi xuất, xem mức cắt từng bài và bỏ chọn những bài muốn giữ.
- Chỉ cắt hai đầu, giữ nguyên khoảng nghỉ giữa bài.
- MP3, AAC, OGG/Vorbis và Opus: sao chép gói âm thanh bằng stream copy, không mã hóa lại.
- WAV/AIFF PCM, FLAC và ALAC: cắt theo mẫu âm thanh và xuất lossless, giữ nguyên các mẫu còn lại.
- Giữ metadata và ảnh bìa nếu định dạng đầu ra hỗ trợ.
- Kiểm tra lại khoảng im lặng trên từng file đã cắt; không xuất nếu kết quả không đạt giới hạn.
- Ghi file mới vào thư mục riêng, giữ cấu trúc thư mục con, không ghi đè file có sẵn.
- Xuất báo cáo JSON; có nút dừng xử lý.
- Xử lý trực tiếp trên máy, không tải nhạc lên dịch vụ bên ngoài.

## Yêu cầu

- macOS 13 trở lên.
- Xcode Command Line Tools để build: `xcode-select --install`.
- FFmpeg và FFprobe. Nếu dùng Homebrew: `brew install ffmpeg`.

App tìm FFmpeg/FFprobe trong `Contents/Helpers`, `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin` và `PATH`. FFmpeg không được đóng gói trong repository này.

## Build và chạy

```sh
git clone https://github.com/dinhduan183/SilenceTrim.git
cd SilenceTrim
./build.command
open SilenceTrim.app
```

`build.command` tạo app cho kiến trúc của máy đang build (Apple Silicon hoặc Intel) và ký ad hoc. Đây là bản build cục bộ, chưa được notarize bằng tài khoản Apple Developer.

## Sử dụng

1. Chọn thư mục nhạc hoặc kéo thư mục vào cửa sổ.
2. Giữ thiết lập mặc định **−60 dB / 0,5 giây**, hoặc điều chỉnh theo bài nhạc.
3. Nhấn **1. Phân tích**, xem trước lượng cắt của từng bài.
4. Nhấn **2. Cắt & xuất**.
5. Nhấn **Mở kết quả** để xem file mới và báo cáo.

Mặc định, thư mục kết quả nằm cạnh thư mục gốc và có đuôi `— Trimmed`. Nếu tên này đã tồn tại, app chọn tên mới có số thứ tự.

File đã đạt giới hạn được sao chép nguyên trạng. File hoàn toàn dưới ngưỡng im lặng cũng được sao chép nguyên trạng để tránh tạo file rỗng; trường hợp này là ngoại lệ đối với giới hạn 0,5 giây.

## Cách xác định im lặng và giữ chất lượng

Âm thanh dưới ngưỡng đã chọn liên tục ít nhất 0,05 giây được xem là im lặng. Ngưỡng quá cao có thể nhận nhầm đoạn nhạc rất nhỏ hoặc fade-in/fade-out thành im lặng. Hạ xuống −70 hoặc −80 dB nếu cần giữ những đoạn này.

Định dạng nén được cắt tại biên gói âm thanh. App chừa thêm biên an toàn rồi kiểm tra đầu ra, nên khoảng giữ lại có thể ngắn hơn 0,5 giây. Chất lượng mã hóa của phần âm thanh giữ lại không thay đổi; tên file, metadata container hoặc kích thước file có thể thay đổi khi xuất. Các chapter cũ không được mang sang file đã cắt vì mốc thời gian đã thay đổi.

Tài liệu kỹ thuật: [FFmpeg stream copy](https://ffmpeg.org/ffmpeg.html#Streamcopy), [silencedetect](https://ffmpeg.org/ffmpeg-filters.html#silencedetect), [atrim](https://ffmpeg.org/ffmpeg-filters.html#atrim).

## Chạy từ dòng lệnh

```sh
./SilenceTrim.app/Contents/MacOS/SilenceTrim --batch \
  --input "/duong/dan/thu-muc-nhac" \
  --output "/duong/dan/thu-muc-ket-qua" \
  --threshold -60 --padding 0.5 --recursive
```

Bỏ `--recursive` nếu chỉ xử lý file ngay trong thư mục nguồn. Khoảng giữ lại hỗ trợ 0,1–2 giây; ngưỡng hỗ trợ −100 đến −20 dB. Exit code `0` là hoàn tất không có lỗi; `1` là có lỗi; `2` là thiếu đối số dòng lệnh.

## Mã nguồn

- `source/main.swift`: giao diện AppKit và chế độ batch CLI.
- `source/TrimEngine.swift`: phân tích, cắt, kiểm tra đầu ra và ghi báo cáo.
- `source/Info.plist`: thông tin ứng dụng.
- `source/AppIcon.icns`: icon.
- `build.command`: script build macOS.

App đã build là kết quả sinh ra và được loại khỏi Git; build lại bằng script trên.

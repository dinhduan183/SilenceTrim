# SilenceTrim 2.1

[![Build macOS and Windows](https://github.com/dinhduan183/SilenceTrim/actions/workflows/build.yml/badge.svg)](https://github.com/dinhduan183/SilenceTrim/actions/workflows/build.yml)

Ứng dụng **macOS và Windows** có giao diện tiếng Việt để cắt khoảng im lặng ở đầu và cuối nhiều bài nhạc. Mặc định giữ lại tối đa **0,5 giây mỗi phía**, với ngưỡng im lặng **−60 dB**. Xử lý trực tiếp trên máy, không tải nhạc lên mạng.

## Tải và chạy

Tải bản đã build trong [GitHub Releases](https://github.com/dinhduan183/SilenceTrim/releases):

| Hệ điều hành | Gói tải | Cách chạy |
| --- | --- | --- |
| macOS 13+ · Apple Silicon hoặc Intel | `SilenceTrim-v2.1-macOS-Universal.zip` | Giải nén và mở `SilenceTrim.app` |
| Windows 10/11 · x64 | `SilenceTrim-v2.1-Windows-x64.zip` | Giải nén **toàn bộ thư mục**, mở `SilenceTrim/SilenceTrim.exe` |

Windows không cần cài Python hoặc Qt. Giữ nguyên thư mục `_internal` bên cạnh các file `.exe`.

**Cả hai bản cần `ffmpeg` và `ffprobe` có sẵn trên máy.** Windows tìm trong biến môi trường `PATH`; macOS tìm trong `PATH` và các vị trí Homebrew tiêu chuẩn. FFmpeg không được đóng gói trong app. Kiểm tra bằng `ffmpeg -version` và `ffprobe -version`, rồi mở lại app sau khi thay đổi PATH.

Bản Mac được ký ad hoc, chưa notarize; khi macOS chặn mở, dùng **System Settings → Privacy & Security → Open Anyway** sau khi xác nhận nguồn tải. Bản Windows chưa có chữ ký Authenticode.

## Tính năng

- Chọn hoặc kéo thư mục nhạc vào cửa sổ; tùy chọn xử lý cả thư mục con.
- Phân tích trước khi xuất, xem mức cắt từng bài và bỏ chọn những bài muốn giữ.
- Tô đỏ và nhắc kiểm tra bài có im lặng gốc ở đầu **hoặc** cuối dài hơn ngưỡng cảnh báo: mặc định **5 giây**, chọn **10 giây** hoặc tự nhập số giây lớn hơn 0. Đổi ngưỡng cập nhật cảnh báo ngay, không cần phân tích lại.
- Chỉ cắt hai đầu, giữ nguyên khoảng nghỉ giữa bài.
- MP3, AAC, OGG/Vorbis và Opus: sao chép gói âm thanh bằng stream copy, không mã hóa lại.
- WAV/AIFF PCM, FLAC và ALAC: cắt theo mẫu âm thanh và xuất lossless, giữ nguyên các mẫu còn lại.
- Giữ metadata và ảnh bìa nếu định dạng đầu ra hỗ trợ.
- Kiểm tra lại khoảng im lặng trên từng file đã cắt; không xuất nếu kết quả không đạt giới hạn.
- Ghi file mới vào thư mục riêng, giữ cấu trúc thư mục con, không ghi đè file có sẵn.
- Xuất báo cáo JSON; có nút dừng xử lý.
- Hỗ trợ đường dẫn tiếng Việt và thư mục nguồn qua symlink. Không quét lại thư mục kết quả hoặc đi theo symlink/junction bên trong nguồn.

## Sử dụng

1. Chọn thư mục nhạc hoặc kéo thư mục vào cửa sổ.
2. Giữ thiết lập mặc định **−60 dB / 0,5 giây**, hoặc điều chỉnh theo bài nhạc.
3. Nhấn **1. Phân tích**, xem trước lượng cắt của từng bài. Kiểm tra các bài tô đỏ có phần im lặng dài bất thường trước khi cắt; rê chuột lên bài để xem số giây ở mỗi đầu và lời nhắc. Ngưỡng cảnh báo độc lập với khoảng giữ lại và ngưỡng âm lượng dB.
4. Nhấn **2. Cắt & xuất**.
5. Nhấn **Mở kết quả** để xem file mới và báo cáo.

Mặc định, thư mục kết quả nằm cạnh thư mục gốc và có đuôi `— Trimmed`. Nếu tên này đã tồn tại, app chọn tên mới có số thứ tự.

File đã đạt giới hạn được sao chép nguyên trạng. File hoàn toàn dưới ngưỡng im lặng cũng được sao chép nguyên trạng để tránh tạo file rỗng; trường hợp này là ngoại lệ đối với giới hạn 0,5 giây.

## Cách xác định im lặng và giữ chất lượng

Âm thanh dưới ngưỡng đã chọn liên tục ít nhất 0,05 giây được xem là im lặng. Ngưỡng quá cao có thể nhận nhầm đoạn nhạc rất nhỏ hoặc fade-in/fade-out thành im lặng. Hạ xuống −70 hoặc −80 dB nếu cần giữ những đoạn này.

Định dạng nén được cắt tại biên gói âm thanh. App chừa thêm biên an toàn rồi kiểm tra đầu ra, nên khoảng giữ lại có thể ngắn hơn 0,5 giây. Chất lượng mã hóa của phần âm thanh giữ lại không thay đổi; metadata container hoặc kích thước file có thể thay đổi khi xuất. Các chapter cũ không được mang sang file đã cắt vì mốc thời gian đã thay đổi.

Tài liệu kỹ thuật: [FFmpeg stream copy](https://ffmpeg.org/ffmpeg.html#Streamcopy), [silencedetect](https://ffmpeg.org/ffmpeg-filters.html#silencedetect), [atrim](https://ffmpeg.org/ffmpeg-filters.html#atrim).

## Build từ mã nguồn

### macOS

Cần Xcode Command Line Tools (`xcode-select --install`); để kiểm thử có thể cài FFmpeg bằng `brew install ffmpeg`.

```sh
git clone https://github.com/dinhduan183/SilenceTrim.git
cd SilenceTrim
./build.command
open SilenceTrim.app
```

Mặc định build cho kiến trúc của máy. Để build Universal cho cả Apple Silicon và Intel:

```sh
BUILD_ARCHS="arm64 x86_64" ./build.command
```

### Windows

Cần Python 3.12 x64 và FFmpeg/FFprobe trong PATH. Chạy PowerShell ở thư mục repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r windows/requirements.txt
python windows/main.py
# Tạo gói không cần Python trên máy người dùng:
.\build-windows.ps1
```

Kết quả nằm ở `dist/SilenceTrim/`, gồm giao diện `SilenceTrim.exe`, dòng lệnh `SilenceTrim-CLI.exe` và thư viện `_internal`. Dùng `tools/make_windows_icon.py` để tạo lại file ICO nếu thay đổi PNG logo. Thông tin thư viện đóng kèm nằm trong [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Chạy từ dòng lệnh

macOS:

```sh
./SilenceTrim.app/Contents/MacOS/SilenceTrim --batch \
  --input "/duong/dan/thu-muc-nhac" \
  --output "/duong/dan/thu-muc-ket-qua" \
  --threshold -60 --padding 0.5 --recursive
```

Windows:

```powershell
.\SilenceTrim-CLI.exe --batch --input "D:\Nhạc" --output "D:\Nhạc đã cắt" --threshold -60 --padding 0.5 --recursive
```

Bỏ `--recursive` nếu chỉ xử lý file ngay trong thư mục nguồn. Khoảng giữ lại hỗ trợ 0,1–2 giây; ngưỡng hỗ trợ −100 đến −20 dB. Exit code `0` là hoàn tất không có lỗi; `1` là có lỗi; `2` là thiếu hoặc sai đối số dòng lệnh.

## Kiểm thử

Sau khi build bản Mac:

```sh
zsh tests/run.command
```

Sau khi cài dependencies Windows (cũng chạy được trên Mac để kiểm tra phần port):

```sh
python -m unittest discover -s windows/tests -v
```

Bộ kiểm thử kiểm tra đường dẫn/symlink, loại trừ thư mục xuất, dữ liệu lossless, khoảng nghỉ giữa bài, các codec, metadata/ảnh bìa, file im lặng, file hỏng, bảo vệ file có sẵn, file nguồn thay đổi, hủy tiến trình và luồng phân tích/xuất qua giao diện. Workflow Windows còn chạy smoke test trên **các file EXE đã đóng gói**.

## GitHub Actions và phát hành

Workflow [build.yml](.github/workflows/build.yml) chạy khi push lên `main`, tạo pull request, push tag `v*` hoặc bấm **Run workflow**. Hai job tạo gói Mac Universal và Windows x64 cùng checksum SHA-256, tải lên Actions artifacts.

Khi push tag đúng với số phiên bản trong mã nguồn, workflow chờ **cả hai job build và kiểm thử thành công** rồi tự tạo GitHub Release và đính kèm hai gói tải. Để phát hành phiên bản mới, cập nhật số phiên bản trong `source/Info.plist`, thông tin About/báo cáo Mac, `windows/silencetrim/__init__.py` và `windows/version_info.txt` trước khi tạo tag tương ứng.

## Mã nguồn

- `source/main.swift`, `source/TrimEngine.swift`: giao diện và engine macOS.
- `source/AppIcon.icns`, `source/AppIcon.png`, `source/AppIcon.ico`: cùng logo cho hai nền tảng.
- `windows/silencetrim/`: giao diện Qt, engine FFmpeg và CLI Windows.
- `build.command`, `build-windows.ps1`: build từng nền tảng.
- `tests/`, `windows/tests/`: kiểm thử.
- `.github/workflows/build.yml`: build, đóng gói và phát hành tự động.

App và thư mục build là kết quả sinh ra, không được lưu trong Git.

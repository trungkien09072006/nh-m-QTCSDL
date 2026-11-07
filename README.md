# NovaPath

NovaPath là giao diện web Python bước đầu cho đề tài **Hệ thống cá nhân hóa lộ trình học và luyện thi Đánh giá năng lực tích hợp AI**. Dashboard hiển thị hồ sơ học sinh, thời gian học, điểm thi gần nhất, dự đoán điểm, năng lực, lộ trình và gợi ý được lưu trong SQL Server. Đây là phiên bản nền tảng; chưa có đăng nhập, làm bài thi hay dịch vụ AI trực tiếp.

## Yêu cầu

- Python 3.10 trở lên
- SQL Server Express với cơ sở dữ liệu `AILearningDB`
- Microsoft ODBC Driver 17 for SQL Server (hoặc chọn driver đã cài bằng `SQL_DRIVER`)

## Cài đặt và chạy trên Windows

Mở PowerShell tại thư mục dự án:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Nếu chưa tạo dữ liệu, chạy script `01_schema\00_run_all.sql` trong SQL Server Management Studio. Thiết lập kết nối rồi khởi động web:

```powershell
$env:SQL_SERVER = "localhost\SQLEXPRESS"
$env:SQL_DATABASE = "AILearningDB"
$env:SQL_DRIVER = "ODBC Driver 17 for SQL Server"
$env:SQL_TRUSTED_CONNECTION = "true"
$env:STUDENT_EMAIL = "student1@gmail.com"
python .\06_web_app\app.py
```

Mở <http://127.0.0.1:5000>. Mặc định ứng dụng dùng Windows Authentication và hồ sơ mẫu `student1@gmail.com`. Để dùng SQL Server Authentication, đặt `SQL_TRUSTED_CONNECTION` thành `false`, sau đó cung cấp `SQL_USERNAME` và `SQL_PASSWORD` qua biến môi trường; không lưu mật khẩu vào mã nguồn.

Khi SQL Server chưa kết nối được, trang sẽ báo trạng thái lỗi và ứng dụng ghi chi tiết vào terminal. Nếu không tìm thấy hồ sơ, hãy kiểm tra `STUDENT_EMAIL` và dữ liệu trong bảng `Users`/`StudentProfiles`.

## Cấu trúc dự án

- `01_schema`–`05_admin_tuning`: các phần schema, dữ liệu, bảo mật và quản trị SQL Server.
- `06_web_app`: ứng dụng Flask, kết nối cơ sở dữ liệu, giao diện tĩnh và kiểm thử.
- `requirements.txt`: các thư viện Python của ứng dụng.

## Kiểm tra

```powershell
python -m unittest discover -s 06_web_app\tests -t 06_web_app
```

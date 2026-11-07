# NovaPath

NovaPath là ứng dụng web Python bước đầu cho đề tài **Hệ thống cá nhân hóa lộ trình học và luyện thi Đánh giá năng lực tích hợp AI**. Ứng dụng hiện có đăng ký/đăng nhập, hồ sơ học sinh và dashboard hiển thị dữ liệu học tập từ SQL Server. Chức năng làm bài thi và dịch vụ AI trực tiếp chưa được triển khai.

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
$env:FLASK_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python .\06_web_app\app.py
```

Mở <http://127.0.0.1:5000/login> để đăng nhập hoặc chọn đăng ký. Tài khoản học sinh mẫu là `student1@gmail.com` hoặc `student2@gmail.com`, mật khẩu `123456`. Mặc định ứng dụng dùng Windows Authentication tới SQL Server Express. Để dùng SQL Server Authentication, đặt `SQL_TRUSTED_CONNECTION` thành `false`, sau đó cung cấp `SQL_USERNAME` và `SQL_PASSWORD` qua biến môi trường; không lưu mật khẩu vào mã nguồn.

Lệnh trên tạo `FLASK_SECRET_KEY` ngẫu nhiên cho phiên PowerShell hiện tại. Nếu bỏ qua, ứng dụng tự tạo khóa tạm mới mỗi lần khởi động (các phiên đăng nhập cũ sẽ hết hiệu lực); khi triển khai, hãy cấu hình một khóa bí mật ổn định. Các biểu mẫu POST có CSRF token. Tài khoản mẫu dùng SHA-256 để tương thích dữ liệu seed cũ; sau lần đăng nhập thành công, ứng dụng tự nâng cấp hash mật khẩu đó. Tài khoản đăng ký mới dùng scrypt.

Khi SQL Server chưa kết nối được, trang sẽ báo trạng thái lỗi và ứng dụng ghi chi tiết vào terminal. Nếu không tìm thấy hồ sơ, hãy kiểm tra tài khoản đã đăng nhập và dữ liệu trong bảng `Users`/`StudentProfiles`.

## Cấu trúc dự án

- `01_schema`–`05_admin_tuning`: các phần schema, dữ liệu, bảo mật và quản trị SQL Server.
- `06_web_app`: ứng dụng Flask, kết nối cơ sở dữ liệu, giao diện tĩnh và kiểm thử.
- `requirements.txt`: các thư viện Python của ứng dụng.

## Kiểm tra

```powershell
python -m unittest discover -s 06_web_app\tests -t 06_web_app
```

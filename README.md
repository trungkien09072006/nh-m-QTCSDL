# NovaPath

NovaPath gồm website Flask và giao diện React + Vite mở trong cửa sổ trình duyệt riêng. Cả hai giao diện dùng chung backend Flask và cơ sở dữ liệu SQL Server. Giao diện Vite hiện có đăng nhập/đăng ký, dashboard và hồ sơ học sinh; phân hệ quản lý nội dung cho giáo viên/quản trị vẫn dùng website Flask.

## Yêu cầu

- Windows với PowerShell
- Python 3.10 trở lên và `pip`
- Node.js 20.19 trở lên và npm
- SQL Server Express với cơ sở dữ liệu `AILearningDB`
- Microsoft ODBC Driver 17 for SQL Server (hoặc một driver SQL Server đã cài, cấu hình bằng `SQL_DRIVER`)
- Google Chrome hoặc Microsoft Edge

## Cài đặt lần đầu

Mở PowerShell tại thư mục dự án và cài dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install --prefix .\vite_app
```

Nếu chưa tạo database/schema, mở `01_schema\00_run_all.sql` trong SQL Server Management Studio (SSMS), cập nhật biến `Root` ở đầu file thành đường dẫn thư mục dự án trên máy của bạn rồi chạy script. Cần có SQL Server và ODBC driver trước khi khởi động ứng dụng.

## Khởi động website và app

Trong PowerShell tại thư mục dự án, kích hoạt môi trường Python nếu đây là terminal mới, sau đó chạy:

```powershell
.\.venv\Scripts\Activate.ps1
npm start
```

Lệnh `npm start` chạy launcher `scripts\start-novapath.ps1`. Launcher chờ Flask và Vite sẵn sàng rồi mở:

- Website trong trình duyệt thường: <http://127.0.0.1:5000/login>
- App trong cửa sổ Chrome/Edge riêng (chế độ `--app`): <http://127.0.0.1:5173/>

Đây là cửa sổ trình duyệt độc lập, không phải PWA đã cài hay file EXE; không cần tải/cài thêm app ngoài Chrome hoặc Edge. Nhấn `Ctrl+C` trong terminal để dừng các server do launcher khởi động. Nếu server đang nghe cổng `5000` hoặc `5173`, launcher sẽ thử dùng lại server đó thay vì khởi động bản thứ hai.

Mặc định backend dùng Windows Authentication tới `localhost\SQLEXPRESS`, database `AILearningDB`, driver `ODBC Driver 17 for SQL Server`. Đặt biến môi trường trong PowerShell trước `npm start` nếu cần thay đổi:

```powershell
$env:SQL_SERVER = "localhost\SQLEXPRESS"
$env:SQL_DATABASE = "AILearningDB"
$env:SQL_DRIVER = "ODBC Driver 17 for SQL Server"
$env:SQL_TRUSTED_CONNECTION = "true"
# SQL_USERNAME và SQL_PASSWORD chỉ cần khi dùng SQL Server Authentication.
```

Khi dùng SQL Server Authentication, đặt `SQL_TRUSTED_CONNECTION` thành `false` và cung cấp `SQL_USERNAME`, `SQL_PASSWORD` qua biến môi trường. Không lưu mật khẩu vào mã nguồn. Backend cũng đọc `FLASK_SECRET_KEY`; launcher tự tạo khóa ngẫu nhiên nếu biến này chưa được đặt.

Vite chuyển tiếp các request `/api` tới Flask, do đó hai giao diện đọc/ghi cùng database. Có thể cần làm mới giao diện còn lại để xem dữ liệu mới. Nếu app gặp sự cố, website vẫn có thể mở riêng tại URL ở trên. Muốn truy cập từ thiết bị khác, cần triển khai trên máy chủ có HTTPS, cấu hình proxy `/api` tới Flask và kết nối tới cùng SQL Server; không đưa Flask development server trực tiếp ra Internet.

## Cấu trúc chính

- `01_schema`: tạo database, bảng và dữ liệu khởi tạo.
- `03_programmability`: stored procedures và trigger được gọi bởi schema runner.
- `06_web_app`: website Flask, API, kết nối database và kiểm thử.
- `vite_app`: giao diện React + Vite và cấu hình proxy API.
- `scripts\start-novapath.ps1`: khởi động cả hai giao diện trên Windows.
- `package.json`: lệnh `npm start` ở thư mục dự án.
- `requirements.txt`: dependencies Python của backend.

## Kiểm tra

```powershell
python -m unittest discover -s 06_web_app\tests -t 06_web_app
npm run build --prefix .\vite_app
```

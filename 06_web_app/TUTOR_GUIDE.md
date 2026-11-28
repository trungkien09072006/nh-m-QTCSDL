
Tài liệu này ghi lại chi tiết module **AI Tutor** do **Người 3** phụ trách, bao gồm các tiêu chí hoàn thành, mã nguồn độc lập, kiểm thử và hướng dẫn tích hợp cho **Người 4**.

---

## 1. Danh sách các file thuộc quyền sở hữu

Theo quy tắc làm việc song song để tránh xung đột git, Người 3 **không sửa** `app.py`, `App.jsx`, `database.py` hay các file schema dùng chung. Toàn bộ tính năng nằm trong các file riêng:

| Thành phần | Đường dẫn file | Nhiệm vụ |
| :--- | :--- | :--- |
| **Backend API** | `06_web_app/tutor_api.py` | Flask Blueprint (`/api/tutor`), xử lý hỏi đáp, kết nối Google Gemini API, truy xuất tài liệu qua sqlite-vec và fallback tri thức SQL Server, lưu `TutorSessions`, `TutorMessages`, `StudyLogs`. |
| **Backend Tests** | `06_web_app/tests/test_tutor.py` | Bộ kiểm thử tự động `unittest` độc lập cho toàn bộ endpoint và phân quyền. |
| **Frontend UI** | `vite_app/src/features/tutor/TutorChat.jsx` | Giao diện hỏi đáp: danh sách câu hỏi đề thi, khung hội thoại thời gian thực, quick prompt chips, làm mới phiên. |
| **Frontend API** | `vite_app/src/features/tutor/tutorApi.js` | Client gọi API `/api/tutor/*` và tự động gắn `X-CSRF-Token`. |
| **Frontend Style** | `vite_app/src/features/tutor/tutor.css` | Phong cách giao diện đồng bộ với tông màu NovaPath. |
| **Frontend Index** | `vite_app/src/features/tutor/index.js` | Export component sạch để Người 4 nhúng vào `App.jsx`. |
| **SQL Seed riêng** | `scripts/03_tutor_demo_seed.sql` | Dữ liệu mẫu kiểm thử: câu hỏi có giải thích chi tiết và lịch sử hội thoại mẫu. |

---

## 2. Đáp ứng tiêu chí hoàn thành theo Rubric

| Yêu cầu đề bài | Cách triển khai cụ thể |
| :--- | :--- |
| **Học sinh hỏi và nhận được giải thích trong giao diện** | Component `TutorChat.jsx` hỗ trợ hỏi về câu hỏi cụ thể trong ngân hàng đề hoặc hỏi tự do; hiển thị câu trả lời có định dạng Markdown, công thức và mẹo tránh bẫy. |
| **Hỗ trợ hỏi về câu cụ thể & lưu lịch sử** | Cho phép chọn câu hỏi từ ngân hàng đề, tự động trích xuất ngữ cảnh (`Questions`, `QuestionOptions`, `Competencies`); lưu vết vào `TutorSessions` và `TutorMessages`. |
| **Ghi rõ nguồn câu trả lời** | Tutor phân biệt tổng hợp có trích dẫn tài liệu, nội dung AI tự sinh và dữ liệu NovaPath. |
| **Ghi nhận thời gian học** | Tự động ghi nhận `StudyLogs (ActivityType='TUTOR', DurationMin=5)` sau mỗi lượt tương tác có giá trị. |

---

## 3. Cấu hình Gemini và nạp tài liệu

Chạy từ thư mục gốc của dự án trong PowerShell. Dùng cùng môi trường Python cho bước nạp và ứng dụng Flask.

```powershell
python -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "<khóa API từ Google AI Studio>"
python 06_web_app/tutor_rag.py "06_web_app/sample_materials/xac-suat-co-ban.md" --source demo-xac-suat --title "Xác suất cơ bản"
```

CLI nhận tệp Markdown hoặc văn bản UTF-8, chia thành các đoạn chồng lấn, gửi đoạn đến Gemini Embedding và lưu chỉ mục cosine trong SQLite với sqlite-vec. Chạy lệnh một lần cho mỗi tài liệu. Dùng lại `--source` để cập nhật tài liệu. Tệp giữ nguyên được bỏ qua. Chỉ nạp học liệu dùng chung cho học sinh vì nội dung được gửi tới Gemini và có thể xuất hiện trong trích dẫn.

- `GEMINI_MODEL` ghi đè mô hình sinh và kiểm tra. Mặc định là `gemini-3.8-flash`.
- `TUTOR_INDEX_PATH` ghi đè đường dẫn chỉ mục, mặc định là `06_web_app/tutor_index.sqlite3`. CLI và Flask cần dùng cùng đường dẫn.
- `TUTOR_MAX_COSINE_DISTANCE` mặc định là `0.40`. Mỗi lượt tìm tối đa bốn đoạn và bỏ các kết quả có khoảng cách lớn hơn ngưỡng.

Khởi động Flask với cùng cấu hình. Trong AI Tutor, hỏi một nội dung được học liệu giải thích. Một câu trả lời **AI tổng hợp từ tài liệu** có số tham chiếu, tiêu đề, mã nguồn, số đoạn và trích dẫn nguyên văn. Hệ thống so khớp trích dẫn với đoạn đã truy xuất và yêu cầu Gemini kiểm tra căn cứ trước khi gắn nhãn. Tin nhắn giữ nguyên nhãn và nguồn khi mở lại lịch sử. Các phản hồi Gemini thiếu căn cứ tài liệu mang nhãn **Nội dung AI tự sinh**. Khi Gemini không khả dụng, Tutor dùng lời giải ngân hàng câu hỏi hoặc hồ sơ học tập NovaPath.

Mở **Sinh câu hỏi luyện tập**, nhập chủ đề hoặc chọn câu mẫu trong ngân hàng rồi chọn mức khó từ 1 đến 5. Tutor kiểm tra cấu trúc, phương án trùng, chủ đề, độ khó, kết quả giải độc lập và lời giải. Câu đạt kiểm tra xuất hiện trong phiên đang mở, với đáp án và lời giải thu gọn. Câu luyện tập không được ghi vào ngân hàng đề hoặc lịch sử hội thoại.

### Kiểm tra bằng tài liệu mẫu

1. Đăng nhập bằng tài khoản học sinh và mở AI Tutor. Hỏi “Khi gieo hai đồng xu cân bằng độc lập, dùng biến cố đối để tính xác suất có ít nhất một mặt ngửa như thế nào?”. Kiểm tra kết quả 3/4, nhãn **AI tổng hợp từ tài liệu** và trích dẫn nguyên văn từ nguồn `demo-xac-suat`. Tải lại trang để kiểm tra lịch sử.
2. Hỏi “Định luật phản xạ ánh sáng phát biểu thế nào?”. Nếu chỉ mục chỉ có tài liệu xác suất mẫu, phản hồi Gemini cần mang nhãn **Nội dung AI tự sinh** và không có mục trích dẫn tài liệu.
3. Mở **Sinh câu hỏi luyện tập**, nhập chủ đề “Biến cố đối trong xác suất” và chọn độ khó 2. Kiểm tra câu có bốn lựa chọn, rồi mở **Xem đáp án và lời giải** để đối chiếu phép tính với phương án được chọn.

## 4. Chạy bộ kiểm thử độc lập

Để kiểm tra module Người 3 mà không cần chờ các bạn khác:

```powershell
$env:PYTHONPATH = "06_web_app"
python -m unittest discover -s 06_web_app/tests -p test_tutor*.py
```

---

## 5. Hướng dẫn dành cho Người 4 (Khi ghép dự án cuối cùng)

Người 4 chỉ cần thực hiện 2 bước đơn giản:

### Bước 1: Đăng ký Blueprint trong `06_web_app/app.py`
Mở `06_web_app/app.py`, thêm vào phần đầu file:
```python
from tutor_api import bp as tutor_bp
app.register_blueprint(tutor_bp)
```

### Bước 2: Nhúng giao diện vào `vite_app/src/App.jsx`
1. Import component ở đầu `App.jsx`:
   ```jsx
   import { TutorChat } from "./features/tutor";
   ```
2. Thêm nút menu trong `<nav className="main-nav">`:
   ```jsx
   <button className={`nav-link ${page === "tutor" ? "active" : ""}`} onClick={() => navigate("tutor")}>
     <span className="nav-icon">✦</span>AI Tutor
   </button>
   ```
3. Thêm render trang trong phần `<div className="page-content">`:
   ```jsx
   {page === "tutor" ? (
     <TutorChat studentName={user.fullname} />
   ) : ...}
   ```

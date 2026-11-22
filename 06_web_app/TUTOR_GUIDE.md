
Tài liệu này ghi lại chi tiết module **AI Tutor** do **Người 3** phụ trách, bao gồm các tiêu chí hoàn thành, mã nguồn độc lập, kiểm thử và hướng dẫn tích hợp cho **Người 4**.

---

## 1. Danh sách các file thuộc quyền sở hữu

Theo quy tắc làm việc song song để tránh xung đột git, Người 3 **không sửa** `app.py`, `App.jsx`, `database.py` hay các file schema dùng chung. Toàn bộ tính năng nằm trong các file riêng:

| Thành phần | Đường dẫn file | Nhiệm vụ |
| :--- | :--- | :--- |
| **Backend API** | `06_web_app/tutor_api.py` | Flask Blueprint (`/api/tutor`), xử lý hỏi đáp, kết nối Google Gemini API, fallback tri thức SQL Server (RAG / Rule-based), lưu `TutorSessions`, `TutorMessages`, `StudyLogs`. |
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
| **Kết nối AI thật nếu có & ghi rõ giới hạn nếu dùng Rule-based** | Tự động phát hiện biến môi trường `GEMINI_API_KEY`: <br>• Khi có key: gọi Google Gemini API (`gemini-1.5-flash`).<br>• Khi chưa có key: tự động fallback sang cơ chế tri thức nội bộ từ DB và ghi rõ nhãn `[Chế độ: Tri thức NovaPath (RAG nội bộ)]`, không mạo danh mô hình ngoài. |
| **Ghi nhận thời gian học** | Tự động ghi nhận `StudyLogs (ActivityType='TUTOR', DurationMin=5)` sau mỗi lượt tương tác có giá trị. |

---

## 3. Hướng dẫn cấu hình mô hình AI ngoài (Google Gemini)

Mặc định hệ thống chạy ở chế độ **Tri thức nội bộ (RAG / Rule-based)** trích xuất từ CSDL SQL Server mà không cần cài thêm thư viện ngoài (dùng thư viện chuẩn `urllib.request`).

Nếu muốn kích hoạt AI sinh ngôn ngữ tự nhiên từ **Google Gemini**:

1. Lấy API key miễn phí tại: [Google AI Studio](https://aistudio.google.com/)
2. Đặt biến môi trường trong PowerShell trước khi chạy app:
   ```powershell
   $env:GEMINI_API_KEY = "AIzaSy..."
   # Tùy chọn model (mặc định là gemini-1.5-flash):
   $env:GEMINI_MODEL = "gemini-1.5-flash"
   ```
3. Khởi động lại backend Flask, hệ thống sẽ tự động chuyển sang nhãn `✨ Gemini AI`.

---

## 4. Chạy bộ kiểm thử độc lập

Để kiểm tra module Người 3 mà không cần chờ các bạn khác:

```powershell
# Chạy bộ test riêng cho AI Tutor
python -m unittest 06_web_app\tests\test_tutor.py
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

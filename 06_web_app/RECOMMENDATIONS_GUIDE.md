# Phần 2 — Gợi ý học và dự đoán điểm

Học sinh xem điểm ĐGNL dự kiến, khả năng đạt mục tiêu, lý do được gợi ý và cách cải thiện. Module nối vào hai thủ tục SQL đã có (`sp_GenerateRecommendations`, `sp_CalculateScorePrediction`), không sửa chúng.

## File của phần này

| Lớp | File |
| --- | --- |
| Backend | `06_web_app/recommendation_service.py`, `06_web_app/recommendations.py` |
| SQL | `scripts/04_recommendations_prediction.sql`, `scripts/04_recommendations_demo_seed.sql` |
| Giao diện | `vite_app/src/features/recommendations/` (`RecommendationsPage.jsx`, `recommendationsApi.js`, `recommendations.css`, `index.js`) |
| Test | `06_web_app/tests/test_recommendations.py` |

Không sửa `app.py`, `App.jsx`, `api.js`, `database.py`.

## Chạy thử (không cần chờ người 1)

1. Chạy `01_schema\00_run_all.sql` như README.
2. Chạy `scripts\04_recommendations_prediction.sql`, rồi `scripts\04_recommendations_demo_seed.sql` (idempotent, dùng học sinh `student1@gmail.com`).
3. Ghép vào app theo mục dưới, đăng nhập bằng `student1@gmail.com` / `123456`, mở mục **Gợi ý & dự đoán**, bấm **Cập nhật dự đoán** và **Tạo gợi ý mới**.

Nếu chưa chạy script `04_recommendations_prediction.sql`, API vẫn chạy nhưng bỏ qua bước dựng hồ sơ năng lực từ lịch sử bài làm.

## API (chỉ tài khoản học sinh, POST cần `X-CSRF-Token`)

| Method | Đường dẫn | Việc làm |
| --- | --- | --- |
| GET | `/api/recommendations` | Danh sách gợi ý kèm lý do, cách cải thiện, mức ưu tiên |
| POST | `/api/recommendations/generate` | Chạy `sp_GenerateRecommendations`, trả số gợi ý mới |
| POST | `/api/recommendations/<id>/respond` | Body `{"accepted": true/false}`, chỉ đổi được gợi ý của chính mình |
| GET | `/api/predictions/latest` | Dự đoán mới nhất, thành phần điểm, bước cải thiện, độ đầy đủ dữ liệu, lịch sử |
| POST | `/api/predictions/refresh` | Chạy `sp_CalculateScorePrediction` (giữ kết quả cũ nếu dữ liệu chưa đổi và dưới 60 giây) |

## Ghép vào project (việc của người 4)

`06_web_app/app.py`:

```python
from recommendations import bp as recommendations_bp
app.register_blueprint(recommendations_bp)
```

`vite_app/src/App.jsx`:

```jsx
import RecommendationsPage from "./features/recommendations/RecommendationsPage.jsx";

// loadPageData: bỏ qua tải dashboard cho trang này
} else if (currentPage !== "exams" && currentPage !== "recommendations") {

// thanh điều hướng
<button className={`nav-link ${page === "recommendations" ? "active" : ""}`} onClick={() => navigate("recommendations")}><span className="nav-icon">✧</span>Gợi ý &amp; dự đoán</button>

// vùng nội dung, cạnh nhánh page === "exams"
) : page === "recommendations" ? (
  <RecommendationsPage />
```

Đã thử ghép các đoạn trên vào một bản sao: `App.jsx` biên dịch được và toàn bộ test Python vẫn chạy.

## Đây là thuật toán gì (giao diện đều ghi rõ)

- **Gợi ý**: thuật toán luật. Chủ đề có mức thành thạo dưới 65% được gợi ý học liệu ngắn nhất; câu đã làm sai được gợi ý ôn lại. Không dùng mô hình học máy.
- **Dự đoán**: công thức trọng số 55% mức thành thạo + 30% điểm đề gần nhất + 15% thời lượng học 7 ngày. Không phải học máy.
- **Khả năng đạt mục tiêu**: ước lượng heuristic (tối đa 0,85 khi chưa đạt, 0,90 khi đạt), chưa hiệu chuẩn hay kiểm chứng. Không trình bày như xác suất thật.
- Mỗi dự đoán kèm **độ đầy đủ dữ liệu** (số câu đã làm, số năng lực có dữ liệu) và cảnh báo khi dữ liệu đã đổi sau lần dự đoán cuối.

## Lưu ý với các phần khác

- `submit_attempt` trong `exam_service.py` chưa cập nhật `StudentCompetency`. Nếu luồng làm bài/chẩn đoán (người 1) không cập nhật mức thành thạo, hãy gọi `EXEC dbo.sp_SyncMasteryFromAnswers @StudentID, @Overwrite = 1` sau khi nộp bài. Mặc định thủ tục chỉ thêm năng lực chưa có dòng, không ghi đè.
- Dashboard hiện coi `IsAccepted = 0` là gợi ý chưa xử lý; module này hiển thị trạng thái đó là "Chưa chấp nhận".
- `tests/test_tutor.py` (người 3) đăng ký blueprint trong `setUpClass`, gây lỗi khi chạy cả bộ vì app đã nhận request. Lỗi này có sẵn ở bản gốc, không do module này.

## Kiểm thử

```powershell
python -m unittest tests.test_recommendations -v   # chạy trong 06_web_app
```

Gồm công thức dự đoán (đối chiếu số tính tay), các bước cải thiện, phân quyền, CSRF, đổi gợi ý của người khác (404), và logic dùng lại/tính mới dự đoán bằng kết nối SQL giả lập.

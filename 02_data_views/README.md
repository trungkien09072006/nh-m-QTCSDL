# 02_data_views – Tầng View dữ liệu của NovaPath

Đề tài: **Hệ thống cá nhân hóa lộ trình học và luyện thi Đánh giá năng lực tích hợp AI**
(AI-powered Personalized Learning Path Platform for Competency Assessment Exam Preparation).

CSDL: SQL Server – `AILearningDB` (schema `dbo`). Mọi file chạy lại được (`CREATE OR ALTER`), không xóa dữ liệu.

## Thứ tự chạy

| # | File | Nội dung |
|---|---|---|
| 01 | `01_vw_users_students.sql` | Tổng quan học sinh, phụ huynh - con em |
| 02 | `02_vw_content.sql` | Cây năng lực, học liệu, ngân hàng câu hỏi, đề thi |
| 03 | `03_vw_exam_results.sql` | Kết quả lượt làm, xem lại bài, thống kê câu hỏi, xếp hạng |
| 04 | `04_vw_personalization.sql` | Learning Profile, lộ trình, gợi ý, dự đoán điểm |
| 05 | `05_vw_analytics.sql` | Thời gian học, thông báo, AI Tutor, dashboard phụ huynh, tổng quan hệ thống, indexed view |
| 06 | `06_vw_ai_learning_analytics.sql` | Chẩn đoán, độ chính xác theo năng lực, chuỗi trả lời, đặc trưng cho AI, chất lượng gợi ý/câu hỏi |
| 07 | `07_vw_alerts_admin.sql` | Cảnh báo học tập, mức độ sẵn sàng thi, danh bạ người dùng, cấu hình, audit, hoạt động nền tảng |
| 08 | `08_vw_parameterized_updatable.sql` | Hàm bảng inline (view có tham số), view cập nhật được `WITH CHECK OPTION`, `INSTEAD OF` trigger |
| 09 | `09_view_permissions.sql` | Cấp quyền SELECT/UPDATE trên view/hàm theo vai trò |
| 10 | `10_view_tests.sql` | Kiểm thử (chạy riêng, không nằm trong `00_run_all.sql`) |

`vw_StudentExamView` (chống lộ đáp án khi làm bài) đã có trong `04_security\04_row_level_security.sql`, không tạo lại ở đây.

## Ánh xạ với yêu cầu đề tài

### Core Flow
| Core Flow | View / hàm |
|---|---|
| 1. Chẩn đoán năng lực & Learning Profile | `vw_DiagnosticResults`, `vw_CompetencyAccuracy`, `vw_StudentCompetencyProfile`, `vw_SubjectMastery`, `vw_StudentOverview` |
| 2. Lập lộ trình học cá nhân hóa | `vw_LearningPathProgress`, `vw_LearningPathItems`, `vw_ActiveLearningPaths`, `fn_WeakCompetencies` |
| 3. Học thích ứng & gợi ý liên tục | `vw_Recommendations`, `vw_AnswerHistory` (chuỗi cho Knowledge Tracing), `fn_PracticeCandidates`, `vw_AvailableExams`, `vw_StudentExamView` |
| 4. Hỗ trợ học bằng AI Tutor | `vw_TutorConversation`, `vw_TutorUsage` |
| 5. Phân tích học tập & theo dõi tiến độ | `vw_StudyActivitySummary`, `vw_DailyStudyTime`, `vw_WeeklyStudyTime`, `vw_StudyConsistency`, `fn_StudyTimeBetween`, `fn_ScoreTrend` |
| 6. Dự đoán kết quả thi | `vw_LatestPrediction`, `vw_AIStudentFeatures`, `vw_ExamReadiness` |

### Vai trò
| Vai trò | Chức năng trong đề tài | View / hàm |
|---|---|---|
| Administrator | Quản lý người dùng, cấu hình AI/hệ thống, giám sát vận hành | `vw_UserDirectory`, `vw_SystemSettings` (che giá trị nhạy cảm), `vw_AuditTrail`, `vw_PlatformActivityDaily`, `vw_SystemOverview` |
| Teacher | Quản lý học liệu, ngân hàng câu hỏi, đề thi; đánh giá chất lượng câu hỏi; theo dõi tiến độ; giám sát chất lượng gợi ý AI | `vw_CompetencyTree`, `vw_LearningResourceCatalog`, `vw_QuestionBank`, `vw_ExamSummary`, `vw_QuestionStatistics`, `vw_QuestionQuality`, `vw_OptionDistribution`, `vw_ExamRanking`, `vw_RecommendationQuality`, `fn_ExamResults`, các view tiến độ học sinh |
| Student | Làm chẩn đoán, đặt mục tiêu điểm, theo lộ trình, luyện tập, xem dashboard, hỏi AI Tutor, xem dự đoán | `vw_StudentEditableProfile`, `vw_AttemptResults`, `vw_AnswerReview` (chỉ lượt đã nộp), `vw_Recommendations`, `vw_LatestPrediction`, `vw_NotificationInbox` (đánh dấu đã đọc), các view/hàm cá nhân |
| Parent | Theo dõi tiến độ, báo cáo năng lực, nhận cảnh báo, theo dõi mục tiêu điểm, mức độ sẵn sàng thi | `vw_ParentChildren`, `vw_ParentDashboard`, `vw_StudentAlerts`, `vw_ExamReadiness`, `vw_StudentCompetencyProfile`, `vw_LatestPrediction`, `vw_WeeklyStudyTime` |
| AI Recommendation Engine (Role_App) | Phân tích hồ sơ, dự đoán, gợi ý | `vw_AIStudentFeatures`, `vw_AnswerHistory`, `vw_CompetencyAccuracy`, `fn_WeakCompetencies`, `fn_PracticeCandidates` |

## Kiến thức Hệ quản trị CSDL được thể hiện

| Kỹ thuật | Nơi dùng |
|---|---|
| View đơn bảng, view nhiều bảng (JOIN), che cột nhạy cảm | mọi view; không view nào có `PasswordHash`; `vw_SystemSettings` che giá trị khóa/bí mật |
| View tổng hợp (GROUP BY, COUNT/SUM/AVG), `OUTER APPLY` | `vw_SubjectMastery`, `vw_StudyActivitySummary`, `vw_StudentOverview` |
| Hàm cửa sổ (`ROW_NUMBER`, `RANK`, `SUM() OVER`, `LAG`) | `vw_StudentCompetencyProfile`, `vw_ExamRanking`, `vw_LatestPrediction`, `vw_AnswerHistory`, `fn_ScoreTrend` |
| CTE đệ quy | `vw_CompetencyTree` |
| Indexed view (`SCHEMABINDING`, `COUNT_BIG`, unique clustered index) | `vw_QuestionCountByCompetency` |
| Inline table-valued function (view có tham số) | `fn_WeakCompetencies`, `fn_PracticeCandidates`, `fn_StudyTimeBetween`, `fn_ScoreTrend`, `fn_ExamResults` |
| View cập nhật được + `WITH CHECK OPTION` | `vw_StudentEditableProfile`, `vw_ActiveLearningPaths` |
| `INSTEAD OF` trigger trên view | `tr_vw_NotificationInbox_MarkRead` |
| Phân quyền theo view, ownership chaining, `GRANT SELECT/UPDATE` | `09_view_permissions.sql` |
| Row-Level Security qua view | view luôn bắt đầu/JOIN từ bảng có RLS (`StudentProfiles`, `ExamAttempts`, `LearningPaths`, `ScorePredictions`, `StudyLogs`, `Notifications`) |
| Nhất quán với thủ tục có sẵn | ngưỡng `Mastery < 0.65`, 3 ngày không học, xác suất `< 0.70` trùng `sp_GenerateRecommendations`, `sp_GenerateNotifications` |

## Lưu ý
- Đề xuất ban đầu nêu PostgreSQL, nhưng mã nguồn nhóm đang dùng SQL Server nên các view viết bằng T-SQL.
- `ReadinessScore` trong `vw_ExamReadiness` là chỉ số tham khảo (trọng số 0.40 / 0.30 / 0.20 / 0.10), không thay thế dự đoán của AI.
- `vw_QuestionCountByCompetency` dùng `SCHEMABINDING`: muốn sửa các cột `CompetencyID`, `IsApproved`, `Difficulty` của `dbo.Questions` cần `DROP VIEW` trước.
- Seed hiện chỉ có đề `MOCK`, nên `vw_DiagnosticResults` rỗng cho tới khi có đề `DIAGNOSTIC`.
- Ghi chú trong code ghi rõ mục đích từng view; phần kiểm thử nằm ở `10_view_tests.sql`.

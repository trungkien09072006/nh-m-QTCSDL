USE AILearningDB;
GO

/*
===============================================================================
PHÂN HỆ 04 - BÀI TOÁN BẢO MẬT: PHẦN 2
MA TRẬN PHÂN QUYỀN ĐẶC QUYỀN TỐI THIỂU (LEAST PRIVILEGE DAC & RBAC)
===============================================================================
*/

PRINT '>>> [02_permissions_matrix.sql] Đang cấu hình ma trận phân quyền...';
GO

-- 1. QUYỀN CHO QUẢN TRỊ VIÊN (Role_Admin)

GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO Role_Admin;
GRANT EXECUTE ON SCHEMA::dbo TO Role_Admin;
GRANT VIEW DEFINITION TO Role_Admin;

-- 2. QUYỀN CHO GIÁO VIÊN / BIÊN SOẠN NỘI DUNG (Role_Teacher)

-- Quản trị ngân hàng đề, câu hỏi, học liệu
GRANT SELECT, INSERT, UPDATE ON dbo.Subjects TO Role_Teacher;
GRANT SELECT, INSERT, UPDATE ON dbo.Competencies TO Role_Teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.LearningResources TO Role_Teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Questions TO Role_Teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.QuestionOptions TO Role_Teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.Exams TO Role_Teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.ExamQuestions TO Role_Teacher;

-- Xem tiến độ và kết quả của học sinh
GRANT SELECT ON dbo.StudentProfiles TO Role_Teacher;
GRANT SELECT ON dbo.StudentCompetency TO Role_Teacher;
GRANT SELECT ON dbo.LearningPaths TO Role_Teacher;
GRANT SELECT ON dbo.LearningPathItems TO Role_Teacher;
GRANT SELECT ON dbo.ExamAttempts TO Role_Teacher;
GRANT SELECT ON dbo.AttemptAnswers TO Role_Teacher;
GRANT SELECT ON dbo.StudyLogs TO Role_Teacher;
GRANT SELECT ON dbo.ScorePredictions TO Role_Teacher;
GRANT SELECT ON dbo.Recommendations TO Role_Teacher;
GRANT SELECT ON dbo.Notifications TO Role_Teacher;

-- Xem thông tin người dùng, CẤM xem PasswordHash
GRANT SELECT ON dbo.Users TO Role_Teacher;
DENY SELECT ON dbo.Users(PasswordHash) TO Role_Teacher;

-- Cấm can thiệp bảng cấu hình và bảng nhật ký kiểm toán
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.SystemSettings TO Role_Teacher;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.AuditLog TO Role_Teacher;

-- Quyền thực thi các thủ tục hỗ trợ
GRANT EXECUTE ON dbo.sp_GenerateRecommendations TO Role_Teacher;
GRANT EXECUTE ON dbo.sp_CalculateScorePrediction TO Role_Teacher;
GRANT EXECUTE ON dbo.sp_GenerateNotifications TO Role_Teacher;

-- 3. QUYỀN CHO HỌC SINH (Role_Student)

-- Xem nội dung môn học và học liệu
GRANT SELECT ON dbo.Subjects TO Role_Student;
GRANT SELECT ON dbo.Competencies TO Role_Student;
GRANT SELECT ON dbo.LearningResources TO Role_Student;
GRANT SELECT ON dbo.Exams TO Role_Student;
GRANT SELECT ON dbo.ExamQuestions TO Role_Student;

-- Làm bài và ghi nhận kết quả thi
GRANT SELECT, INSERT, UPDATE ON dbo.ExamAttempts TO Role_Student;
GRANT SELECT, INSERT, UPDATE ON dbo.AttemptAnswers TO Role_Student;

-- Xem thông tin học tập, lộ trình, gợi ý cá nhân
GRANT SELECT, UPDATE ON dbo.StudentProfiles TO Role_Student;
GRANT SELECT ON dbo.StudentCompetency TO Role_Student;
GRANT SELECT ON dbo.LearningPaths TO Role_Student;
GRANT SELECT, UPDATE ON dbo.LearningPathItems TO Role_Student;
GRANT SELECT, UPDATE ON dbo.Recommendations TO Role_Student;
GRANT SELECT ON dbo.ScorePredictions TO Role_Student;
GRANT SELECT, INSERT ON dbo.StudyLogs TO Role_Student;
GRANT SELECT, UPDATE ON dbo.Notifications TO Role_Student;

-- Chat với trợ lý AI Tutor
GRANT SELECT, INSERT ON dbo.TutorSessions TO Role_Student;
GRANT SELECT, INSERT ON dbo.TutorMessages TO Role_Student;

-- Xem Users (Phone/Email đã được Dynamic Data Masking che mờ), CẤM xem PasswordHash
GRANT SELECT ON dbo.Users TO Role_Student;
DENY SELECT ON dbo.Users(PasswordHash) TO Role_Student;

-- Cấm tuyệt đối can thiệp sửa đổi nội dung và hệ thống
DENY INSERT, UPDATE, DELETE ON dbo.Subjects TO Role_Student;
DENY INSERT, UPDATE, DELETE ON dbo.Competencies TO Role_Student;
DENY INSERT, UPDATE, DELETE ON dbo.LearningResources TO Role_Student;
DENY INSERT, UPDATE, DELETE ON dbo.Questions TO Role_Student;
DENY INSERT, UPDATE, DELETE ON dbo.QuestionOptions TO Role_Student;
DENY INSERT, UPDATE, DELETE ON dbo.Exams TO Role_Student;
DENY INSERT, UPDATE, DELETE ON dbo.ExamQuestions TO Role_Student;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.SystemSettings TO Role_Student;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.AuditLog TO Role_Student;

-- Quyền thực thi thủ tục nghiệp vụ
GRANT EXECUTE ON dbo.sp_AskTutor TO Role_Student;
GRANT EXECUTE ON dbo.sp_GenerateRecommendations TO Role_Student;
GRANT EXECUTE ON dbo.sp_CalculateScorePrediction TO Role_Student;
GRANT EXECUTE ON dbo.sp_GenerateNotifications TO Role_Student;

-------------------------------------------------------------------------------
-- 4. QUYỀN CHO PHỤ HUYNH (Role_Parent)
-------------------------------------------------------------------------------
GRANT SELECT ON dbo.ParentStudent TO Role_Parent;
GRANT SELECT ON dbo.StudentProfiles TO Role_Parent;
GRANT SELECT ON dbo.StudentCompetency TO Role_Parent;
GRANT SELECT ON dbo.LearningPaths TO Role_Parent;
GRANT SELECT ON dbo.LearningPathItems TO Role_Parent;
GRANT SELECT ON dbo.ExamAttempts TO Role_Parent;
GRANT SELECT ON dbo.AttemptAnswers TO Role_Parent;
GRANT SELECT ON dbo.ScorePredictions TO Role_Parent;
GRANT SELECT ON dbo.StudyLogs TO Role_Parent;
GRANT SELECT, UPDATE ON dbo.Notifications TO Role_Parent;
GRANT SELECT ON dbo.Subjects TO Role_Parent;
GRANT SELECT ON dbo.Competencies TO Role_Parent;

GRANT SELECT ON dbo.Users TO Role_Parent;
DENY SELECT ON dbo.Users(PasswordHash) TO Role_Parent;

DENY INSERT, UPDATE, DELETE ON dbo.ExamAttempts TO Role_Parent;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.Questions TO Role_Parent;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.QuestionOptions TO Role_Parent;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.SystemSettings TO Role_Parent;
DENY SELECT, INSERT, UPDATE, DELETE ON dbo.AuditLog TO Role_Parent;

-------------------------------------------------------------------------------
-- 5. QUYỀN CHO BACKEND ỨNG DỤNG (Role_App)
-------------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO Role_App;
GRANT EXECUTE ON SCHEMA::dbo TO Role_App;

-- Tính bất biến của AuditLog: Không cho phép sửa đổi hay xóa nhật ký kiểm toán
DENY UPDATE, DELETE ON dbo.AuditLog TO Role_Admin;
DENY UPDATE, DELETE ON dbo.AuditLog TO Role_Teacher;
DENY UPDATE, DELETE ON dbo.AuditLog TO Role_Student;
DENY UPDATE, DELETE ON dbo.AuditLog TO Role_Parent;
DENY UPDATE, DELETE ON dbo.AuditLog TO Role_App;

PRINT '    + Đã cấu hình hoàn tất ma trận phân quyền.';
GO

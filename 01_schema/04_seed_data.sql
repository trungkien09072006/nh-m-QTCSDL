USE AILearningDB;
GO

SET NOCOUNT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    /* ===== 0. KHAI BÁO BIẾN DÙNG CHUNG (T-SQL Variables) ===== */
    -- Mật khẩu mẫu cho tất cả user: 123456
    DECLARE @PassHash VARBINARY(256) = HASHBYTES('SHA2_256', N'123456');
    
    -- Lấy sẵn RoleID
    DECLARE @RoleAdmin INT = (SELECT RoleID FROM Roles WHERE RoleName = 'Admin');
    DECLARE @RoleTeacher INT = (SELECT RoleID FROM Roles WHERE RoleName = 'Teacher');
    DECLARE @RoleStudent INT = (SELECT RoleID FROM Roles WHERE RoleName = 'Student');
    DECLARE @RoleParent INT = (SELECT RoleID FROM Roles WHERE RoleName = 'Parent');

    /* ===== 1. NGƯỜI DÙNG (USERS) ===== */
    INSERT INTO Users (RoleID, Email, PasswordHash, FullName, Phone) VALUES 
    (@RoleAdmin, 'admin@ai-edu.vn', @PassHash, N'Quản trị viên', '0901234567'),
    (@RoleTeacher, 'teacher@ai-edu.vn', @PassHash, N'Thầy Nguyễn Văn Giáo', '0901234568'),
    (@RoleStudent, 'student1@gmail.com', @PassHash, N'Trần Văn Học', '0901234569'),
    (@RoleStudent, 'student2@gmail.com', @PassHash, N'Lê Thị Chăm', '0901234570'),
    (@RoleParent, 'parent1@gmail.com', @PassHash, N'Trần Văn Phụ Huynh', '0901234571');

    -- Khai báo ID User vừa tạo
    DECLARE @TeacherID INT = (SELECT UserID FROM Users WHERE Email = 'teacher@ai-edu.vn');
    DECLARE @Stu1ID INT = (SELECT UserID FROM Users WHERE Email = 'student1@gmail.com');
    DECLARE @Stu2ID INT = (SELECT UserID FROM Users WHERE Email = 'student2@gmail.com');
    DECLARE @Par1ID INT = (SELECT UserID FROM Users WHERE Email = 'parent1@gmail.com');

    /* ===== 2. HỒ SƠ HỌC SINH & PHỤ HUYNH ===== */
    INSERT INTO StudentProfiles (StudentID, SchoolName, TargetScore, ExamDate, DailyStudyMin) VALUES 
    (@Stu1ID, N'THPT Chuyên Hà Nội - Amsterdam', 950, '2025-06-15', 120),
    (@Stu2ID, N'THPT Kim Liên', 850, '2025-06-20', 90);

    INSERT INTO ParentStudent (ParentID, StudentID) VALUES (@Par1ID, @Stu1ID);

    /* ===== 3. MÔN HỌC & NĂNG LỰC ===== */
    INSERT INTO Subjects (SubjectName, Description) VALUES 
    (N'Tư duy logic', N'Khả năng suy luận, phân tích quy luật, giải quyết vấn đề'),
    (N'Định lượng', N'Toán học, xử lý số liệu, đại số và hình học'),
    (N'Đọc hiểu', N'Đọc hiểu văn bản, phân tích ngôn ngữ');

    -- Lấy SubjectID
    DECLARE @SubLogic INT = (SELECT SubjectID FROM Subjects WHERE SubjectName = N'Tư duy logic');
    DECLARE @SubQuant INT = (SELECT SubjectID FROM Subjects WHERE SubjectName = N'Định lượng');

    INSERT INTO Competencies (SubjectID, CompetencyName) VALUES 
    (@SubLogic, N'Suy luận logic'),
    (@SubLogic, N'Phân tích quy luật'),
    (@SubQuant, N'Đại số'),
    (@SubQuant, N'Hình học');

    -- Lấy CompetencyID
    DECLARE @CompLogic INT = (SELECT CompetencyID FROM Competencies WHERE CompetencyName = N'Suy luận logic');
    DECLARE @CompAlgebra INT = (SELECT CompetencyID FROM Competencies WHERE CompetencyName = N'Đại số');

    /* ===== 4. HỌC LIỆU ===== */
    INSERT INTO LearningResources (CompetencyID, Title, ResourceType, Url, EstimatedMin, CreatedBy) VALUES 
    (@CompLogic, N'Video: Các dạng bài toán Logic phổ biến', 'VIDEO', 'https://youtube.com/watch?v=logic1', 20, @TeacherID),
    (@CompAlgebra, N'Chuyên đề: Hàm số và Đồ thị', 'ARTICLE', 'https://ai-edu.vn/tailieu/hamso', 15, @TeacherID);

    DECLARE @ResAlgebraID INT = (SELECT ResourceID FROM LearningResources WHERE Title LIKE N'Chuyên đề: Hàm số%');

    /* ===== 5. CÂU HỎI & ĐÁP ÁN ===== */
    -- Câu hỏi 1 (Logic)
    INSERT INTO Questions (CompetencyID, Content, Difficulty, Explanation, IsAIGenerated, IsApproved, CreatedBy) VALUES 
    (@CompLogic, N'Cho dãy số: 2, 6, 12, 20, 30. Số tiếp theo là gì?', 3, N'Quy luật: n*(n+1). 1*2=2, 2*3=6, 3*4=12, 4*5=20, 5*6=30. Vậy 6*7=42.', 0, 1, @TeacherID);
    DECLARE @Q1ID INT = SCOPE_IDENTITY();

    INSERT INTO QuestionOptions (QuestionID, OptionLabel, OptionText, IsCorrect) VALUES
    (@Q1ID, 'A', '40', 0),
    (@Q1ID, 'B', '42', 1),
    (@Q1ID, 'C', '44', 0),
    (@Q1ID, 'D', '46', 0);

    -- Câu hỏi 2 (Đại số)
    INSERT INTO Questions (CompetencyID, Content, Difficulty, Explanation, IsAIGenerated, IsApproved, CreatedBy) VALUES 
    (@CompAlgebra, N'Giải phương trình: 2x + 5 = 15. Nghiệm x là?', 2, N'2x = 10 => x = 5.', 0, 1, @TeacherID);
    DECLARE @Q2ID INT = SCOPE_IDENTITY();

    INSERT INTO QuestionOptions (QuestionID, OptionLabel, OptionText, IsCorrect) VALUES
    (@Q2ID, 'A', '3', 0),
    (@Q2ID, 'B', '4', 0),
    (@Q2ID, 'C', '5', 1),
    (@Q2ID, 'D', '6', 0);

    /* ===== 6. BÀI THI & LÀM BÀI ===== */
    INSERT INTO Exams (Title, ExamType, DurationMin, CreatedBy) VALUES 
    (N'Đề thi thử ĐGNL ĐHQG Hà Nội - Đợt 1', 'MOCK', 120, @TeacherID);
    DECLARE @ExamID INT = SCOPE_IDENTITY();

    INSERT INTO ExamQuestions (ExamID, QuestionID, OrderNo) VALUES 
    (@ExamID, @Q1ID, 1),
    (@ExamID, @Q2ID, 2);

    -- Học sinh 1 làm bài
    INSERT INTO ExamAttempts (ExamID, StudentID, StartedAt, SubmittedAt, Score) VALUES 
    (@ExamID, @Stu1ID, DATEADD(HOUR, -2, SYSDATETIME()), SYSDATETIME(), 50.00);
    DECLARE @AttemptID INT = SCOPE_IDENTITY();

    -- Điền đáp án (Đúng câu 1, sai câu 2)
    INSERT INTO AttemptAnswers (AttemptID, QuestionID, SelectedOption, IsCorrect, TimeSpentSec) VALUES 
    (@AttemptID, @Q1ID, (SELECT OptionID FROM QuestionOptions WHERE QuestionID = @Q1ID AND OptionText = '42'), 1, 45),
    (@AttemptID, @Q2ID, (SELECT OptionID FROM QuestionOptions WHERE QuestionID = @Q2ID AND OptionText = '3'), 0, 60);

    /* ===== 7. CÁ NHÂN HÓA & AI ===== */
    -- Cập nhật hồ sơ năng lực
    INSERT INTO StudentCompetency (StudentID, CompetencyID, Mastery, AttemptCount) VALUES 
    (@Stu1ID, @CompLogic, 0.8000, 1),  -- Làm đúng
    (@Stu1ID, @CompAlgebra, 0.2000, 1); -- Làm sai

    -- Lộ trình học tập (PathID)
    INSERT INTO LearningPaths (StudentID, StartDate, EndDate, Status) VALUES 
    (@Stu1ID, CAST(GETDATE() AS DATE), DATEADD(DAY, 30, CAST(GETDATE() AS DATE)), 'ACTIVE');
    DECLARE @PathID INT = SCOPE_IDENTITY();

    -- Chi tiết lộ trình (Gợi ý học Đại số)
    INSERT INTO LearningPathItems (PathID, CompetencyID, ResourceID, ScheduledDate, Priority, Status) VALUES 
    (@PathID, @CompAlgebra, @ResAlgebraID, DATEADD(DAY, 1, CAST(GETDATE() AS DATE)), 1, 'TODO');

    -- Gợi ý từ AI
    INSERT INTO Recommendations (StudentID, QuestionID, ResourceID, Reason, IsAccepted) VALUES 
    (@Stu1ID, NULL, @ResAlgebraID, N'Điểm số phần Đại số của bạn đang thấp, hãy xem tài liệu này để củng cố kiến thức.', 0);

    -- Dự đoán điểm
    INSERT INTO ScorePredictions (StudentID, PredictedScore, ProbReachTarget, RiskNote) VALUES 
    (@Stu1ID, 880.50, 0.6500, N'Nguy cơ không đạt mục tiêu nếu không cải thiện tốc độ làm bài Định lượng.');

    -- AI Tutor (Session)
    INSERT INTO TutorSessions (StudentID) VALUES (@Stu1ID);
    DECLARE @SessionID INT = SCOPE_IDENTITY();

    INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID, SentAt) VALUES 
    (@SessionID, 'USER', N'Tại sao câu 1 đáp án lại là 42 vậy ạ?', @Q1ID, DATEADD(MINUTE, -10, SYSDATETIME())),
    (@SessionID, 'AI', N'Chào bạn, đây là quy luật dãy số: 1x2=2, 2x3=6, 3x4=12, 4x5=20, 5x6=30. Vậy số tiếp theo là 6x7=42 nhé!', @Q1ID, DATEADD(MINUTE, -9, SYSDATETIME()));

    -- Nhật ký học tập
    INSERT INTO StudyLogs (StudentID, ActivityType, DurationMin, LoggedAt) VALUES 
    (@Stu1ID, 'LESSON', 45, DATEADD(HOUR, -3, SYSDATETIME())),
    (@Stu1ID, 'MOCK', 120, DATEADD(HOUR, -2, SYSDATETIME())),
    (@Stu1ID, 'TUTOR', 15, DATEADD(MINUTE, -10, SYSDATETIME()));

    -- Hoàn tất giao dịch
    COMMIT TRANSACTION;
    PRINT N'>> Chèn dữ liệu mẫu (Seed Data) thành công!';
END TRY
BEGIN CATCH
    -- Nếu có lỗi, Rollback toàn bộ
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    PRINT N'>> Lỗi xảy ra khi chèn dữ liệu: ' + ERROR_MESSAGE();
    THROW;
END CATCH;
GO
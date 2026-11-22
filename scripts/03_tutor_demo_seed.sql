
USE AILearningDB;
GO

SET NOCOUNT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    PRINT N'Bắt đầu nạp dữ liệu kiểm thử độc lập cho AI Tutor...';

    -- 1. Tìm hoặc gán giáo viên & học sinh mẫu
    DECLARE @TeacherID INT = (SELECT TOP 1 UserID FROM Users WHERE RoleID = (SELECT RoleID FROM Roles WHERE RoleName = 'Teacher'));
    DECLARE @StudentID INT = (SELECT TOP 1 UserID FROM Users WHERE RoleID = (SELECT RoleID FROM Roles WHERE RoleName = 'Student'));
    DECLARE @CompLogic INT = (SELECT TOP 1 CompetencyID FROM Competencies WHERE CompetencyName LIKE N'%logic%');

    IF @CompLogic IS NULL
        SET @CompLogic = (SELECT TOP 1 CompetencyID FROM Competencies);

    -- 2. Thêm câu hỏi kiểm thử có lời giải chi tiết (nếu chưa có)
    IF NOT EXISTS (SELECT 1 FROM Questions WHERE Content LIKE N'%Hình hộp chữ nhật có ba kích thước%')
    BEGIN
        INSERT INTO Questions (CompetencyID, Content, Difficulty, Explanation, IsAIGenerated, IsApproved, CreatedBy)
        VALUES (
            @CompLogic,
            N'Một hình hộp chữ nhật có ba kích thước tỉ lệ với 1, 2, 3 và thể tích bằng 48 cm³. Diện tích toàn phần của hình hộp là bao nhiêu?',
            3,
            N'Gọi ba kích thước là x, 2x, 3x (x > 0). Thể tích V = x * 2x * 3x = 6x³ = 48 => x³ = 8 => x = 2 cm. Ba kích thước lần lượt là 2 cm, 4 cm, 6 cm. Diện tích toàn phần S = 2 * (2*4 + 4*6 + 6*2) = 2 * (8 + 24 + 12) = 88 cm².',
            0,
            1,
            @TeacherID
        );
        DECLARE @NewQID INT = SCOPE_IDENTITY();

        INSERT INTO QuestionOptions (QuestionID, OptionLabel, OptionText, IsCorrect) VALUES
        (@NewQID, 'A', '72 cm²', 0),
        (@NewQID, 'B', '88 cm²', 1),
        (@NewQID, 'C', '96 cm²', 0),
        (@NewQID, 'D', '108 cm²', 0);

        PRINT N'Đã thêm câu hỏi kiểm thử hình học / định lượng (ID: ' + CAST(@NewQID AS NVARCHAR(10)) + N')';
    END

    -- 3. Tạo phiên hội thoại và tin nhắn mẫu cho học sinh đầu tiên (nếu chưa có tin nhắn nào)
    IF @StudentID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM TutorSessions WHERE StudentID = @StudentID)
    BEGIN
        INSERT INTO TutorSessions (StudentID, StartedAt)
        VALUES (@StudentID, SYSDATETIME());

        DECLARE @SessionID INT = SCOPE_IDENTITY();
        DECLARE @FirstQID INT = (SELECT TOP 1 QuestionID FROM Questions ORDER BY QuestionID ASC);

        -- Tin nhắn 1 của học sinh
        INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID, SentAt)
        VALUES (
            @SessionID,
            'USER',
            N'Chào AI Tutor, nhờ bạn giải thích giúp em quy luật của câu hỏi này với ạ!',
            @FirstQID,
            DATEADD(MINUTE, -10, SYSDATETIME())
        );

        -- Tin nhắn 1 phản hồi của AI
        INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID, SentAt)
        VALUES (
            @SessionID,
            'AI',
            N'> **[Chế độ: Tri thức NovaPath (RAG nội bộ)]**' + CHAR(13) + CHAR(10) +
            N'Chào em! Ở câu hỏi này, quy luật của dãy số là dạng tích hai số nguyên liên tiếp n * (n + 1).' + CHAR(13) + CHAR(10) +
            N'- Số thứ 1: 1 * 2 = 2' + CHAR(13) + CHAR(10) +
            N'- Số thứ 2: 2 * 3 = 6' + CHAR(13) + CHAR(10) +
            N'- Số thứ 3: 3 * 4 = 12' + CHAR(13) + CHAR(10) +
            N'- Số thứ 4: 4 * 5 = 20' + CHAR(13) + CHAR(10) +
            N'- Số thứ 5: 5 * 6 = 30' + CHAR(13) + CHAR(10) +
            N'Do đó, số tiếp theo (thứ 6) là: 6 * 7 = **42** (Phương án B).' + CHAR(13) + CHAR(10) +
            N'💡 **Mẹo:** Dạng dãy số tăng dần như thế này em nên thử xét hiệu hai số liên tiếp (4, 6, 8, 10...) hoặc tách nhân tử để tìm quy luật nhanh nhé!',
            @FirstQID,
            DATEADD(MINUTE, -9, SYSDATETIME())
        );

        -- Ghi nhật ký học tập
        INSERT INTO StudyLogs (StudentID, ActivityType, DurationMin, LoggedAt)
        VALUES (@StudentID, 'TUTOR', 10, DATEADD(MINUTE, -9, SYSDATETIME()));

        PRINT N'Đã tạo phiên hội thoại và tin nhắn kiểm thử cho StudentID = ' + CAST(@StudentID AS NVARCHAR(10));
    END

    COMMIT TRANSACTION;
    PRINT N'Nạp dữ liệu kiểm thử AI Tutor thành công!';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    DECLARE @ErrMsg NVARCHAR(4000) = ERROR_MESSAGE();
    RAISERROR(@ErrMsg, 16, 1);
END CATCH;
GO

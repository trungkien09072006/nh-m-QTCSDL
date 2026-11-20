USE AILearningDB;
GO

SET NOCOUNT ON;

DECLARE @ExamTitle NVARCHAR(200) = N'Bài chẩn đoán năng lực mẫu';
DECLARE @TeacherID INT = (
    SELECT TOP (1) u.UserID
    FROM dbo.Users AS u
    INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
    WHERE r.RoleName = 'Teacher'
    ORDER BY u.UserID
);
DECLARE @QuestionList TABLE (QuestionID INT PRIMARY KEY, OrderNo INT NOT NULL);
DECLARE @DiagnosticExamID INT;

IF @TeacherID IS NULL
    THROW 50001, N'Cần có tài khoản giáo viên trước khi tạo đề chẩn đoán mẫu.', 1;

INSERT INTO @QuestionList (QuestionID, OrderNo)
SELECT q.QuestionID, ROW_NUMBER() OVER (ORDER BY q.CreatedAt, q.QuestionID)
FROM (
    SELECT TOP (10) QuestionID, CreatedAt
    FROM dbo.Questions
    WHERE IsApproved = 1
    ORDER BY CreatedAt, QuestionID
) AS q;

IF NOT EXISTS (SELECT 1 FROM @QuestionList)
BEGIN
    PRINT N'Chưa có câu hỏi được duyệt; bỏ qua đề chẩn đoán mẫu.';
    RETURN;
END;

SELECT @DiagnosticExamID = ExamID
FROM dbo.Exams
WHERE Title = @ExamTitle AND ExamType = 'DIAGNOSTIC';

IF @DiagnosticExamID IS NULL
BEGIN
    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO dbo.Exams (Title, ExamType, DurationMin, CreatedBy)
        VALUES (@ExamTitle, 'DIAGNOSTIC', 20, @TeacherID);

        SET @DiagnosticExamID = SCOPE_IDENTITY();

        INSERT INTO dbo.ExamQuestions (ExamID, QuestionID, OrderNo)
        SELECT @DiagnosticExamID, QuestionID, OrderNo
        FROM @QuestionList;

        COMMIT TRANSACTION;
        PRINT N'Đã tạo đề chẩn đoán năng lực mẫu.';
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

USE AILearningDB;
GO


PRINT '>>> [04_row_level_security.sql] Đang cấu hình Row-Level Security...';
GO

-- 1. THỦ TỤC THIẾT LẬP SESSION CONTEXT
CREATE OR ALTER PROCEDURE dbo.sp_SetSecurityContext
    @UserID   INT,
    @RoleName NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    EXEC sp_set_session_context @key = N'CurrentUserID', @value = @UserID;
    IF @RoleName IS NOT NULL
        EXEC sp_set_session_context @key = N'CurrentUserRole', @value = @RoleName;
END;
GO

GRANT EXECUTE ON dbo.sp_SetSecurityContext TO Role_Admin, Role_Teacher, Role_Student, Role_Parent, Role_App;
GO

-- 2. HÀM PREDICATE CHO DỮ LIỆU HỌC SINH (ExamAttempts, StudentProfiles, ...)
CREATE OR ALTER FUNCTION dbo.fn_SecurityPredicate_StudentData(@StudentID INT)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN (
    SELECT 1 AS AccessResult
    WHERE
        -- Quản trị viên, Giáo viên, Web App, sa có toàn quyền truy cập
        IS_ROLEMEMBER('db_owner') = 1
        OR IS_ROLEMEMBER('Role_Admin') = 1
        OR IS_ROLEMEMBER('Role_Teacher') = 1
        OR IS_ROLEMEMBER('Role_App') = 1
        OR SUSER_SNAME() = 'sa'
        
        -- Học sinh: Chỉ xem được dữ liệu của chính mình
        OR (
            (IS_ROLEMEMBER('Role_Student') = 1 OR CAST(SESSION_CONTEXT(N'CurrentUserRole') AS NVARCHAR(50)) = N'Student')
            AND @StudentID = CAST(SESSION_CONTEXT(N'CurrentUserID') AS INT)
        )
        
        -- Phụ huynh: Chỉ xem được dữ liệu của con em mình (liên kết qua bảng ParentStudent)
        OR (
            (IS_ROLEMEMBER('Role_Parent') = 1 OR CAST(SESSION_CONTEXT(N'CurrentUserRole') AS NVARCHAR(50)) = N'Parent')
            AND EXISTS (
                SELECT 1 FROM dbo.ParentStudent ps
                WHERE ps.ParentID = CAST(SESSION_CONTEXT(N'CurrentUserID') AS INT)
                  AND ps.StudentID = @StudentID
            )
        )
        
        -- Phiên làm việc quản trị khi chưa set Session Context
        OR (
            SESSION_CONTEXT(N'CurrentUserID') IS NULL
            AND IS_ROLEMEMBER('Role_Student') = 0
            AND IS_ROLEMEMBER('Role_Parent') = 0
        )
);
GO

-- 3. HÀM PREDICATE CHO THÔNG BÁO (Notifications)
CREATE OR ALTER FUNCTION dbo.fn_SecurityPredicate_Notifications(@UserID INT)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN (
    SELECT 1 AS AccessResult
    WHERE
        IS_ROLEMEMBER('db_owner') = 1
        OR IS_ROLEMEMBER('Role_Admin') = 1
        OR IS_ROLEMEMBER('Role_App') = 1
        OR SUSER_SNAME() = 'sa'
        
        -- Người dùng chỉ xem thông báo gửi đích danh cho mình
        OR (
            SESSION_CONTEXT(N'CurrentUserID') IS NOT NULL
            AND @UserID = CAST(SESSION_CONTEXT(N'CurrentUserID') AS INT)
        )
        
        OR (
            SESSION_CONTEXT(N'CurrentUserID') IS NULL
            AND IS_ROLEMEMBER('Role_Student') = 0
            AND IS_ROLEMEMBER('Role_Parent') = 0
        )
);
GO

-- 4. KÍCH HOẠT CÁC CHÍNH SÁCH BẢO MẬT (SECURITY POLICIES)
IF EXISTS (SELECT 1 FROM sys.security_policies WHERE name = 'sec_policy_StudentData')
    DROP SECURITY POLICY dbo.sec_policy_StudentData;

CREATE SECURITY POLICY dbo.sec_policy_StudentData
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.ExamAttempts,
    ADD BLOCK PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.ExamAttempts AFTER INSERT,
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.StudentProfiles,
    ADD BLOCK PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.StudentProfiles AFTER UPDATE,
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.StudentCompetency,
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.LearningPaths,
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.ScorePredictions,
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_StudentData(StudentID) ON dbo.StudyLogs
WITH (STATE = ON);
PRINT '    + Đã áp dụng Policy: sec_policy_StudentData';

IF EXISTS (SELECT 1 FROM sys.security_policies WHERE name = 'sec_policy_Notifications')
    DROP SECURITY POLICY dbo.sec_policy_Notifications;

CREATE SECURITY POLICY dbo.sec_policy_Notifications
    ADD FILTER PREDICATE dbo.fn_SecurityPredicate_Notifications(UserID) ON dbo.Notifications
WITH (STATE = ON);
PRINT '    + Đã áp dụng Policy: sec_policy_Notifications';
GO

-- 5. VIEW BẢO MẬT CHỐNG GIAN LẬN ĐỀ THI TRỰC TUYẾN
-- Học sinh làm bài thi trực tuyến chỉ được truy vấn qua View này để không lộ đáp án đúng
CREATE OR ALTER VIEW dbo.vw_StudentExamView
AS
SELECT 
    eq.ExamID,
    eq.OrderNo,
    q.QuestionID,
    q.CompetencyID,
    q.Content AS QuestionContent,
    q.Difficulty,
    qo.OptionID,
    qo.OptionLabel,
    qo.OptionText
    -- Không hiển thị qo.IsCorrect và q.Explanation
FROM dbo.ExamQuestions eq
INNER JOIN dbo.Questions q ON q.QuestionID = eq.QuestionID
INNER JOIN dbo.QuestionOptions qo ON qo.QuestionID = q.QuestionID
WHERE q.IsApproved = 1;
GO

GRANT SELECT ON dbo.vw_StudentExamView TO Role_Student;
PRINT '    + Đã tạo View: vw_StudentExamView';
GO

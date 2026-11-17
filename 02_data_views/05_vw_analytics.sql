USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 5
VIEW THỐNG KÊ, THÔNG BÁO, AI TUTOR, TỔNG QUAN HỆ THỐNG
===============================================================================
*/
PRINT '>>> [05_vw_analytics.sql] Đang tạo view thống kê...';
GO

/* ===== 1. TỔNG HỢP THỜI GIAN HỌC THEO LOẠI HOẠT ĐỘNG ===== */
CREATE OR ALTER VIEW dbo.vw_StudyActivitySummary
AS
SELECT
    sl.StudentID,
    sl.ActivityType,
    CASE sl.ActivityType
        WHEN 'LESSON' THEN N'Học bài'
        WHEN 'QUIZ'   THEN N'Kiểm tra nhanh'
        WHEN 'MOCK'   THEN N'Thi thử'
        WHEN 'TUTOR'  THEN N'Hỏi AI Tutor'
    END AS ActivityName,
    COUNT(*) AS SessionCount,
    SUM(sl.DurationMin) AS TotalMin,
    SUM(CASE WHEN sl.LoggedAt >= DATEADD(DAY, -7, SYSDATETIME()) THEN sl.DurationMin ELSE 0 END) AS Min7d,
    MAX(sl.LoggedAt) AS LastLoggedAt
FROM dbo.StudyLogs AS sl
GROUP BY sl.StudentID, sl.ActivityType;
GO

/* ===== 2. THỜI GIAN HỌC THEO NGÀY (dùng cho biểu đồ) ===== */
CREATE OR ALTER VIEW dbo.vw_DailyStudyTime
AS
SELECT
    sl.StudentID,
    CAST(sl.LoggedAt AS DATE) AS StudyDate,
    COUNT(*) AS SessionCount,
    SUM(sl.DurationMin) AS TotalMin
FROM dbo.StudyLogs AS sl
GROUP BY sl.StudentID, CAST(sl.LoggedAt AS DATE);
GO

/* ===== 3. THỜI GIAN HỌC THEO TUẦN SO VỚI MỤC TIÊU DailyStudyMin x 7 ===== */
CREATE OR ALTER VIEW dbo.vw_WeeklyStudyTime
AS
SELECT
    w.StudentID,
    w.WeekStart,                                   -- thứ Hai đầu tuần (không phụ thuộc DATEFIRST)
    DATEADD(DAY, 6, w.WeekStart) AS WeekEnd,
    w.SessionCount,
    w.TotalMin,
    sp.DailyStudyMin * 7 AS WeeklyGoalMin,
    CAST(100.0 * w.TotalMin / NULLIF(sp.DailyStudyMin * 7, 0) AS DECIMAL(7,2)) AS GoalAchievedPercent
FROM (
    SELECT
        sl.StudentID,
        CAST(DATEADD(DAY, DATEDIFF(DAY, 0, CAST(sl.LoggedAt AS DATE)) / 7 * 7, 0) AS DATE) AS WeekStart,
        COUNT(*) AS SessionCount,
        SUM(sl.DurationMin) AS TotalMin
    FROM dbo.StudyLogs AS sl
    GROUP BY sl.StudentID,
             CAST(DATEADD(DAY, DATEDIFF(DAY, 0, CAST(sl.LoggedAt AS DATE)) / 7 * 7, 0) AS DATE)
) AS w
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = w.StudentID;
GO

/* ===== 4. HỘP THƯ THÔNG BÁO ===== */
CREATE OR ALTER VIEW dbo.vw_NotificationInbox
AS
SELECT
    n.NotificationID,
    n.UserID,
    n.StudentID,
    su.FullName AS StudentName,
    n.NotifyType,
    CASE n.NotifyType
        WHEN 'INACTIVITY'      THEN N'Lâu không học'
        WHEN 'BEHIND_SCHEDULE' THEN N'Trễ lộ trình'
        WHEN 'LOW_PROBABILITY' THEN N'Xác suất đạt mục tiêu thấp'
    END AS NotifyTypeName,
    n.Message,
    n.IsRead,
    n.CreatedAt
FROM dbo.Notifications AS n
LEFT JOIN dbo.Users AS su ON su.UserID = n.StudentID;
GO

/* ===== 5. LỊCH SỬ TRÒ CHUYỆN VỚI AI TUTOR ===== */
CREATE OR ALTER VIEW dbo.vw_TutorConversation
AS
SELECT
    ts.SessionID,
    ts.StudentID,
    ts.StartedAt AS SessionStartedAt,
    tm.MessageID,
    tm.Sender,
    CASE tm.Sender WHEN 'USER' THEN N'Học sinh' ELSE N'AI Tutor' END AS SenderName,
    tm.Content,
    tm.QuestionID,
    tm.SentAt
FROM dbo.TutorSessions AS ts
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = ts.StudentID    -- RLS
INNER JOIN dbo.TutorMessages AS tm ON tm.SessionID = ts.SessionID;
GO

/* ===== 6. BẢNG ĐIỀU KHIỂN PHỤ HUYNH (mỗi dòng = một người con) ===== */
CREATE OR ALTER VIEW dbo.vw_ParentDashboard
AS
SELECT
    ps.ParentID,
    o.StudentID,
    o.FullName AS StudentName,
    o.SchoolName,
    o.TargetScore,
    o.ExamDate,
    o.DaysToExam,
    o.AvgMastery,
    o.SubmittedAttempts,
    o.LatestScore,
    o.StudyMin7d,
    o.DailyStudyMin * 7 AS WeeklyGoalMin,
    o.LastActivityAt,
    o.PredictedScore,
    o.ProbReachTarget,
    ISNULL(nt.UnreadNotifications, 0) AS UnreadNotifications
FROM dbo.ParentStudent AS ps
INNER JOIN dbo.vw_StudentOverview AS o ON o.StudentID = ps.StudentID
OUTER APPLY (
    SELECT COUNT(*) AS UnreadNotifications
    FROM dbo.Notifications AS n
    WHERE n.UserID = ps.ParentID AND n.StudentID = ps.StudentID AND n.IsRead = 0
) AS nt;
GO

/* ===== 7. TỔNG QUAN HỆ THỐNG (ADMIN) - MỘT DÒNG ===== */
CREATE OR ALTER VIEW dbo.vw_SystemOverview
AS
SELECT
    (SELECT COUNT(*) FROM dbo.Users WHERE IsActive = 1) AS ActiveUsers,
    (SELECT COUNT(*) FROM dbo.Users AS u INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID WHERE r.RoleName = 'Student') AS Students,
    (SELECT COUNT(*) FROM dbo.Users AS u INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID WHERE r.RoleName = 'Teacher') AS Teachers,
    (SELECT COUNT(*) FROM dbo.Users AS u INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID WHERE r.RoleName = 'Parent') AS Parents,
    (SELECT COUNT(*) FROM dbo.Questions WHERE IsApproved = 1) AS ApprovedQuestions,
    (SELECT COUNT(*) FROM dbo.Questions WHERE IsApproved = 0) AS PendingQuestions,
    (SELECT COUNT(*) FROM dbo.Questions WHERE IsAIGenerated = 1) AS AIGeneratedQuestions,
    (SELECT COUNT(*) FROM dbo.Exams) AS Exams,
    (SELECT COUNT(*) FROM dbo.ExamAttempts WHERE SubmittedAt IS NOT NULL) AS SubmittedAttempts,
    (SELECT CAST(AVG(Score) AS DECIMAL(6,2)) FROM dbo.ExamAttempts WHERE SubmittedAt IS NOT NULL) AS AvgScore,
    (SELECT COUNT(*) FROM dbo.LearningPaths WHERE Status = 'ACTIVE') AS ActivePaths,
    (SELECT COUNT(*) FROM dbo.Notifications WHERE IsRead = 0) AS UnreadNotifications,
    (SELECT ISNULL(SUM(DurationMin), 0) FROM dbo.StudyLogs WHERE LoggedAt >= DATEADD(DAY, -7, SYSDATETIME())) AS StudyMin7d;
GO

/* ===== 8. INDEXED VIEW: SỐ CÂU HỎI THEO NĂNG LỰC (materialized) ===== */
-- Yêu cầu SCHEMABINDING, tên 2 phần, COUNT_BIG(*), index clustered duy nhất.
-- Lưu ý: SCHEMABINDING sẽ chặn ALTER/DROP các cột CompetencyID, IsApproved, Difficulty của dbo.Questions
-- khi view còn tồn tại. Cần sửa cấu trúc thì DROP VIEW này trước.
CREATE OR ALTER VIEW dbo.vw_QuestionCountByCompetency
WITH SCHEMABINDING
AS
SELECT
    q.CompetencyID,
    q.IsApproved,
    COUNT_BIG(*) AS QuestionCount,
    SUM(CAST(q.Difficulty AS INT)) AS DifficultySum
FROM dbo.Questions AS q
GROUP BY q.CompetencyID, q.IsApproved;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.vw_QuestionCountByCompetency')
      AND name = 'UX_vw_QuestionCountByCompetency'
)
    CREATE UNIQUE CLUSTERED INDEX UX_vw_QuestionCountByCompetency
        ON dbo.vw_QuestionCountByCompetency (CompetencyID, IsApproved);
GO

PRINT '    + Đã tạo: vw_StudyActivitySummary, vw_DailyStudyTime, vw_WeeklyStudyTime, vw_NotificationInbox, vw_TutorConversation, vw_ParentDashboard, vw_SystemOverview, vw_QuestionCountByCompetency (indexed)';
GO

USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 1
VIEW VỀ NGƯỜI DÙNG VÀ HỒ SƠ HỌC SINH
-------------------------------------------------------------------------------
- Chạy lại được nhiều lần (CREATE OR ALTER), không xóa dữ liệu.
- Không view nào trả về cột PasswordHash.
- Các view bắt đầu từ bảng StudentProfiles (đang có Row-Level Security), nên mỗi
  vai trò chỉ thấy đúng học sinh mà mình được phép xem.
===============================================================================
*/
PRINT '>>> [01_vw_users_students.sql] Đang tạo view người dùng / hồ sơ học sinh...';
GO

/* ===== 1. TỔNG QUAN MỘT HỌC SINH (hồ sơ + học tập + điểm + dự đoán) ===== */
CREATE OR ALTER VIEW dbo.vw_StudentOverview
AS
SELECT
    sp.StudentID,
    u.FullName,
    u.Email,
    u.Phone,
    u.IsActive,
    sp.SchoolName,
    sp.TargetScore,
    sp.ExamDate,
    CASE WHEN sp.ExamDate IS NULL THEN NULL
         ELSE DATEDIFF(DAY, CAST(SYSDATETIME() AS DATE), sp.ExamDate) END AS DaysToExam,
    sp.DailyStudyMin,
    mst.CompetencyCount,
    mst.AvgMastery,
    att.SubmittedAttempts,
    att.BestScore,
    lat.LatestScore,
    lat.LatestSubmittedAt,
    stu.TotalStudyMin,
    stu.StudyMin7d,
    stu.LastActivityAt,
    pred.PredictedScore,
    pred.ProbReachTarget,
    pred.PredictedAt
FROM dbo.StudentProfiles AS sp
INNER JOIN dbo.Users AS u ON u.UserID = sp.StudentID
OUTER APPLY (
    SELECT COUNT(*) AS CompetencyCount,
           CAST(AVG(sc.Mastery) AS DECIMAL(5,4)) AS AvgMastery
    FROM dbo.StudentCompetency AS sc
    WHERE sc.StudentID = sp.StudentID
) AS mst
OUTER APPLY (
    SELECT COUNT(*) AS SubmittedAttempts,
           MAX(ea.Score) AS BestScore
    FROM dbo.ExamAttempts AS ea
    WHERE ea.StudentID = sp.StudentID AND ea.SubmittedAt IS NOT NULL
) AS att
OUTER APPLY (
    SELECT TOP 1 ea.Score AS LatestScore, ea.SubmittedAt AS LatestSubmittedAt
    FROM dbo.ExamAttempts AS ea
    WHERE ea.StudentID = sp.StudentID AND ea.SubmittedAt IS NOT NULL
    ORDER BY ea.SubmittedAt DESC, ea.AttemptID DESC
) AS lat
OUTER APPLY (
    SELECT ISNULL(SUM(sl.DurationMin), 0) AS TotalStudyMin,
           ISNULL(SUM(CASE WHEN sl.LoggedAt >= DATEADD(DAY, -7, SYSDATETIME())
                           THEN sl.DurationMin END), 0) AS StudyMin7d,
           MAX(sl.LoggedAt) AS LastActivityAt
    FROM dbo.StudyLogs AS sl
    WHERE sl.StudentID = sp.StudentID
) AS stu
OUTER APPLY (
    SELECT TOP 1 p.PredictedScore, p.ProbReachTarget, p.PredictedAt
    FROM dbo.ScorePredictions AS p
    WHERE p.StudentID = sp.StudentID
    ORDER BY p.PredictedAt DESC, p.PredictionID DESC
) AS pred;
GO

/* ===== 2. PHỤ HUYNH - CON EM ===== */
CREATE OR ALTER VIEW dbo.vw_ParentChildren
AS
SELECT
    ps.ParentID,
    pu.FullName   AS ParentName,
    ps.StudentID,
    su.FullName   AS StudentName,
    sp.SchoolName,
    sp.TargetScore,
    sp.ExamDate,
    sp.DailyStudyMin
FROM dbo.ParentStudent AS ps
INNER JOIN dbo.Users AS pu ON pu.UserID = ps.ParentID
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = ps.StudentID   -- RLS: chỉ con em của phụ huynh
INNER JOIN dbo.Users AS su ON su.UserID = sp.StudentID;
GO

PRINT '    + Đã tạo: vw_StudentOverview, vw_ParentChildren';
GO

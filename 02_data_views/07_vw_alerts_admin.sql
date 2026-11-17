USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 7
VIEW CẢNH BÁO / SẴN SÀNG THI (PHỤ HUYNH, GIÁO VIÊN) VÀ VẬN HÀNH HỆ THỐNG (ADMIN)
-------------------------------------------------------------------------------
- Parent: Receive learning alerts, Track target score achievement, Monitor examination readiness
                                           ... vw_StudentAlerts, vw_ExamReadiness
- Administrator: Manage users / Configure AI services / Monitor platform operations
                                           ... vw_UserDirectory, vw_SystemSettings, vw_AuditTrail, vw_PlatformActivityDaily
Ngưỡng cảnh báo trùng với sp_GenerateNotifications (3 ngày không học, nhiệm vụ đến hạn,
xác suất đạt mục tiêu < 0.70) để dữ liệu view và thông báo luôn nhất quán.
===============================================================================
*/
PRINT '>>> [07_vw_alerts_admin.sql] Đang tạo view cảnh báo và quản trị...';
GO

/* ===== 1. CẢNH BÁO HỌC TẬP CỦA TỪNG HỌC SINH ===== */
CREATE OR ALTER VIEW dbo.vw_StudentAlerts
AS
SELECT
    f.StudentID,
    f.StudentName,
    f.IsInactive3d,
    f.DueOrOverdueItems,
    f.IsBehindSchedule,
    f.LatestProbReachTarget,
    f.IsLowProbability,
    f.IsInactive3d + f.IsBehindSchedule + f.IsLowProbability AS AlertCount,
    CASE
        WHEN f.IsInactive3d + f.IsBehindSchedule + f.IsLowProbability >= 2 THEN N'Cao'
        WHEN f.IsInactive3d + f.IsBehindSchedule + f.IsLowProbability = 1  THEN N'Trung bình'
        ELSE N'Bình thường'
    END AS AlertLevel,
    CONCAT(
        CASE WHEN f.IsInactive3d = 1 THEN N'Không học trong 3 ngày qua. ' ELSE N'' END,
        CASE WHEN f.IsBehindSchedule = 1 THEN CONCAT(N'Có ', f.DueOrOverdueItems, N' nhiệm vụ đến hạn/trễ lịch. ') ELSE N'' END,
        CASE WHEN f.IsLowProbability = 1 THEN N'Xác suất đạt mục tiêu dưới 70%. ' ELSE N'' END
    ) AS AlertSummary
FROM (
    SELECT
        sp.StudentID,
        u.FullName AS StudentName,
        CASE WHEN lg.LogsLast3d = 0 THEN 1 ELSE 0 END AS IsInactive3d,
        ISNULL(pth.DueOrOverdueItems, 0) AS DueOrOverdueItems,
        CASE WHEN ISNULL(pth.DueOrOverdueItems, 0) > 0 THEN 1 ELSE 0 END AS IsBehindSchedule,
        pr.ProbReachTarget AS LatestProbReachTarget,
        CASE WHEN pr.ProbReachTarget IS NOT NULL AND pr.ProbReachTarget < 0.7000 THEN 1 ELSE 0 END AS IsLowProbability
    FROM dbo.StudentProfiles AS sp
    INNER JOIN dbo.Users AS u ON u.UserID = sp.StudentID
    OUTER APPLY (
        SELECT COUNT(*) AS LogsLast3d
        FROM dbo.StudyLogs AS sl
        WHERE sl.StudentID = sp.StudentID AND sl.LoggedAt >= DATEADD(DAY, -3, SYSDATETIME())
    ) AS lg
    OUTER APPLY (
        SELECT COUNT(*) AS DueOrOverdueItems
        FROM dbo.LearningPaths AS lp
        INNER JOIN dbo.LearningPathItems AS lpi ON lpi.PathID = lp.PathID
        WHERE lp.StudentID = sp.StudentID
          AND lp.Status = 'ACTIVE'
          AND lpi.Status IN ('TODO', 'DOING')
          AND lpi.ScheduledDate <= CAST(SYSDATETIME() AS DATE)
    ) AS pth
    OUTER APPLY (
        SELECT TOP 1 p.ProbReachTarget
        FROM dbo.ScorePredictions AS p
        WHERE p.StudentID = sp.StudentID
        ORDER BY p.PredictedAt DESC, p.PredictionID DESC
    ) AS pr
) AS f;
GO

/* ===== 2. MỨC ĐỘ SẴN SÀNG THI (chỉ số heuristic 0-100) ===== */
-- ReadinessScore = 100 * (0.40*Xác suất đạt mục tiêu + 0.30*Mastery TB + 0.20*Tiến độ lộ trình + 0.10*Tỷ lệ học 7 ngày)
-- Thành phần thiếu dữ liệu được tính là 0. Đây là chỉ số tham khảo cho phụ huynh/giáo viên, không thay thế dự đoán của AI.
CREATE OR ALTER VIEW dbo.vw_ExamReadiness
AS
SELECT
    x.StudentID,
    x.StudentName,
    x.TargetScore,
    x.ExamDate,
    x.DaysToExam,
    x.LatestPredictedScore,
    x.TargetScore - x.LatestPredictedScore AS ScoreGap,
    x.LatestProbReachTarget,
    x.AvgMastery,
    x.ActivePathProgressPercent,
    x.StudyRatio7d,
    x.ReadinessScore,
    CASE
        WHEN x.ReadinessScore >= 75 THEN N'Sẵn sàng'
        WHEN x.ReadinessScore >= 50 THEN N'Cần tăng tốc'
        ELSE N'Cần can thiệp'
    END AS ReadinessLevel
FROM (
    SELECT
        f.StudentID,
        u.FullName AS StudentName,
        f.TargetScore,
        f.ExamDate,
        f.DaysToExam,
        f.LatestPredictedScore,
        f.LatestProbReachTarget,
        f.AvgMastery,
        f.ActivePathProgressPercent,
        f.StudyRatio7d,
        CAST(100.0 * (0.40 * ISNULL(f.LatestProbReachTarget, 0)
                    + 0.30 * ISNULL(f.AvgMastery, 0)
                    + 0.20 * ISNULL(f.ActivePathProgressPercent, 0) / 100.0
                    + 0.10 * ISNULL(f.StudyRatio7d, 0)) AS DECIMAL(5,2)) AS ReadinessScore
    FROM dbo.vw_AIStudentFeatures AS f
    INNER JOIN dbo.Users AS u ON u.UserID = f.StudentID
) AS x;
GO

/* ===== 3. DANH BẠ NGƯỜI DÙNG (ADMIN) - KHÔNG CÓ PasswordHash ===== */
CREATE OR ALTER VIEW dbo.vw_UserDirectory
AS
SELECT
    u.UserID,
    r.RoleID,
    r.RoleName,
    u.FullName,
    u.Email,
    u.Phone,
    u.IsActive,
    CASE WHEN u.IsActive = 1 THEN N'Đang hoạt động' ELSE N'Đã khóa' END AS AccountStatus,
    u.CreatedAt,
    CASE r.RoleName
        WHEN 'Parent'  THEN (SELECT COUNT(*) FROM dbo.ParentStudent AS ps WHERE ps.ParentID = u.UserID)
        WHEN 'Student' THEN (SELECT COUNT(*) FROM dbo.ParentStudent AS ps WHERE ps.StudentID = u.UserID)
    END AS LinkedAccounts,                 -- Parent: số con; Student: số phụ huynh liên kết
    la.LastActivityAt
FROM dbo.Users AS u
INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
OUTER APPLY (
    SELECT MAX(sl.LoggedAt) AS LastActivityAt
    FROM dbo.StudyLogs AS sl
    WHERE sl.StudentID = u.UserID
) AS la;
GO

/* ===== 4. CẤU HÌNH HỆ THỐNG / AI (ADMIN) - CHE GIÁ TRỊ NHẠY CẢM ===== */
CREATE OR ALTER VIEW dbo.vw_SystemSettings
AS
SELECT
    ss.SettingKey,
    CASE
        WHEN ss.SettingKey LIKE '%KEY%' OR ss.SettingKey LIKE '%SECRET%'
          OR ss.SettingKey LIKE '%TOKEN%' OR ss.SettingKey LIKE '%PASSWORD%'
        THEN N'********'
        ELSE ss.SettingValue
    END AS SettingValue,
    CASE
        WHEN ss.SettingKey LIKE '%KEY%' OR ss.SettingKey LIKE '%SECRET%'
          OR ss.SettingKey LIKE '%TOKEN%' OR ss.SettingKey LIKE '%PASSWORD%'
        THEN CAST(1 AS BIT) ELSE CAST(0 AS BIT)
    END AS IsMasked,
    ss.UpdatedBy,
    u.FullName AS UpdatedByName,
    ss.UpdatedAt
FROM dbo.SystemSettings AS ss
LEFT JOIN dbo.Users AS u ON u.UserID = ss.UpdatedBy;
GO

/* ===== 5. NHẬT KÝ KIỂM TOÁN (ADMIN) ===== */
CREATE OR ALTER VIEW dbo.vw_AuditTrail
AS
SELECT
    a.AuditID,
    a.TableName,
    a.Action,
    CASE a.Action
        WHEN 'INSERT' THEN N'Thêm mới'
        WHEN 'UPDATE' THEN N'Cập nhật'
        WHEN 'DELETE' THEN N'Xóa'
    END AS ActionName,
    a.RecordKey,
    a.ChangedBy,
    a.ChangedAt,
    CAST(a.ChangedAt AS DATE) AS ChangedDate
FROM dbo.AuditLog AS a;
GO

/* ===== 6. HOẠT ĐỘNG NỀN TẢNG THEO NGÀY (ADMIN: Monitor overall platform operations) ===== */
CREATE OR ALTER VIEW dbo.vw_PlatformActivityDaily
AS
SELECT
    ev.ActivityDate,
    SUM(ev.NewUsers)         AS NewUsers,
    SUM(ev.AttemptsStarted)  AS AttemptsStarted,
    SUM(ev.AttemptsSubmitted) AS AttemptsSubmitted,
    SUM(ev.StudyMin)         AS StudyMin,
    SUM(ev.TutorMessages)    AS TutorMessages,
    SUM(ev.Recommendations)  AS Recommendations
FROM (
    SELECT CAST(CreatedAt AS DATE) AS ActivityDate, 1 AS NewUsers, 0 AS AttemptsStarted, 0 AS AttemptsSubmitted, 0 AS StudyMin, 0 AS TutorMessages, 0 AS Recommendations
    FROM dbo.Users
    UNION ALL
    SELECT CAST(StartedAt AS DATE), 0, 1, 0, 0, 0, 0 FROM dbo.ExamAttempts
    UNION ALL
    SELECT CAST(SubmittedAt AS DATE), 0, 0, 1, 0, 0, 0 FROM dbo.ExamAttempts WHERE SubmittedAt IS NOT NULL
    UNION ALL
    SELECT CAST(LoggedAt AS DATE), 0, 0, 0, DurationMin, 0, 0 FROM dbo.StudyLogs
    UNION ALL
    SELECT CAST(SentAt AS DATE), 0, 0, 0, 0, 1, 0 FROM dbo.TutorMessages WHERE Sender = 'USER'
    UNION ALL
    SELECT CAST(CreatedAt AS DATE), 0, 0, 0, 0, 0, 1 FROM dbo.Recommendations
) AS ev
GROUP BY ev.ActivityDate;
GO

PRINT '    + Đã tạo: vw_StudentAlerts, vw_ExamReadiness, vw_UserDirectory, vw_SystemSettings, vw_AuditTrail, vw_PlatformActivityDaily';
GO

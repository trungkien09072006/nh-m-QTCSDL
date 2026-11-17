USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 4
VIEW VỀ CÁ NHÂN HÓA: NĂNG LỰC - LỘ TRÌNH - GỢI Ý - DỰ ĐOÁN ĐIỂM
-------------------------------------------------------------------------------
Bảng Recommendations / LearningPathItems chưa có chính sách RLS riêng, nên các view
bên dưới luôn INNER JOIN với bảng đã có RLS (StudentProfiles / LearningPaths) để
học sinh, phụ huynh chỉ thấy đúng dữ liệu của mình.
Ngưỡng "cần ôn" Mastery < 0.65 trùng với sp_GenerateRecommendations.
===============================================================================
*/
PRINT '>>> [04_vw_personalization.sql] Đang tạo view cá nhân hóa...';
GO

/* ===== 1. HỒ SƠ NĂNG LỰC CỦA HỌC SINH (Learning Profile) ===== */
CREATE OR ALTER VIEW dbo.vw_StudentCompetencyProfile
AS
SELECT
    sc.StudentID,
    u.FullName AS StudentName,
    s.SubjectID,
    s.SubjectName,
    c.CompetencyID,
    c.CompetencyName,
    sc.Mastery,
    CAST(ROUND(sc.Mastery * 100, 0) AS INT) AS MasteryPercent,
    CASE
        WHEN sc.Mastery < 0.40 THEN N'Yếu'
        WHEN sc.Mastery < 0.65 THEN N'Trung bình'
        WHEN sc.Mastery < 0.80 THEN N'Khá'
        ELSE N'Giỏi'
    END AS MasteryLevel,
    CASE WHEN sc.Mastery < 0.65 THEN 1 ELSE 0 END AS NeedsReview,
    sc.AttemptCount,
    sc.UpdatedAt,
    ROW_NUMBER() OVER (PARTITION BY sc.StudentID ORDER BY sc.Mastery ASC, c.CompetencyID ASC) AS WeaknessRank
FROM dbo.StudentCompetency AS sc
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = sc.StudentID
INNER JOIN dbo.Users AS u ON u.UserID = sc.StudentID
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = sc.CompetencyID
INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID;
GO

/* ===== 2. MỨC THÀNH THẠO THEO MÔN ===== */
CREATE OR ALTER VIEW dbo.vw_SubjectMastery
AS
SELECT
    sc.StudentID,
    s.SubjectID,
    s.SubjectName,
    COUNT(*) AS CompetencyCount,
    CAST(AVG(sc.Mastery) AS DECIMAL(5,4)) AS AvgMastery,
    CAST(ROUND(AVG(sc.Mastery) * 100, 0) AS INT) AS AvgMasteryPercent,
    SUM(CASE WHEN sc.Mastery < 0.65 THEN 1 ELSE 0 END) AS WeakCompetencyCount,
    SUM(sc.AttemptCount) AS TotalAttempts
FROM dbo.StudentCompetency AS sc
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = sc.StudentID
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = sc.CompetencyID
INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
GROUP BY sc.StudentID, s.SubjectID, s.SubjectName;
GO

/* ===== 3. TIẾN ĐỘ TỪNG LỘ TRÌNH HỌC ===== */
CREATE OR ALTER VIEW dbo.vw_LearningPathProgress
AS
SELECT
    lp.PathID,
    lp.StudentID,
    u.FullName AS StudentName,
    lp.StartDate,
    lp.EndDate,
    lp.Status AS PathStatus,
    lp.GeneratedAt,
    DATEDIFF(DAY, CAST(SYSDATETIME() AS DATE), lp.EndDate) AS DaysLeft,
    ISNULL(it.TotalItems, 0)   AS TotalItems,
    ISNULL(it.DoneItems, 0)    AS DoneItems,
    ISNULL(it.DoingItems, 0)   AS DoingItems,
    ISNULL(it.TodoItems, 0)    AS TodoItems,
    ISNULL(it.SkippedItems, 0) AS SkippedItems,
    ISNULL(it.OverdueItems, 0) AS OverdueItems,
    CASE WHEN ISNULL(it.TotalItems, 0) = 0 THEN 0
         ELSE CAST(100.0 * it.DoneItems / it.TotalItems AS DECIMAL(5,2)) END AS ProgressPercent
FROM dbo.LearningPaths AS lp
INNER JOIN dbo.Users AS u ON u.UserID = lp.StudentID
OUTER APPLY (
    SELECT COUNT(*) AS TotalItems,
           SUM(CASE WHEN i.Status = 'DONE'    THEN 1 ELSE 0 END) AS DoneItems,
           SUM(CASE WHEN i.Status = 'DOING'   THEN 1 ELSE 0 END) AS DoingItems,
           SUM(CASE WHEN i.Status = 'TODO'    THEN 1 ELSE 0 END) AS TodoItems,
           SUM(CASE WHEN i.Status = 'SKIPPED' THEN 1 ELSE 0 END) AS SkippedItems,
           SUM(CASE WHEN i.Status IN ('TODO', 'DOING')
                     AND i.ScheduledDate < CAST(SYSDATETIME() AS DATE) THEN 1 ELSE 0 END) AS OverdueItems
    FROM dbo.LearningPathItems AS i
    WHERE i.PathID = lp.PathID
) AS it;
GO

/* ===== 4. CHI TIẾT NHIỆM VỤ TRONG LỘ TRÌNH ===== */
CREATE OR ALTER VIEW dbo.vw_LearningPathItems
AS
SELECT
    i.ItemID,
    i.PathID,
    lp.StudentID,
    lp.Status AS PathStatus,
    i.ScheduledDate,
    i.Priority,
    i.Status AS ItemStatus,
    CASE i.Status
        WHEN 'TODO'    THEN N'Chưa học'
        WHEN 'DOING'   THEN N'Đang học'
        WHEN 'DONE'    THEN N'Hoàn thành'
        WHEN 'SKIPPED' THEN N'Bỏ qua'
    END AS ItemStatusName,
    CASE WHEN i.Status IN ('TODO', 'DOING') AND i.ScheduledDate < CAST(SYSDATETIME() AS DATE)
         THEN 1 ELSE 0 END AS IsOverdue,
    c.CompetencyID,
    c.CompetencyName,
    s.SubjectName,
    r.ResourceID,
    r.Title        AS ResourceTitle,
    r.ResourceType,
    r.EstimatedMin
FROM dbo.LearningPathItems AS i
INNER JOIN dbo.LearningPaths AS lp ON lp.PathID = i.PathID          -- RLS theo StudentID
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = i.CompetencyID
INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
LEFT JOIN dbo.LearningResources AS r ON r.ResourceID = i.ResourceID;
GO

/* ===== 5. GỢI Ý CÁ NHÂN HÓA (học liệu hoặc câu hỏi ôn lại) ===== */
CREATE OR ALTER VIEW dbo.vw_Recommendations
AS
SELECT
    rec.RecID,
    rec.StudentID,
    CASE WHEN rec.ResourceID IS NOT NULL THEN N'Học liệu' ELSE N'Ôn câu hỏi' END AS RecommendationType,
    rec.ResourceID,
    r.Title        AS ResourceTitle,
    r.ResourceType,
    r.EstimatedMin,
    rec.QuestionID,
    q.Content      AS QuestionContent,       -- không kèm đáp án / lời giải
    q.Difficulty,
    c.CompetencyID,
    c.CompetencyName,
    rec.Reason,
    rec.CreatedAt,
    rec.IsAccepted,
    CASE
        WHEN rec.IsAccepted IS NULL THEN N'Chưa phản hồi'
        WHEN rec.IsAccepted = 1     THEN N'Đã chấp nhận'
        ELSE N'Chưa chấp nhận'
    END AS ResponseStatus
FROM dbo.Recommendations AS rec
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = rec.StudentID   -- RLS
LEFT JOIN dbo.LearningResources AS r ON r.ResourceID = rec.ResourceID
LEFT JOIN dbo.Questions AS q ON q.QuestionID = rec.QuestionID
LEFT JOIN dbo.Competencies AS c ON c.CompetencyID = COALESCE(q.CompetencyID, r.CompetencyID);
GO

/* ===== 6. DỰ ĐOÁN ĐIỂM MỚI NHẤT CỦA TỪNG HỌC SINH ===== */
CREATE OR ALTER VIEW dbo.vw_LatestPrediction
AS
SELECT
    x.PredictionID,
    x.StudentID,
    u.FullName AS StudentName,
    sp.TargetScore,
    x.PredictedScore,
    sp.TargetScore - x.PredictedScore AS ScoreGap,
    x.ProbReachTarget,
    CAST(ROUND(x.ProbReachTarget * 100, 0) AS INT) AS ProbReachPercent,
    CASE
        WHEN x.ProbReachTarget >= 0.80 THEN N'An toàn'
        WHEN x.ProbReachTarget >= 0.60 THEN N'Cần theo dõi'
        ELSE N'Nguy cơ cao'
    END AS RiskLevel,
    x.RiskNote,
    x.PredictedAt
FROM (
    SELECT p.*,
           ROW_NUMBER() OVER (PARTITION BY p.StudentID ORDER BY p.PredictedAt DESC, p.PredictionID DESC) AS rn
    FROM dbo.ScorePredictions AS p
) AS x
INNER JOIN dbo.StudentProfiles AS sp ON sp.StudentID = x.StudentID
INNER JOIN dbo.Users AS u ON u.UserID = x.StudentID
WHERE x.rn = 1;
GO

PRINT '    + Đã tạo: vw_StudentCompetencyProfile, vw_SubjectMastery, vw_LearningPathProgress, vw_LearningPathItems, vw_Recommendations, vw_LatestPrediction';
GO

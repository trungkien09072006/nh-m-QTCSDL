USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 6
VIEW CHO LUỒNG CHẨN ĐOÁN, ĐỘ CHÍNH XÁC NĂNG LỰC, AI ENGINE VÀ PHÂN TÍCH HỌC TẬP
-------------------------------------------------------------------------------
Ánh xạ với đề tài:
- Core Flow 1 (Chẩn đoán năng lực, Learning Profile) ... vw_DiagnosticResults, vw_CompetencyAccuracy
- Core Flow 3 (Học thích ứng)                         ... vw_AnswerHistory (chuỗi dữ liệu cho Knowledge Tracing)
- Core Flow 5 (Phân tích học tập, tính đều đặn)         ... vw_StudyConsistency
- Core Flow 4 (AI Tutor)                               ... vw_TutorUsage
- Core Flow 6 (Dự đoán điểm) + AI Recommendation Engine ... vw_AIStudentFeatures
- Teacher: Monitor AI recommendation quality / Evaluate question quality
                                                       ... vw_RecommendationQuality, vw_QuestionQuality, vw_OptionDistribution
===============================================================================
*/
PRINT '>>> [06_vw_ai_learning_analytics.sql] Đang tạo view phục vụ AI & phân tích học tập...';
GO

/* ===== 1. KẾT QUẢ BÀI CHẨN ĐOÁN THEO NĂNG LỰC (điểm mạnh / điểm yếu) ===== */
CREATE OR ALTER VIEW dbo.vw_DiagnosticResults
AS
SELECT
    x.StudentID,
    x.StudentName,
    x.AttemptID,
    x.ExamID,
    x.ExamTitle,
    x.SubmittedAt,
    x.SubjectName,
    x.CompetencyID,
    x.CompetencyName,
    x.QuestionsAnswered,
    x.CorrectCount,
    x.AccuracyPercent,
    CASE
        WHEN x.AccuracyPercent >= 70 THEN N'Điểm mạnh'
        WHEN x.AccuracyPercent >= 50 THEN N'Cần củng cố'
        ELSE N'Điểm yếu'
    END AS DiagnosticLevel
FROM (
    SELECT
        ea.StudentID,
        u.FullName AS StudentName,
        ea.AttemptID,
        e.ExamID,
        e.Title AS ExamTitle,
        ea.SubmittedAt,
        s.SubjectName,
        c.CompetencyID,
        c.CompetencyName,
        COUNT(*) AS QuestionsAnswered,
        SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) AS CorrectCount,
        CAST(100.0 * SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,2)) AS AccuracyPercent
    FROM dbo.ExamAttempts AS ea
    INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID AND e.ExamType = 'DIAGNOSTIC'
    INNER JOIN dbo.Users AS u ON u.UserID = ea.StudentID
    INNER JOIN dbo.AttemptAnswers AS aa ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
    INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
    INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
    INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
    WHERE ea.SubmittedAt IS NOT NULL
    GROUP BY ea.StudentID, u.FullName, ea.AttemptID, e.ExamID, e.Title, ea.SubmittedAt,
             s.SubjectName, c.CompetencyID, c.CompetencyName
) AS x;
GO

/* ===== 2. ĐỘ CHÍNH XÁC THEO NĂNG LỰC TỪ LỊCH SỬ LÀM BÀI (mọi loại đề đã nộp) ===== */
CREATE OR ALTER VIEW dbo.vw_CompetencyAccuracy
AS
SELECT
    ea.StudentID,
    s.SubjectID,
    s.SubjectName,
    c.CompetencyID,
    c.CompetencyName,
    COUNT(*) AS AnsweredCount,
    SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) AS CorrectCount,
    CAST(100.0 * SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,2)) AS AccuracyPercent,
    CAST(AVG(CAST(aa.TimeSpentSec AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AvgTimeSec,
    MAX(ea.SubmittedAt) AS LastAnsweredAt
FROM dbo.ExamAttempts AS ea
INNER JOIN dbo.AttemptAnswers AS aa ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
WHERE ea.SubmittedAt IS NOT NULL
GROUP BY ea.StudentID, s.SubjectID, s.SubjectName, c.CompetencyID, c.CompetencyName;
GO

/* ===== 3. CHUỖI SỰ KIỆN TRẢ LỜI THEO THỜI GIAN (đầu vào Knowledge Tracing) ===== */
CREATE OR ALTER VIEW dbo.vw_AnswerHistory
AS
SELECT
    ea.StudentID,
    q.CompetencyID,
    aa.QuestionID,
    ea.AttemptID,
    ea.SubmittedAt,
    q.Difficulty,
    CAST(ISNULL(aa.IsCorrect, 0) AS INT) AS IsCorrect,
    aa.TimeSpentSec,
    ROW_NUMBER() OVER (
        PARTITION BY ea.StudentID, q.CompetencyID
        ORDER BY ea.SubmittedAt, ea.AttemptID, aa.QuestionID
    ) AS SeqNo,
    SUM(CAST(ISNULL(aa.IsCorrect, 0) AS INT)) OVER (
        PARTITION BY ea.StudentID, q.CompetencyID
        ORDER BY ea.SubmittedAt, ea.AttemptID, aa.QuestionID
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS RunningCorrect
FROM dbo.ExamAttempts AS ea
INNER JOIN dbo.AttemptAnswers AS aa ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
WHERE ea.SubmittedAt IS NOT NULL;
GO

/* ===== 4. TÍNH ĐỀU ĐẶN VÀ MỨC ĐỘ THAM GIA HỌC (engagement) ===== */
CREATE OR ALTER VIEW dbo.vw_StudyConsistency
AS
SELECT
    sp.StudentID,
    u.FullName AS StudentName,
    ISNULL(a.ActiveDays7, 0)  AS ActiveDays7,
    ISNULL(a.ActiveDays14, 0) AS ActiveDays14,
    ISNULL(a.ActiveDays30, 0) AS ActiveDays30,
    ISNULL(a.TotalMin30d, 0)  AS TotalMin30d,
    CASE WHEN ISNULL(a.ActiveDays30, 0) = 0 THEN 0
         ELSE CAST(1.0 * a.TotalMin30d / a.ActiveDays30 AS DECIMAL(8,2)) END AS AvgMinPerActiveDay30,
    a.LastActivityAt,
    CASE WHEN a.LastActivityAt IS NULL THEN NULL
         ELSE DATEDIFF(DAY, CAST(a.LastActivityAt AS DATE), CAST(SYSDATETIME() AS DATE)) END AS DaysSinceLastActivity,
    CASE
        WHEN ISNULL(a.ActiveDays7, 0) >= 5 THEN N'Đều đặn'
        WHEN ISNULL(a.ActiveDays7, 0) >= 3 THEN N'Trung bình'
        ELSE N'Thấp'
    END AS ConsistencyLevel
FROM dbo.StudentProfiles AS sp
INNER JOIN dbo.Users AS u ON u.UserID = sp.StudentID
OUTER APPLY (
    SELECT
        COUNT(DISTINCT CASE WHEN sl.LoggedAt >= DATEADD(DAY, -7,  SYSDATETIME()) THEN CAST(sl.LoggedAt AS DATE) END) AS ActiveDays7,
        COUNT(DISTINCT CASE WHEN sl.LoggedAt >= DATEADD(DAY, -14, SYSDATETIME()) THEN CAST(sl.LoggedAt AS DATE) END) AS ActiveDays14,
        COUNT(DISTINCT CASE WHEN sl.LoggedAt >= DATEADD(DAY, -30, SYSDATETIME()) THEN CAST(sl.LoggedAt AS DATE) END) AS ActiveDays30,
        SUM(CASE WHEN sl.LoggedAt >= DATEADD(DAY, -30, SYSDATETIME()) THEN sl.DurationMin ELSE 0 END) AS TotalMin30d,
        MAX(sl.LoggedAt) AS LastActivityAt
    FROM dbo.StudyLogs AS sl
    WHERE sl.StudentID = sp.StudentID
) AS a;
GO

/* ===== 5. MỨC SỬ DỤNG AI TUTOR ===== */
CREATE OR ALTER VIEW dbo.vw_TutorUsage
AS
SELECT
    sp.StudentID,
    u.FullName AS StudentName,
    COUNT(DISTINCT ts.SessionID) AS SessionCount,
    COUNT(tm.MessageID) AS MessageCount,
    SUM(CASE WHEN tm.Sender = 'USER' THEN 1 ELSE 0 END) AS StudentQuestions,
    SUM(CASE WHEN tm.Sender = 'AI'   THEN 1 ELSE 0 END) AS AIReplies,
    COUNT(DISTINCT tm.QuestionID) AS DistinctQuestionsAsked,
    MIN(tm.SentAt) AS FirstMessageAt,
    MAX(tm.SentAt) AS LastMessageAt
FROM dbo.StudentProfiles AS sp
INNER JOIN dbo.Users AS u ON u.UserID = sp.StudentID
LEFT JOIN dbo.TutorSessions AS ts ON ts.StudentID = sp.StudentID
LEFT JOIN dbo.TutorMessages AS tm ON tm.SessionID = ts.SessionID
GROUP BY sp.StudentID, u.FullName;
GO

/* ===== 6. ĐẶC TRƯNG CHO AI ENGINE (Prediction / Recommendation / Knowledge Tracing) - MỘT DÒNG / HỌC SINH ===== */
CREATE OR ALTER VIEW dbo.vw_AIStudentFeatures
AS
SELECT
    o.StudentID,
    o.TargetScore,
    o.ExamDate,
    o.DaysToExam,
    o.DailyStudyMin,
    o.CompetencyCount,
    o.AvgMastery,
    m.MinMastery,
    m.WeakCompetencyCount,
    acc.AvgAccuracyPercent,
    acc.AvgTimeSec,
    o.SubmittedAttempts,
    o.LatestScore,
    CASE WHEN o.LatestScore IS NULL THEN NULL
         WHEN o.LatestScore <= 100 THEN o.LatestScore * 12      -- cùng quy ước chuẩn hóa như sp_CalculateScorePrediction
         ELSE o.LatestScore END AS LatestScoreNormalized,
    o.StudyMin7d,
    o.DailyStudyMin * 7 AS WeeklyGoalMin,
    CASE WHEN o.DailyStudyMin * 7 <= 0 THEN NULL
         WHEN 1.0 * o.StudyMin7d / (o.DailyStudyMin * 7) > 1 THEN CAST(1 AS DECIMAL(5,4))
         ELSE CAST(1.0 * o.StudyMin7d / (o.DailyStudyMin * 7) AS DECIMAL(5,4)) END AS StudyRatio7d,
    cons.ActiveDays14,
    pth.ProgressPercent AS ActivePathProgressPercent,
    ISNULL(pth.OverdueItems, 0) AS OverdueItems,
    o.PredictedScore AS LatestPredictedScore,
    o.ProbReachTarget AS LatestProbReachTarget,
    rec.RecommendationCount,
    rec.AcceptedRecommendationCount
FROM dbo.vw_StudentOverview AS o
OUTER APPLY (
    SELECT MIN(sc.Mastery) AS MinMastery,
           SUM(CASE WHEN sc.Mastery < 0.65 THEN 1 ELSE 0 END) AS WeakCompetencyCount
    FROM dbo.StudentCompetency AS sc
    WHERE sc.StudentID = o.StudentID
) AS m
OUTER APPLY (
    SELECT CAST(100.0 * SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS DECIMAL(5,2)) AS AvgAccuracyPercent,
           CAST(AVG(CAST(aa.TimeSpentSec AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AvgTimeSec
    FROM dbo.ExamAttempts AS ea
    INNER JOIN dbo.AttemptAnswers AS aa ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
    WHERE ea.StudentID = o.StudentID AND ea.SubmittedAt IS NOT NULL
) AS acc
OUTER APPLY (
    SELECT c.ActiveDays14 FROM dbo.vw_StudyConsistency AS c WHERE c.StudentID = o.StudentID
) AS cons
OUTER APPLY (
    SELECT TOP 1 p.ProgressPercent, p.OverdueItems
    FROM dbo.vw_LearningPathProgress AS p
    WHERE p.StudentID = o.StudentID AND p.PathStatus = 'ACTIVE'
    ORDER BY p.GeneratedAt DESC, p.PathID DESC
) AS pth
OUTER APPLY (
    SELECT COUNT(*) AS RecommendationCount,
           SUM(CASE WHEN r.IsAccepted = 1 THEN 1 ELSE 0 END) AS AcceptedRecommendationCount
    FROM dbo.Recommendations AS r
    WHERE r.StudentID = o.StudentID
) AS rec;
GO

/* ===== 7. CHẤT LƯỢNG GỢI Ý CỦA AI THEO LOẠI VÀ NĂNG LỰC (Teacher: Monitor AI recommendation quality) ===== */
CREATE OR ALTER VIEW dbo.vw_RecommendationQuality
AS
SELECT
    CASE WHEN rec.ResourceID IS NOT NULL THEN N'Học liệu' ELSE N'Ôn câu hỏi' END AS RecommendationType,
    c.CompetencyID,
    c.CompetencyName,
    COUNT(*) AS TotalRecommendations,
    SUM(CASE WHEN rec.IsAccepted = 1 THEN 1 ELSE 0 END) AS AcceptedCount,
    SUM(CASE WHEN rec.IsAccepted IS NULL THEN 1 ELSE 0 END) AS NoResponseCount,
    SUM(CASE WHEN rec.IsAccepted = 0 THEN 1 ELSE 0 END) AS NotAcceptedCount,
    CAST(100.0 * SUM(CASE WHEN rec.IsAccepted = 1 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,2)) AS AcceptedPercent,
    COUNT(DISTINCT rec.StudentID) AS StudentCount,
    MIN(rec.CreatedAt) AS FirstCreatedAt,
    MAX(rec.CreatedAt) AS LastCreatedAt
FROM dbo.Recommendations AS rec
LEFT JOIN dbo.LearningResources AS r ON r.ResourceID = rec.ResourceID
LEFT JOIN dbo.Questions AS q ON q.QuestionID = rec.QuestionID
LEFT JOIN dbo.Competencies AS c ON c.CompetencyID = COALESCE(q.CompetencyID, r.CompetencyID)
GROUP BY CASE WHEN rec.ResourceID IS NOT NULL THEN N'Học liệu' ELSE N'Ôn câu hỏi' END,
         c.CompetencyID, c.CompetencyName;
GO

/* ===== 8. ĐÁNH GIÁ CHẤT LƯỢNG CÂU HỎI (Teacher: Evaluate question quality) ===== */
CREATE OR ALTER VIEW dbo.vw_QuestionQuality
AS
SELECT
    qs.QuestionID,
    qs.CompetencyName,
    qs.Difficulty,
    qs.IsApproved,
    qs.TimesAnswered,
    qs.CorrectRatePercent,
    qs.AvgTimeSec,
    CASE
        WHEN qs.TimesAnswered < 5 THEN N'Chưa đủ dữ liệu (cần >= 5 lượt trả lời)'
        WHEN qs.CorrectRatePercent >= 95 THEN N'Quá dễ - cân nhắc tăng độ khó hoặc thay câu hỏi'
        WHEN qs.CorrectRatePercent <= 15 THEN N'Quá khó - kiểm tra lại đáp án / nội dung'
        WHEN qs.Difficulty >= 4 AND qs.CorrectRatePercent >= 85 THEN N'Gắn nhãn khó nhưng học sinh làm đúng nhiều - hiệu chỉnh độ khó'
        WHEN qs.Difficulty <= 2 AND qs.CorrectRatePercent <= 40 THEN N'Gắn nhãn dễ nhưng học sinh làm sai nhiều - hiệu chỉnh độ khó'
        ELSE N'Đạt'
    END AS QualityAssessment,
    CASE WHEN qs.TimesAnswered >= 5
              AND (qs.CorrectRatePercent >= 95 OR qs.CorrectRatePercent <= 15
                   OR (qs.Difficulty >= 4 AND qs.CorrectRatePercent >= 85)
                   OR (qs.Difficulty <= 2 AND qs.CorrectRatePercent <= 40))
         THEN 1 ELSE 0 END AS NeedsReview
FROM dbo.vw_QuestionStatistics AS qs;
GO

/* ===== 9. PHÂN BỐ LỰA CHỌN CỦA TỪNG ĐÁP ÁN (phân tích nhiễu / distractor) ===== */
CREATE OR ALTER VIEW dbo.vw_OptionDistribution
AS
SELECT
    o.QuestionID,
    o.OptionID,
    o.OptionLabel,
    o.OptionText,
    o.IsCorrect,
    ISNULL(ch.TimesChosen, 0) AS TimesChosen,
    CASE WHEN ISNULL(tot.TotalAnswered, 0) = 0 THEN NULL
         ELSE CAST(100.0 * ISNULL(ch.TimesChosen, 0) / tot.TotalAnswered AS DECIMAL(5,2)) END AS ChosenPercent
FROM dbo.QuestionOptions AS o
OUTER APPLY (
    SELECT COUNT(*) AS TimesChosen
    FROM dbo.AttemptAnswers AS aa
    INNER JOIN dbo.ExamAttempts AS ea ON ea.AttemptID = aa.AttemptID
    WHERE aa.SelectedOption = o.OptionID AND ea.SubmittedAt IS NOT NULL
) AS ch
OUTER APPLY (
    SELECT COUNT(*) AS TotalAnswered
    FROM dbo.AttemptAnswers AS aa
    INNER JOIN dbo.ExamAttempts AS ea ON ea.AttemptID = aa.AttemptID
    WHERE aa.QuestionID = o.QuestionID AND aa.SelectedOption IS NOT NULL AND ea.SubmittedAt IS NOT NULL
) AS tot;
GO

PRINT '    + Đã tạo: vw_DiagnosticResults, vw_CompetencyAccuracy, vw_AnswerHistory, vw_StudyConsistency, vw_TutorUsage, vw_AIStudentFeatures, vw_RecommendationQuality, vw_QuestionQuality, vw_OptionDistribution';
GO

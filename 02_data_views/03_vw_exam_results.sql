USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 3
VIEW VỀ LƯỢT LÀM BÀI VÀ KẾT QUẢ THI
-------------------------------------------------------------------------------
- Các view bắt đầu từ ExamAttempts (đang có RLS): học sinh chỉ thấy bài của mình,
  phụ huynh chỉ thấy bài của con.
- vw_AnswerReview chỉ trả về lượt ĐÃ NỘP nên không lộ đáp án khi đang làm bài.
===============================================================================
*/
PRINT '>>> [03_vw_exam_results.sql] Đang tạo view kết quả thi...';
GO

/* ===== 1. KẾT QUẢ TỪNG LƯỢT LÀM BÀI ===== */
CREATE OR ALTER VIEW dbo.vw_AttemptResults
AS
SELECT
    ea.AttemptID,
    ea.ExamID,
    e.Title        AS ExamTitle,
    e.ExamType,
    e.DurationMin,
    ea.StudentID,
    u.FullName     AS StudentName,
    ea.StartedAt,
    ea.SubmittedAt,
    CASE WHEN ea.SubmittedAt IS NULL THEN N'Đang làm' ELSE N'Đã nộp' END AS AttemptStatus,
    CASE WHEN ea.SubmittedAt IS NULL THEN NULL
         ELSE CAST(DATEDIFF(SECOND, ea.StartedAt, ea.SubmittedAt) / 60.0 AS DECIMAL(8,2)) END AS UsedMinutes,
    ea.Score,
    tq.TotalQuestions,
    ISNULL(ans.AnsweredCount, 0) AS AnsweredCount,
    ISNULL(ans.CorrectCount, 0)  AS CorrectCount,
    ISNULL(ans.AnsweredCount, 0) - ISNULL(ans.CorrectCount, 0) AS WrongCount,
    CASE WHEN tq.TotalQuestions = 0 THEN 0
         ELSE CAST(100.0 * ISNULL(ans.CorrectCount, 0) / tq.TotalQuestions AS DECIMAL(5,2)) END AS AccuracyPercent
FROM dbo.ExamAttempts AS ea
INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
INNER JOIN dbo.Users AS u ON u.UserID = ea.StudentID
OUTER APPLY (
    SELECT COUNT(*) AS TotalQuestions
    FROM dbo.ExamQuestions AS eq
    WHERE eq.ExamID = ea.ExamID
) AS tq
OUTER APPLY (
    SELECT COUNT(aa.SelectedOption) AS AnsweredCount,
           SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) AS CorrectCount
    FROM dbo.AttemptAnswers AS aa
    WHERE aa.AttemptID = ea.AttemptID
) AS ans;
GO

/* ===== 2. XEM LẠI BÀI LÀM (CHỈ LƯỢT ĐÃ NỘP): ĐÁP ÁN CHỌN - ĐÁP ÁN ĐÚNG - LỜI GIẢI ===== */
CREATE OR ALTER VIEW dbo.vw_AnswerReview
AS
SELECT
    ea.AttemptID,
    ea.ExamID,
    e.Title            AS ExamTitle,
    ea.StudentID,
    eq.OrderNo,
    q.QuestionID,
    c.CompetencyName,
    q.Difficulty,
    q.Content          AS QuestionContent,
    sel.OptionLabel    AS SelectedLabel,
    sel.OptionText     AS SelectedText,
    cor.OptionLabel    AS CorrectLabel,
    cor.OptionText     AS CorrectText,
    aa.IsCorrect,
    CASE WHEN aa.SelectedOption IS NULL THEN N'Bỏ trống'
         WHEN aa.IsCorrect = 1 THEN N'Đúng'
         ELSE N'Sai' END AS ResultLabel,
    aa.TimeSpentSec,
    q.Explanation
FROM dbo.ExamAttempts AS ea
INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
INNER JOIN dbo.AttemptAnswers AS aa ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
INNER JOIN dbo.ExamQuestions AS eq ON eq.ExamID = aa.ExamID AND eq.QuestionID = aa.QuestionID
INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
LEFT JOIN dbo.QuestionOptions AS sel ON sel.OptionID = aa.SelectedOption
LEFT JOIN dbo.QuestionOptions AS cor ON cor.QuestionID = q.QuestionID AND cor.IsCorrect = 1
WHERE ea.SubmittedAt IS NOT NULL;
GO

/* ===== 3. THỐNG KÊ CHẤT LƯỢNG TỪNG CÂU HỎI (GIÁO VIÊN / ADMIN) ===== */
CREATE OR ALTER VIEW dbo.vw_QuestionStatistics
AS
SELECT
    q.QuestionID,
    c.CompetencyName,
    q.Difficulty,
    q.IsApproved,
    ISNULL(st.TimesAnswered, 0) AS TimesAnswered,
    ISNULL(st.TimesCorrect, 0)  AS TimesCorrect,
    CASE WHEN ISNULL(st.TimesAnswered, 0) = 0 THEN NULL
         ELSE CAST(100.0 * st.TimesCorrect / st.TimesAnswered AS DECIMAL(5,2)) END AS CorrectRatePercent,
    st.AvgTimeSec,
    CASE
        WHEN ISNULL(st.TimesAnswered, 0) = 0 THEN N'Chưa có dữ liệu'
        WHEN 100.0 * st.TimesCorrect / st.TimesAnswered >= 80 THEN N'Dễ (thực tế)'
        WHEN 100.0 * st.TimesCorrect / st.TimesAnswered >= 40 THEN N'Trung bình (thực tế)'
        ELSE N'Khó (thực tế)'
    END AS ObservedDifficulty
FROM dbo.Questions AS q
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
OUTER APPLY (
    SELECT COUNT(*) AS TimesAnswered,
           SUM(CASE WHEN aa.IsCorrect = 1 THEN 1 ELSE 0 END) AS TimesCorrect,
           CAST(AVG(CAST(aa.TimeSpentSec AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AvgTimeSec
    FROM dbo.AttemptAnswers AS aa
    INNER JOIN dbo.ExamAttempts AS ea ON ea.AttemptID = aa.AttemptID
    WHERE aa.QuestionID = q.QuestionID AND ea.SubmittedAt IS NOT NULL
) AS st;
GO

/* ===== 4. XẾP HẠNG THEO ĐỀ (GIÁO VIÊN / ADMIN - học sinh không được xem vì sẽ lộ điểm người khác) ===== */
CREATE OR ALTER VIEW dbo.vw_ExamRanking
AS
SELECT
    x.ExamID,
    x.ExamTitle,
    x.StudentID,
    x.StudentName,
    x.BestScore,
    x.AttemptCount,
    RANK() OVER (PARTITION BY x.ExamID ORDER BY x.BestScore DESC) AS RankInExam
FROM (
    SELECT
        ea.ExamID,
        e.Title AS ExamTitle,
        ea.StudentID,
        u.FullName AS StudentName,
        MAX(ea.Score) AS BestScore,
        COUNT(*) AS AttemptCount
    FROM dbo.ExamAttempts AS ea
    INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
    INNER JOIN dbo.Users AS u ON u.UserID = ea.StudentID
    WHERE ea.SubmittedAt IS NOT NULL AND ea.Score IS NOT NULL
    GROUP BY ea.ExamID, e.Title, ea.StudentID, u.FullName
) AS x;
GO

PRINT '    + Đã tạo: vw_AttemptResults, vw_AnswerReview, vw_QuestionStatistics, vw_ExamRanking';
GO

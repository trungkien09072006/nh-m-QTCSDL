USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 2
VIEW VỀ NỘI DUNG HỌC: MÔN - NĂNG LỰC - HỌC LIỆU - NGÂN HÀNG CÂU HỎI - ĐỀ THI
-------------------------------------------------------------------------------
LƯU Ý BẢO MẬT: vw_QuestionBank có lộ đáp án đúng -> chỉ cấp cho Admin/Teacher.
Học sinh làm bài qua vw_StudentExamView (04_security) hoặc vw_AvailableExams.
===============================================================================
*/
PRINT '>>> [02_vw_content.sql] Đang tạo view nội dung học...';
GO

/* ===== 1. CÂY NĂNG LỰC (đệ quy theo ParentCompID) ===== */
CREATE OR ALTER VIEW dbo.vw_CompetencyTree
AS
WITH tree AS (
    SELECT
        c.CompetencyID, c.SubjectID, c.CompetencyName, c.ParentCompID,
        0 AS Lvl,
        CAST(c.CompetencyName AS NVARCHAR(1000)) AS PathName,
        CAST(RIGHT('000000' + CAST(c.CompetencyID AS VARCHAR(10)), 6) AS VARCHAR(400)) AS SortKey
    FROM dbo.Competencies AS c
    WHERE c.ParentCompID IS NULL
    UNION ALL
    SELECT
        c.CompetencyID, c.SubjectID, c.CompetencyName, c.ParentCompID,
        t.Lvl + 1,
        CAST(t.PathName + N' > ' + c.CompetencyName AS NVARCHAR(1000)),
        CAST(t.SortKey + '/' + RIGHT('000000' + CAST(c.CompetencyID AS VARCHAR(10)), 6) AS VARCHAR(400))
    FROM dbo.Competencies AS c
    INNER JOIN tree AS t ON c.ParentCompID = t.CompetencyID
)
SELECT
    t.CompetencyID,
    t.SubjectID,
    s.SubjectName,
    t.CompetencyName,
    t.ParentCompID,
    t.Lvl            AS TreeLevel,
    t.PathName       AS FullPath,
    t.SortKey,
    (SELECT COUNT(*) FROM dbo.LearningResources AS r WHERE r.CompetencyID = t.CompetencyID) AS ResourceCount,
    (SELECT COUNT(*) FROM dbo.Questions AS q WHERE q.CompetencyID = t.CompetencyID AND q.IsApproved = 1) AS ApprovedQuestionCount
FROM tree AS t
INNER JOIN dbo.Subjects AS s ON s.SubjectID = t.SubjectID;
GO

/* ===== 2. DANH MỤC HỌC LIỆU ===== */
CREATE OR ALTER VIEW dbo.vw_LearningResourceCatalog
AS
SELECT
    r.ResourceID,
    r.Title,
    r.ResourceType,
    CASE r.ResourceType
        WHEN 'VIDEO'    THEN N'Video'
        WHEN 'ARTICLE'  THEN N'Bài viết'
        WHEN 'SLIDE'    THEN N'Slide'
        WHEN 'EXERCISE' THEN N'Bài tập'
    END AS ResourceTypeName,
    r.Url,
    r.EstimatedMin,
    c.CompetencyID,
    c.CompetencyName,
    s.SubjectID,
    s.SubjectName,
    r.CreatedBy,
    u.FullName AS CreatedByName
FROM dbo.LearningResources AS r
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = r.CompetencyID
INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
INNER JOIN dbo.Users AS u ON u.UserID = r.CreatedBy;
GO

/* ===== 3. NGÂN HÀNG CÂU HỎI (DÀNH CHO GIÁO VIÊN / ADMIN - CÓ ĐÁP ÁN) ===== */
CREATE OR ALTER VIEW dbo.vw_QuestionBank
AS
SELECT
    q.QuestionID,
    s.SubjectID,
    s.SubjectName,
    c.CompetencyID,
    c.CompetencyName,
    q.Content,
    q.Difficulty,
    CASE q.Difficulty
        WHEN 1 THEN N'Rất dễ'
        WHEN 2 THEN N'Dễ'
        WHEN 3 THEN N'Trung bình'
        WHEN 4 THEN N'Khó'
        ELSE N'Rất khó'
    END AS DifficultyLabel,
    q.IsAIGenerated,
    q.IsApproved,
    CASE WHEN q.IsApproved = 1 THEN N'Đã duyệt' ELSE N'Chờ duyệt' END AS ApprovalStatus,
    opt.OptionCount,
    opt.CorrectCount,
    opt.CorrectOptionLabel,
    opt.CorrectOptionText,
    CASE WHEN opt.OptionCount >= 2 AND opt.CorrectCount = 1 THEN 1 ELSE 0 END AS IsReadyToApprove,
    ex.UsedInExams,
    q.Explanation,
    q.CreatedBy,
    u.FullName AS CreatedByName,
    q.CreatedAt
FROM dbo.Questions AS q
INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
INNER JOIN dbo.Users AS u ON u.UserID = q.CreatedBy
OUTER APPLY (
    SELECT COUNT(*) AS OptionCount,
           ISNULL(SUM(CAST(o.IsCorrect AS INT)), 0) AS CorrectCount,
           MAX(CASE WHEN o.IsCorrect = 1 THEN o.OptionLabel END) AS CorrectOptionLabel,
           MAX(CASE WHEN o.IsCorrect = 1 THEN o.OptionText END)  AS CorrectOptionText
    FROM dbo.QuestionOptions AS o
    WHERE o.QuestionID = q.QuestionID
) AS opt
OUTER APPLY (
    SELECT COUNT(*) AS UsedInExams
    FROM dbo.ExamQuestions AS eq
    WHERE eq.QuestionID = q.QuestionID
) AS ex;
GO

/* ===== 4. TỔNG HỢP ĐỀ THI (DÀNH CHO GIÁO VIÊN / ADMIN) ===== */
CREATE OR ALTER VIEW dbo.vw_ExamSummary
AS
SELECT
    e.ExamID,
    e.Title,
    e.ExamType,
    e.DurationMin,
    e.CreatedBy,
    u.FullName AS CreatedByName,
    e.CreatedAt,
    ISNULL(qs.QuestionCount, 0)  AS QuestionCount,
    qs.AvgDifficulty,
    ISNULL(att.TotalAttempts, 0)     AS TotalAttempts,
    ISNULL(att.SubmittedAttempts, 0) AS SubmittedAttempts,
    att.AvgScore,
    att.MaxScore,
    att.MinScore
FROM dbo.Exams AS e
INNER JOIN dbo.Users AS u ON u.UserID = e.CreatedBy
OUTER APPLY (
    SELECT COUNT(*) AS QuestionCount,
           CAST(AVG(CAST(q.Difficulty AS DECIMAL(5,2))) AS DECIMAL(4,2)) AS AvgDifficulty
    FROM dbo.ExamQuestions AS eq
    INNER JOIN dbo.Questions AS q ON q.QuestionID = eq.QuestionID
    WHERE eq.ExamID = e.ExamID
) AS qs
OUTER APPLY (
    SELECT COUNT(*) AS TotalAttempts,
           SUM(CASE WHEN ea.SubmittedAt IS NOT NULL THEN 1 ELSE 0 END) AS SubmittedAttempts,
           CAST(AVG(CASE WHEN ea.SubmittedAt IS NOT NULL THEN ea.Score END) AS DECIMAL(6,2)) AS AvgScore,
           MAX(CASE WHEN ea.SubmittedAt IS NOT NULL THEN ea.Score END) AS MaxScore,
           MIN(CASE WHEN ea.SubmittedAt IS NOT NULL THEN ea.Score END) AS MinScore
    FROM dbo.ExamAttempts AS ea
    WHERE ea.ExamID = e.ExamID
) AS att;
GO

/* ===== 5. ĐỀ THI KHẢ DỤNG CHO HỌC SINH (KHÔNG LỘ ĐÁP ÁN, KHÔNG THỐNG KÊ NGƯỜI KHÁC) ===== */
CREATE OR ALTER VIEW dbo.vw_AvailableExams
AS
SELECT
    e.ExamID,
    e.Title,
    e.ExamType,
    CASE e.ExamType
        WHEN 'DIAGNOSTIC' THEN N'Chẩn đoán năng lực'
        WHEN 'MOCK'       THEN N'Thi thử'
        WHEN 'QUIZ'       THEN N'Kiểm tra nhanh'
    END AS ExamTypeName,
    e.DurationMin,
    qc.QuestionCount,
    e.CreatedAt
FROM dbo.Exams AS e
CROSS APPLY (
    SELECT COUNT(*) AS QuestionCount
    FROM dbo.ExamQuestions AS eq
    WHERE eq.ExamID = e.ExamID
) AS qc
WHERE qc.QuestionCount > 0;
GO

PRINT '    + Đã tạo: vw_CompetencyTree, vw_LearningResourceCatalog, vw_QuestionBank, vw_ExamSummary, vw_AvailableExams';
GO

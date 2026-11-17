USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 8
HÀM BẢNG INLINE (VIEW CÓ THAM SỐ), VIEW CẬP NHẬT ĐƯỢC (WITH CHECK OPTION) VÀ INSTEAD OF TRIGGER
-------------------------------------------------------------------------------
- View thường không nhận tham số -> dùng inline table-valued function (iTVF) để truy vấn
  theo học sinh / năng lực / khoảng thời gian; trình tối ưu coi iTVF như view (được mở rộng inline).
- WITH CHECK OPTION: không cho cập nhật làm dòng "biến mất" khỏi điều kiện của view.
- INSTEAD OF trigger: cho phép UPDATE trên view có JOIN nhưng chỉ ghi vào cột được phép.
===============================================================================
*/
PRINT '>>> [08_vw_parameterized_updatable.sql] Đang tạo hàm bảng inline và view cập nhật được...';
GO

/* ===== 1. NĂNG LỰC YẾU CỦA MỘT HỌC SINH + HỌC LIỆU NGẮN NHẤT ĐỂ ÔN (Core Flow 2/3) ===== */
CREATE OR ALTER FUNCTION dbo.fn_WeakCompetencies
(
    @StudentID INT,
    @Threshold DECIMAL(5,4) = 0.6500
)
RETURNS TABLE
AS
RETURN
(
    SELECT
        p.StudentID,
        p.SubjectName,
        p.CompetencyID,
        p.CompetencyName,
        p.Mastery,
        p.MasteryPercent,
        p.AttemptCount,
        rs.ResourceID,
        rs.Title        AS SuggestedResourceTitle,
        rs.ResourceType AS SuggestedResourceType,
        rs.EstimatedMin AS SuggestedResourceMin
    FROM dbo.vw_StudentCompetencyProfile AS p
    OUTER APPLY (
        SELECT TOP 1 r.ResourceID, r.Title, r.ResourceType, r.EstimatedMin
        FROM dbo.LearningResources AS r
        WHERE r.CompetencyID = p.CompetencyID
        ORDER BY r.EstimatedMin ASC, r.ResourceID ASC       -- cùng quy tắc với sp_GenerateRecommendations
    ) AS rs
    WHERE p.StudentID = @StudentID
      AND p.Mastery < @Threshold
);
GO

/* ===== 2. NGÂN HÀNG CÂU HỎI ĐỂ LUYỆN TẬP THÍCH ỨNG (không lộ đáp án, loại câu đã làm đúng) ===== */
CREATE OR ALTER FUNCTION dbo.fn_PracticeCandidates
(
    @StudentID    INT,
    @CompetencyID INT,
    @MinDifficulty TINYINT = 1,
    @MaxDifficulty TINYINT = 5
)
RETURNS TABLE
AS
RETURN
(
    SELECT
        q.QuestionID,
        q.CompetencyID,
        q.Content AS QuestionContent,
        q.Difficulty,
        q.IsAIGenerated
    FROM dbo.Questions AS q
    WHERE q.CompetencyID = @CompetencyID
      AND q.IsApproved = 1
      AND q.Difficulty BETWEEN @MinDifficulty AND @MaxDifficulty
      AND NOT EXISTS (
            SELECT 1
            FROM dbo.AttemptAnswers AS aa
            INNER JOIN dbo.ExamAttempts AS ea ON ea.AttemptID = aa.AttemptID
            WHERE ea.StudentID = @StudentID
              AND ea.SubmittedAt IS NOT NULL
              AND aa.QuestionID = q.QuestionID
              AND aa.IsCorrect = 1
      )
);
GO

/* ===== 3. THỜI GIAN HỌC THEO NGÀY TRONG KHOẢNG @From - @To ===== */
CREATE OR ALTER FUNCTION dbo.fn_StudyTimeBetween
(
    @StudentID INT,
    @From      DATE,
    @To        DATE
)
RETURNS TABLE
AS
RETURN
(
    SELECT
        sl.StudentID,
        CAST(sl.LoggedAt AS DATE) AS StudyDate,
        COUNT(*) AS SessionCount,
        SUM(sl.DurationMin) AS TotalMin
    FROM dbo.StudyLogs AS sl
    WHERE sl.StudentID = @StudentID
      AND CAST(sl.LoggedAt AS DATE) BETWEEN @From AND @To
    GROUP BY sl.StudentID, CAST(sl.LoggedAt AS DATE)
);
GO

/* ===== 4. LỊCH SỬ ĐIỂM THEO LƯỢT LÀM CỦA MỘT HỌC SINH + THAY ĐỔI SO VỚI LƯỢT TRƯỚC (LAG) ===== */
CREATE OR ALTER FUNCTION dbo.fn_ScoreTrend
(
    @StudentID INT
)
RETURNS TABLE
AS
RETURN
(
    SELECT
        t.StudentID,
        t.AttemptID,
        t.ExamID,
        t.ExamTitle,
        t.SubmittedAt,
        t.Score,
        t.PrevScore,
        t.Score - t.PrevScore AS ScoreChange,
        CASE
            WHEN t.PrevScore IS NULL THEN N'Lần đầu'
            WHEN t.Score > t.PrevScore THEN N'Tăng'
            WHEN t.Score < t.PrevScore THEN N'Giảm'
            ELSE N'Giữ nguyên'
        END AS Trend
    FROM (
        SELECT
            ea.StudentID,
            ea.AttemptID,
            ea.ExamID,
            e.Title AS ExamTitle,
            ea.SubmittedAt,
            ea.Score,
            LAG(ea.Score) OVER (ORDER BY ea.SubmittedAt, ea.AttemptID) AS PrevScore
        FROM dbo.ExamAttempts AS ea
        INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
        WHERE ea.StudentID = @StudentID
          AND ea.SubmittedAt IS NOT NULL
          AND ea.Score IS NOT NULL
    ) AS t
);
GO

/* ===== 5. KẾT QUẢ THEO ĐỀ (GIÁO VIÊN) ===== */
CREATE OR ALTER FUNCTION dbo.fn_ExamResults
(
    @ExamID INT
)
RETURNS TABLE
AS
RETURN
(
    SELECT
        r.AttemptID,
        r.ExamID,
        r.ExamTitle,
        r.StudentID,
        r.StudentName,
        r.SubmittedAt,
        r.Score,
        r.CorrectCount,
        r.TotalQuestions,
        r.AccuracyPercent
    FROM dbo.vw_AttemptResults AS r
    WHERE r.ExamID = @ExamID
      AND r.SubmittedAt IS NOT NULL
);
GO

/* ===== 6. VIEW CẬP NHẬT ĐƯỢC: HỒ SƠ HỌC SINH (đặt mục tiêu điểm, thời gian học mỗi ngày) ===== */
-- Chỉ lộ các cột học sinh được phép sửa; WITH CHECK OPTION buộc TargetScore trong 0..1200 và DailyStudyMin > 0
-- (cùng ràng buộc CHECK của bảng gốc, kiểm tra thêm ở tầng view). RLS của StudentProfiles vẫn áp dụng.
CREATE OR ALTER VIEW dbo.vw_StudentEditableProfile
AS
SELECT
    sp.StudentID,
    sp.SchoolName,
    sp.TargetScore,
    sp.ExamDate,
    sp.DailyStudyMin
FROM dbo.StudentProfiles AS sp
WHERE sp.TargetScore BETWEEN 0 AND 1200 AND sp.DailyStudyMin > 0
WITH CHECK OPTION;
GO

/* ===== 7. VIEW CẬP NHẬT ĐƯỢC: LỘ TRÌNH ĐANG HOẠT ĐỘNG ===== */
-- WITH CHECK OPTION: không thể UPDATE Status sang giá trị khác 'ACTIVE' qua view này
-- (muốn kết thúc / thay thế lộ trình phải cập nhật trên bảng LearningPaths).
CREATE OR ALTER VIEW dbo.vw_ActiveLearningPaths
AS
SELECT
    lp.PathID,
    lp.StudentID,
    lp.StartDate,
    lp.EndDate,
    lp.Status,
    lp.GeneratedAt
FROM dbo.LearningPaths AS lp
WHERE lp.Status = 'ACTIVE'
WITH CHECK OPTION;
GO

/* ===== 8. INSTEAD OF TRIGGER: CHỈ CHO PHÉP ĐÁNH DẤU ĐÃ ĐỌC TRÊN HỘP THƯ THÔNG BÁO ===== */
CREATE OR ALTER TRIGGER dbo.tr_vw_NotificationInbox_MarkRead
ON dbo.vw_NotificationInbox
INSTEAD OF UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF UPDATE(NotificationID) OR UPDATE(UserID) OR UPDATE(StudentID) OR UPDATE(StudentName)
       OR UPDATE(NotifyType) OR UPDATE(NotifyTypeName) OR UPDATE(Message) OR UPDATE(CreatedAt)
        THROW 52001, N'Chỉ được phép cập nhật cột IsRead trên vw_NotificationInbox.', 1;

    UPDATE n
       SET n.IsRead = i.IsRead
    FROM dbo.Notifications AS n
    INNER JOIN inserted AS i ON i.NotificationID = n.NotificationID;
END;
GO

PRINT '    + Đã tạo: fn_WeakCompetencies, fn_PracticeCandidates, fn_StudyTimeBetween, fn_ScoreTrend, fn_ExamResults, vw_StudentEditableProfile, vw_ActiveLearningPaths, tr_vw_NotificationInbox_MarkRead';
GO

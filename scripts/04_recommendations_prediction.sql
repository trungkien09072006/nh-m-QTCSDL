USE AILearningDB;
GO
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/*
===============================================================================
PHẦN 2 - GỢI Ý HỌC VÀ DỰ ĐOÁN ĐIỂM: SCRIPT SQL RIÊNG
-------------------------------------------------------------------------------
- Chạy lại được nhiều lần (CREATE OR ALTER), không xóa dữ liệu.
- KHÔNG sửa 02_stored_procedures.sql. Module này vẫn dùng nguyên
  sp_GenerateRecommendations và sp_CalculateScorePrediction đã có.
- Chỉ bổ sung một thủ tục hỗ trợ:
    sp_SyncMasteryFromAnswers : dựng hồ sơ năng lực (StudentCompetency) từ lịch
                                sử bài làm đã nộp khi học sinh chưa có dữ liệu.
- Nếu chưa chạy script này, API vẫn hoạt động nhưng bỏ qua bước dựng hồ sơ năng lực.
===============================================================================
*/

/* ===== 1. ĐỒNG BỘ MỨC THÀNH THẠO TỪ LỊCH SỬ LÀM BÀI ===== */
-- Mastery = (số câu đúng + 1) / (số câu đã làm + 2)   (làm mượt Laplace)
--   -> học sinh mới làm 1 câu đúng không bị coi là 100%, làm sai 1 câu không bị coi là 0%.
-- @Overwrite = 0 (mặc định): chỉ thêm năng lực CHƯA có dòng trong StudentCompetency,
--                            không ghi đè giá trị do luồng làm bài/chẩn đoán đã cập nhật.
-- @Overwrite = 1           : tính lại toàn bộ từ lịch sử bài làm đã nộp.
CREATE OR ALTER PROCEDURE dbo.sp_SyncMasteryFromAnswers
    @StudentID INT,
    @Overwrite BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @History TABLE (
        CompetencyID INT PRIMARY KEY,
        Mastery      DECIMAL(5,4) NOT NULL,
        AttemptCount INT NOT NULL
    );

    INSERT INTO @History (CompetencyID, Mastery, AttemptCount)
    SELECT
        q.CompetencyID,
        CAST((SUM(CASE WHEN aa.IsCorrect = 1 THEN 1.0 ELSE 0.0 END) + 1.0)
             / (COUNT(*) + 2.0) AS DECIMAL(5,4)),
        COUNT(DISTINCT ea.AttemptID)
    FROM dbo.ExamAttempts AS ea
    INNER JOIN dbo.AttemptAnswers AS aa
        ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
    INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
    WHERE ea.StudentID = @StudentID
      AND ea.SubmittedAt IS NOT NULL
      AND aa.IsCorrect IS NOT NULL
    GROUP BY q.CompetencyID;

    IF @Overwrite = 1
    BEGIN
        UPDATE sc
        SET sc.Mastery = h.Mastery,
            sc.AttemptCount = h.AttemptCount,
            sc.UpdatedAt = SYSDATETIME()
        FROM dbo.StudentCompetency AS sc
        INNER JOIN @History AS h ON h.CompetencyID = sc.CompetencyID
        WHERE sc.StudentID = @StudentID;
    END;

    INSERT INTO dbo.StudentCompetency (StudentID, CompetencyID, Mastery, AttemptCount, UpdatedAt)
    SELECT @StudentID, h.CompetencyID, h.Mastery, h.AttemptCount, SYSDATETIME()
    FROM @History AS h
    WHERE NOT EXISTS (
        SELECT 1
        FROM dbo.StudentCompetency AS sc
        WHERE sc.StudentID = @StudentID AND sc.CompetencyID = h.CompetencyID
    );
END;
GO

PRINT '>>> Đã tạo: sp_SyncMasteryFromAnswers';
GO

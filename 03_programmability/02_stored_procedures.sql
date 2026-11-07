USE AILearningDB;
GO

/* ===== 1. TỰ ĐỘNG GỢI Ý BÀI HỌC THEO ĐIỂM YẾU (CÓ GIẢI THÍCH TỪ DỮ LIỆU) ===== */
CREATE OR ALTER PROCEDURE dbo.sp_GenerateRecommendations
    @StudentID INT
AS
BEGIN
    SET NOCOUNT ON;

    -- 1a. Gợi ý học liệu cho các năng lực có Mastery < 0.65
    INSERT INTO dbo.Recommendations (StudentID, QuestionID, ResourceID, Reason, IsAccepted)
    SELECT
        sc.StudentID,
        NULL AS QuestionID,
        lr.ResourceID,
        CONCAT(
            N'Mức độ thành thạo chủ đề "', c.CompetencyName, N'" hiện đạt ',
            CAST(CAST(ROUND(sc.Mastery * 100, 0) AS INT) AS NVARCHAR(10)),
            N'% qua ', sc.AttemptCount,
            N' lượt làm bài. Hệ thống gợi ý học liệu "', lr.Title,
            N'" (', lr.EstimatedMin, N' phút) để củng cố kiến thức.'
        ) AS Reason,
        NULL AS IsAccepted
    FROM dbo.StudentCompetency AS sc
    INNER JOIN dbo.Competencies AS c ON c.CompetencyID = sc.CompetencyID
    CROSS APPLY (
        SELECT TOP 1 r.ResourceID, r.Title, r.EstimatedMin
        FROM dbo.LearningResources AS r
        WHERE r.CompetencyID = sc.CompetencyID
        ORDER BY r.EstimatedMin ASC, r.ResourceID ASC
    ) AS lr
    WHERE sc.StudentID = @StudentID
      AND sc.Mastery < 0.65
      AND NOT EXISTS (
          SELECT 1
          FROM dbo.Recommendations AS rec
          WHERE rec.StudentID = @StudentID
            AND rec.ResourceID = lr.ResourceID
            AND ISNULL(rec.IsAccepted, 0) = 0
      );

    -- 1b. Gợi ý ôn lại câu hỏi đã làm sai trong các lượt thi đã nộp
    INSERT INTO dbo.Recommendations (StudentID, QuestionID, ResourceID, Reason, IsAccepted)
    SELECT TOP 2
        ea.StudentID,
        aa.QuestionID,
        NULL AS ResourceID,
        CONCAT(
            N'Bạn đã chọn sai câu hỏi thuộc chủ đề "', c.CompetencyName,
            N'" (độ khó ', q.Difficulty, N'/5, thời gian suy nghĩ ',
            ISNULL(aa.TimeSpentSec, 0), N' giây). Hãy xem lại lời giải chi tiết.'
        ) AS Reason,
        NULL AS IsAccepted
    FROM dbo.AttemptAnswers AS aa
    INNER JOIN dbo.ExamAttempts AS ea ON ea.AttemptID = aa.AttemptID AND ea.ExamID = aa.ExamID
    INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
    INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
    WHERE ea.StudentID = @StudentID
      AND ea.SubmittedAt IS NOT NULL
      AND aa.IsCorrect = 0
      AND NOT EXISTS (
          SELECT 1
          FROM dbo.Recommendations AS rec
          WHERE rec.StudentID = @StudentID
            AND rec.QuestionID = aa.QuestionID
            AND ISNULL(rec.IsAccepted, 0) = 0
      )
    ORDER BY ea.SubmittedAt DESC;
END;
GO

/* ===== 2. DỰ ĐOÁN TIẾN ĐỘ VÀ ĐIỂM SỐ ĐGNL ===== */
CREATE OR ALTER PROCEDURE dbo.sp_CalculateScorePrediction
    @StudentID INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @TargetScore INT;
    DECLARE @DailyStudyMin INT;
    DECLARE @AvgMastery DECIMAL(5,4);
    DECLARE @LatestExamScore DECIMAL(6,2);
    DECLARE @Minutes7d INT;

    SELECT
        @TargetScore = TargetScore,
        @DailyStudyMin = DailyStudyMin
    FROM dbo.StudentProfiles
    WHERE StudentID = @StudentID;

    IF @TargetScore IS NULL
        RETURN;

    SELECT @AvgMastery = AVG(Mastery)
    FROM dbo.StudentCompetency
    WHERE StudentID = @StudentID;

    SELECT TOP 1 @LatestExamScore = Score
    FROM dbo.ExamAttempts
    WHERE StudentID = @StudentID AND SubmittedAt IS NOT NULL AND Score IS NOT NULL
    ORDER BY SubmittedAt DESC, AttemptID DESC;

    SELECT @Minutes7d = ISNULL(SUM(DurationMin), 0)
    FROM dbo.StudyLogs
    WHERE StudentID = @StudentID
      AND LoggedAt >= DATEADD(DAY, -7, SYSDATETIME());

    SET @AvgMastery = ISNULL(@AvgMastery, 0.5000);
    DECLARE @NormalizedExam DECIMAL(6,2) = CASE
        WHEN @LatestExamScore IS NULL THEN @AvgMastery * 1200.0
        WHEN @LatestExamScore <= 100.0 THEN @LatestExamScore * 12.0
        ELSE @LatestExamScore
    END;

    DECLARE @WeeklyGoalMin INT = ISNULL(@DailyStudyMin, 60) * 7;
    DECLARE @StudyRatio DECIMAL(5,4) = CASE
        WHEN @WeeklyGoalMin <= 0 THEN 0.5
        WHEN 1.0 * @Minutes7d / @WeeklyGoalMin > 1.0 THEN 1.0
        ELSE CAST(1.0 * @Minutes7d / @WeeklyGoalMin AS DECIMAL(5,4))
    END;

    DECLARE @PredictedScore DECIMAL(6,2) = ROUND(
        (@AvgMastery * 1200.0 * 0.55) + (@NormalizedExam * 0.30) + (@StudyRatio * 1200.0 * 0.15),
        2
    );

    IF @PredictedScore > 1200 SET @PredictedScore = 1200;
    IF @PredictedScore < 0 SET @PredictedScore = 0;

    DECLARE @ProbReachTarget DECIMAL(5,4) = CASE
        WHEN @TargetScore <= 0 THEN 1.0000
        WHEN @PredictedScore >= @TargetScore THEN 0.9000
        ELSE CAST(ROUND((@PredictedScore / @TargetScore) * 0.85, 4) AS DECIMAL(5,4))
    END;

    DECLARE @WeakestComp NVARCHAR(150);
    SELECT TOP 1 @WeakestComp = c.CompetencyName
    FROM dbo.StudentCompetency AS sc
    INNER JOIN dbo.Competencies AS c ON c.CompetencyID = sc.CompetencyID
    WHERE sc.StudentID = @StudentID
    ORDER BY sc.Mastery ASC;

    DECLARE @RiskNote NVARCHAR(300) = CASE
        WHEN @ProbReachTarget < 0.6000 THEN CONCAT(
            N'Nguy cơ chậm mục tiêu ', @TargetScore,
            N' điểm. Cần ưu tiên cải thiện chủ đề "', ISNULL(@WeakestComp, N'trọng tâm'),
            N'" và duy trì đủ ', @WeeklyGoalMin, N' phút học/tuần.'
        )
        WHEN @StudyRatio < 0.5000 THEN CONCAT(
            N'Thời lượng học 7 ngày qua (', @Minutes7d, N'/', @WeeklyGoalMin,
            N' phút) còn thấp. Hãy tăng thời gian ôn tập để giữ vững tiến độ.'
        )
        ELSE CONCAT(
            N'Tiến độ khả quan! Hãy tiếp tục ôn luyện chủ đề "',
            ISNULL(@WeakestComp, N'nâng cao'), N'" để bứt phá mục tiêu ', @TargetScore, N' điểm.'
        )
    END;

    INSERT INTO dbo.ScorePredictions (StudentID, PredictedScore, ProbReachTarget, RiskNote)
    VALUES (@StudentID, @PredictedScore, @ProbReachTarget, @RiskNote);
END;
GO

/* ===== 3. TỰ ĐỘNG TẠO THÔNG BÁO PHÙ HỢP ===== */
CREATE OR ALTER PROCEDURE dbo.sp_GenerateNotifications
    @StudentID INT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (
        SELECT 1 FROM dbo.StudyLogs
        WHERE StudentID = @StudentID
          AND LoggedAt >= DATEADD(DAY, -3, SYSDATETIME())
    )
    AND NOT EXISTS (
        SELECT 1 FROM dbo.Notifications
        WHERE UserID = @StudentID AND NotifyType = 'INACTIVITY' AND IsRead = 0
    )
    BEGIN
        INSERT INTO dbo.Notifications (UserID, StudentID, NotifyType, Message)
        VALUES (
            @StudentID,
            @StudentID,
            'INACTIVITY',
            N'Bạn chưa ghi nhận hoạt động học tập nào trong 3 ngày qua. Hãy dành 15-30 phút ôn tập hôm nay nhé!'
        );
    END;

    DECLARE @OverdueCount INT;
    SELECT @OverdueCount = COUNT(*)
    FROM dbo.LearningPaths AS lp
    INNER JOIN dbo.LearningPathItems AS lpi ON lpi.PathID = lp.PathID
    WHERE lp.StudentID = @StudentID
      AND lp.Status = 'ACTIVE'
      AND lpi.Status IN ('TODO', 'DOING')
      AND lpi.ScheduledDate <= CAST(SYSDATETIME() AS DATE);

    IF @OverdueCount > 0
    AND NOT EXISTS (
        SELECT 1 FROM dbo.Notifications
        WHERE UserID = @StudentID AND NotifyType = 'BEHIND_SCHEDULE' AND IsRead = 0
    )
    BEGIN
        INSERT INTO dbo.Notifications (UserID, StudentID, NotifyType, Message)
        VALUES (
            @StudentID,
            @StudentID,
            'BEHIND_SCHEDULE',
            CONCAT(N'Bạn đang có ', @OverdueCount, N' nhiệm vụ trong lộ trình học tập đến hạn hoặc trễ lịch cần hoàn thành.')
        );
    END;

    DECLARE @LatestProb DECIMAL(5,4);
    DECLARE @LatestPredicted DECIMAL(6,2);
    SELECT TOP 1
        @LatestProb = ProbReachTarget,
        @LatestPredicted = PredictedScore
    FROM dbo.ScorePredictions
    WHERE StudentID = @StudentID
    ORDER BY PredictedAt DESC, PredictionID DESC;

    IF @LatestProb IS NOT NULL AND @LatestProb < 0.7000
    AND NOT EXISTS (
        SELECT 1 FROM dbo.Notifications
        WHERE UserID = @StudentID AND NotifyType = 'LOW_PROBABILITY' AND IsRead = 0
    )
    BEGIN
        INSERT INTO dbo.Notifications (UserID, StudentID, NotifyType, Message)
        VALUES (
            @StudentID,
            @StudentID,
            'LOW_PROBABILITY',
            CONCAT(
                N'Dự đoán điểm hiện tại là ', CAST(@LatestPredicted AS NVARCHAR(20)),
                N' (xác suất đạt mục tiêu ', CAST(CAST(ROUND(@LatestProb * 100, 0) AS INT) AS NVARCHAR(10)),
                N'%). Hãy xem các học liệu được gợi ý để cải thiện điểm yếu.'
            )
        );
    END;
END;
GO

/* ===== 4. TRỢ LÝ HỎI ĐÁP DỰA TRÊN DỮ LIỆU HỌC TẬP (AI TUTOR BƯỚC ĐẦU) ===== */
CREATE OR ALTER PROCEDURE dbo.sp_AskTutor
    @StudentID  INT,
    @UserMessage NVARCHAR(MAX),
    @QuestionID INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @SessionID INT;
    SELECT TOP 1 @SessionID = SessionID
    FROM dbo.TutorSessions
    WHERE StudentID = @StudentID
    ORDER BY StartedAt DESC, SessionID DESC;

    IF @SessionID IS NULL
    BEGIN
        INSERT INTO dbo.TutorSessions (StudentID) VALUES (@StudentID);
        SET @SessionID = SCOPE_IDENTITY();
    END;

    INSERT INTO dbo.TutorMessages (SessionID, Sender, Content, QuestionID)
    VALUES (@SessionID, 'USER', @UserMessage, @QuestionID);

    DECLARE @Reply NVARCHAR(MAX);

    IF @QuestionID IS NOT NULL
    BEGIN
        SELECT
            @Reply = CONCAT(
                N'Giải thích cho câu hỏi thuộc chủ đề "', c.CompetencyName, N'": ',
                ISNULL(q.Explanation, N'Câu hỏi này hiện chưa có lời giải chi tiết.'),
                CASE WHEN o.OptionLabel IS NOT NULL
                     THEN CONCAT(N' Đáp án đúng là phương án ', o.OptionLabel, N' (', o.OptionText, N').')
                     ELSE N'' END
            )
        FROM dbo.Questions AS q
        INNER JOIN dbo.Competencies AS c ON c.CompetencyID = q.CompetencyID
        LEFT JOIN dbo.QuestionOptions AS o ON o.QuestionID = q.QuestionID AND o.IsCorrect = 1
        WHERE q.QuestionID = @QuestionID;
    END;

    IF @Reply IS NULL
    BEGIN
        DECLARE @WeakComp NVARCHAR(150);
        DECLARE @WeakMastery INT;
        DECLARE @RecTitle NVARCHAR(200);

        SELECT TOP 1
            @WeakComp = c.CompetencyName,
            @WeakMastery = CAST(ROUND(sc.Mastery * 100, 0) AS INT)
        FROM dbo.StudentCompetency AS sc
        INNER JOIN dbo.Competencies AS c ON c.CompetencyID = sc.CompetencyID
        WHERE sc.StudentID = @StudentID
        ORDER BY sc.Mastery ASC;

        SELECT TOP 1 @RecTitle = lr.Title
        FROM dbo.Recommendations AS r
        INNER JOIN dbo.LearningResources AS lr ON lr.ResourceID = r.ResourceID
        WHERE r.StudentID = @StudentID AND ISNULL(r.IsAccepted, 0) = 0
        ORDER BY r.CreatedAt DESC;

        SET @Reply = CONCAT(
            N'Dựa trên dữ liệu học tập hiện tại của bạn, năng lực cần ưu tiên cải thiện nhất là "',
            ISNULL(@WeakComp, N'Đại số & Tư duy logic'), N'" (mức thành thạo ',
            ISNULL(CAST(@WeakMastery AS NVARCHAR(10)), N'50'), N'%). ',
            CASE WHEN @RecTitle IS NOT NULL
                 THEN CONCAT(N'Bạn nên bắt đầu với học liệu "', @RecTitle, N'" trong mục Gợi ý cá nhân hóa, hoặc chọn một câu hỏi cụ thể bên trên để xem lời giải chi tiết nhé!')
                 ELSE N'Hãy chọn một câu hỏi cụ thể ở khung bên trên để mình trích xuất lời giải và phương pháp làm bài cho bạn nhé!' END
        );
    END;

    INSERT INTO dbo.TutorMessages (SessionID, Sender, Content, QuestionID)
    VALUES (@SessionID, 'AI', @Reply, @QuestionID);

    INSERT INTO dbo.StudyLogs (StudentID, ActivityType, DurationMin)
    VALUES (@StudentID, 'TUTOR', 5);
END;
GO
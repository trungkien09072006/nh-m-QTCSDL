USE AILearningDB;
GO

SET NOCOUNT ON;

/*
===============================================================================
PHẦN 2 - DỮ LIỆU MẪU ĐỂ TỰ KIỂM THỬ GỢI Ý HỌC VÀ DỰ ĐOÁN ĐIỂM
-------------------------------------------------------------------------------
- Không phụ thuộc luồng làm bài/chẩn đoán của thành viên khác.
- Chạy lại được nhiều lần (có kiểm tra tồn tại trước khi chèn).
- Chạy SAU: 01_schema (đủ 00_run_all) và 04_recommendations_prediction.sql.
- Học sinh mẫu: student1@gmail.com (nếu không có thì lấy học sinh đầu tiên).
- Đây chỉ là dữ liệu mẫu để thử nghiệm, KHÔNG phải kết quả học tập thật.
===============================================================================
*/
BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @StudentID INT = (SELECT UserID FROM dbo.Users WHERE Email = 'student1@gmail.com');
    IF @StudentID IS NULL
        SET @StudentID = (
            SELECT TOP (1) u.UserID
            FROM dbo.Users AS u
            INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
            WHERE r.RoleName = 'Student'
            ORDER BY u.UserID
        );
    DECLARE @TeacherID INT = (
        SELECT TOP (1) u.UserID
        FROM dbo.Users AS u
        INNER JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
        WHERE r.RoleName = 'Teacher'
        ORDER BY u.UserID
    );

    IF @StudentID IS NULL OR @TeacherID IS NULL
        THROW 50010, N'Cần có ít nhất một học sinh và một giáo viên (chạy 04_seed_data.sql trước).', 1;

    IF NOT EXISTS (SELECT 1 FROM dbo.StudentProfiles WHERE StudentID = @StudentID)
        THROW 50011, N'Học sinh mẫu chưa có StudentProfiles.', 1;

    /* 1. Ngày thi trong tương lai (seed gốc đặt ngày đã qua) */
    UPDATE dbo.StudentProfiles
    SET ExamDate = DATEADD(DAY, 75, CAST(SYSDATETIME() AS DATE))
    WHERE StudentID = @StudentID
      AND (ExamDate IS NULL OR ExamDate <= CAST(SYSDATETIME() AS DATE));

    /* 2. Mỗi năng lực có ít nhất một học liệu để gợi ý */
    INSERT INTO dbo.LearningResources (CompetencyID, Title, ResourceType, Url, EstimatedMin, CreatedBy)
    SELECT c.CompetencyID,
           CONCAT(N'Ôn tập nhanh: ', c.CompetencyName),
           'ARTICLE',
           NULL,
           20,
           @TeacherID
    FROM dbo.Competencies AS c
    WHERE NOT EXISTS (
        SELECT 1 FROM dbo.LearningResources AS r WHERE r.CompetencyID = c.CompetencyID
    );

    /* 3. Hồ sơ năng lực mẫu: thiếu năng lực nào thì thêm năng lực đó (không ghi đè) */
    INSERT INTO dbo.StudentCompetency (StudentID, CompetencyID, Mastery, AttemptCount)
    SELECT @StudentID, c.CompetencyID,
           CASE c.CompetencyName
               WHEN N'Suy luận logic'    THEN 0.8000
               WHEN N'Đại số'            THEN 0.2000
               WHEN N'Phân tích quy luật' THEN 0.4500
               WHEN N'Hình học'          THEN 0.5800
               ELSE 0.5000
           END,
           2
    FROM dbo.Competencies AS c
    WHERE NOT EXISTS (
        SELECT 1 FROM dbo.StudentCompetency AS sc
        WHERE sc.StudentID = @StudentID AND sc.CompetencyID = c.CompetencyID
    );

    /* 4. Nhật ký học 7 ngày gần đây (chỉ thêm khi học sinh còn rất ít nhật ký) */
    IF (SELECT COUNT(*) FROM dbo.StudyLogs WHERE StudentID = @StudentID) < 6
    BEGIN
        INSERT INTO dbo.StudyLogs (StudentID, ActivityType, DurationMin, LoggedAt)
        VALUES
            (@StudentID, 'LESSON', 40, DATEADD(DAY, -1, SYSDATETIME())),
            (@StudentID, 'QUIZ',   30, DATEADD(DAY, -2, SYSDATETIME())),
            (@StudentID, 'LESSON', 50, DATEADD(DAY, -4, SYSDATETIME())),
            (@StudentID, 'QUIZ',   25, DATEADD(DAY, -5, SYSDATETIME())),
            (@StudentID, 'TUTOR',  15, DATEADD(DAY, -6, SYSDATETIME()));
    END;

    COMMIT TRANSACTION;
    PRINT N'>> Đã nạp dữ liệu mẫu cho phần Gợi ý học & Dự đoán điểm (StudentID = '
          + CAST(@StudentID AS NVARCHAR(10)) + N').';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

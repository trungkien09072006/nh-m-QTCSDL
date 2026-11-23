USE AILearningDB;
GO

SET NOCOUNT ON;

/*
===============================================================================
PHẦN 4 - DỮ LIỆU MẪU CHO LỘ TRÌNH HỌC VÀ TIẾN ĐỘ
- Chạy lại được nhiều lần (idempotent), không làm trùng dữ liệu.
- Chạy sau: 01_schema\00_run_all.sql (có 04_seed_data.sql).
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
        THROW 50020, N'Cần có ít nhất một học sinh và một giáo viên (chạy 04_seed_data.sql trước).', 1;

    -- 1. Đảm bảo mỗi năng lực có ít nhất 1 học liệu
    INSERT INTO dbo.LearningResources (CompetencyID, Title, ResourceType, Url, EstimatedMin, CreatedBy)
    SELECT c.CompetencyID,
           CONCAT(N'Bài giảng trọng tâm: ', c.CompetencyName),
           'ARTICLE',
           'https://ai-edu.vn/tailieu/ontap',
           20,
           @TeacherID
    FROM dbo.Competencies AS c
    WHERE NOT EXISTS (
        SELECT 1 FROM dbo.LearningResources AS r WHERE r.CompetencyID = c.CompetencyID
    );

    -- 2. Lấy hoặc tạo lộ trình ACTIVE cho học sinh
    DECLARE @PathID INT = (
        SELECT TOP (1) PathID
        FROM dbo.LearningPaths
        WHERE StudentID = @StudentID AND Status = 'ACTIVE'
    );

    IF @PathID IS NULL
    BEGIN
        INSERT INTO dbo.LearningPaths (StudentID, StartDate, EndDate, Status)
        VALUES (
            @StudentID,
            DATEADD(DAY, -5, CAST(SYSDATETIME() AS DATE)),
            DATEADD(DAY, 25, CAST(SYSDATETIME() AS DATE)),
            'ACTIVE'
        );
        SET @PathID = SCOPE_IDENTITY();
    END;

    -- 3. Lấy các năng lực & học liệu tương ứng
    DECLARE @CompLogic INT = (SELECT TOP 1 CompetencyID FROM dbo.Competencies WHERE CompetencyName = N'Suy luận logic');
    DECLARE @CompRule  INT = (SELECT TOP 1 CompetencyID FROM dbo.Competencies WHERE CompetencyName = N'Phân tích quy luật');
    DECLARE @CompAlg   INT = (SELECT TOP 1 CompetencyID FROM dbo.Competencies WHERE CompetencyName = N'Đại số');
    DECLARE @CompGeo   INT = (SELECT TOP 1 CompetencyID FROM dbo.Competencies WHERE CompetencyName = N'Hình học');

    DECLARE @ResLogic INT = (SELECT TOP 1 ResourceID FROM dbo.LearningResources WHERE CompetencyID = @CompLogic ORDER BY ResourceID);
    DECLARE @ResRule  INT = (SELECT TOP 1 ResourceID FROM dbo.LearningResources WHERE CompetencyID = @CompRule ORDER BY ResourceID);
    DECLARE @ResAlg   INT = (SELECT TOP 1 ResourceID FROM dbo.LearningResources WHERE CompetencyID = @CompAlg ORDER BY ResourceID);
    DECLARE @ResGeo   INT = (SELECT TOP 1 ResourceID FROM dbo.LearningResources WHERE CompetencyID = @CompGeo ORDER BY ResourceID);

    -- 4. Chèn thêm nhiệm vụ mẫu nếu lộ trình hiện có ít hơn 5 nhiệm vụ
    IF (SELECT COUNT(*) FROM dbo.LearningPathItems WHERE PathID = @PathID) < 5
    BEGIN
        IF @CompLogic IS NOT NULL
            INSERT INTO dbo.LearningPathItems (PathID, CompetencyID, ResourceID, ScheduledDate, Priority, Status)
            VALUES (@PathID, @CompLogic, @ResLogic, DATEADD(DAY, -2, CAST(SYSDATETIME() AS DATE)), 1, 'DONE');

        IF @CompRule IS NOT NULL
            INSERT INTO dbo.LearningPathItems (PathID, CompetencyID, ResourceID, ScheduledDate, Priority, Status)
            VALUES (@PathID, @CompRule, @ResRule, DATEADD(DAY, -1, CAST(SYSDATETIME() AS DATE)), 1, 'DOING');

        IF @CompGeo IS NOT NULL
            INSERT INTO dbo.LearningPathItems (PathID, CompetencyID, ResourceID, ScheduledDate, Priority, Status)
            VALUES (@PathID, @CompGeo, @ResGeo, CAST(SYSDATETIME() AS DATE), 2, 'TODO');

        IF @CompAlg IS NOT NULL
            INSERT INTO dbo.LearningPathItems (PathID, CompetencyID, ResourceID, ScheduledDate, Priority, Status)
            VALUES (@PathID, @CompAlg, @ResAlg, DATEADD(DAY, 3, CAST(SYSDATETIME() AS DATE)), 3, 'TODO');

        IF @CompLogic IS NOT NULL
            INSERT INTO dbo.LearningPathItems (PathID, CompetencyID, ResourceID, ScheduledDate, Priority, Status)
            VALUES (@PathID, @CompLogic, @ResLogic, DATEADD(DAY, 5, CAST(SYSDATETIME() AS DATE)), 4, 'SKIPPED');
    END;

    COMMIT TRANSACTION;
    PRINT N'>> Đã nạp dữ liệu mẫu cho Lộ trình học & Tiến độ (PathID = ' + CAST(@PathID AS NVARCHAR(10)) + N').';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
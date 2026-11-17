USE AILearningDB;
GO
SET NOCOUNT ON;

/*
===============================================================================
PHÂN HỆ 02 - KIỂM THỬ DATA VIEWS
Chạy sau khi đã chạy 01_schema (có seed data), 02_data_views\01..09 và (cho TEST 7) 04_security.
Dữ liệu mẫu: 2 học sinh (student1 có 1 lượt thi MOCK 50 điểm, 1/2 câu đúng; student2 chưa làm bài),
1 phụ huynh của student1. Seed chưa có đề DIAGNOSTIC nên vw_DiagnosticResults rỗng là bình thường.
===============================================================================
*/
PRINT '===== KIỂM THỬ DATA VIEWS =====';
GO

-- TEST 1: Mọi view (vw_*) phải truy vấn được
PRINT '--- TEST 1: Truy vấn thử toàn bộ view ---';
DECLARE @v SYSNAME, @sql NVARCHAR(400), @n INT, @fail INT = 0;
DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT name FROM sys.views WHERE schema_id = SCHEMA_ID('dbo') AND name LIKE 'vw[_]%' ORDER BY name;
OPEN cur; FETCH NEXT FROM cur INTO @v;
WHILE @@FETCH_STATUS = 0
BEGIN
    BEGIN TRY
        SET @sql = N'SELECT @n = COUNT(*) FROM dbo.' + QUOTENAME(@v);
        EXEC sp_executesql @sql, N'@n INT OUTPUT', @n = @n OUTPUT;
        PRINT N'   OK   ' + @v + N': ' + CAST(@n AS NVARCHAR(20)) + N' dòng';
    END TRY
    BEGIN CATCH
        SET @fail += 1;
        PRINT N'   LỖI  ' + @v + N': ' + ERROR_MESSAGE();
    END CATCH;
    FETCH NEXT FROM cur INTO @v;
END;
CLOSE cur; DEALLOCATE cur;
PRINT CASE WHEN @fail = 0 THEN N'-> TEST 1: THÀNH CÔNG, mọi view đều truy vấn được.'
           ELSE N'-> TEST 1: THẤT BẠI, có ' + CAST(@fail AS NVARCHAR(10)) + N' view lỗi.' END;
GO

-- TEST 2: Không view / hàm nào được lộ PasswordHash
PRINT '';
PRINT '--- TEST 2: Không view / hàm nào chứa cột PasswordHash ---';
IF EXISTS (
    SELECT 1 FROM sys.columns AS c
    INNER JOIN sys.objects AS o ON o.object_id = c.object_id
    WHERE o.schema_id = SCHEMA_ID('dbo')
      AND (o.name LIKE 'vw[_]%' OR o.name LIKE 'fn[_]%')
      AND o.type IN ('V', 'IF')
      AND c.name = 'PasswordHash'
)
    PRINT '-> TEST 2: THẤT BẠI (có đối tượng lộ PasswordHash).';
ELSE
    PRINT '-> TEST 2: THÀNH CÔNG (không view / hàm nào lộ PasswordHash).';
GO

-- TEST 3: View dành cho học sinh / phụ huynh không được chứa cột lộ đáp án
PRINT '';
PRINT '--- TEST 3: View của học sinh không lộ IsCorrect / Explanation khi chưa nộp bài ---';
IF EXISTS (
    SELECT 1 FROM sys.columns AS c
    INNER JOIN sys.views AS v ON v.object_id = c.object_id
    WHERE v.name IN ('vw_AvailableExams', 'vw_Recommendations', 'vw_StudentExamView')
      AND c.name IN ('IsCorrect', 'Explanation', 'CorrectLabel', 'CorrectText')
)
    PRINT '-> TEST 3: THẤT BẠI (view lộ đáp án).';
ELSE
    PRINT '-> TEST 3: THÀNH CÔNG (không lộ đáp án).';
IF NOT EXISTS (SELECT 1 FROM dbo.vw_AnswerReview WHERE EXISTS (
        SELECT 1 FROM dbo.ExamAttempts ea WHERE ea.AttemptID = vw_AnswerReview.AttemptID AND ea.SubmittedAt IS NULL))
    PRINT '-> vw_AnswerReview chỉ gồm lượt đã nộp: ĐÚNG';
ELSE PRINT '-> vw_AnswerReview chứa lượt chưa nộp: SAI';
GO

-- TEST 4: Số liệu view khớp bảng gốc
PRINT '';
PRINT '--- TEST 4: Đối chiếu số liệu view với bảng gốc ---';
PRINT CASE WHEN (SELECT COUNT(*) FROM dbo.vw_QuestionBank) = (SELECT COUNT(*) FROM dbo.Questions)
           THEN '-> vw_QuestionBank = Questions: KHỚP' ELSE '-> vw_QuestionBank = Questions: LỆCH' END;
PRINT CASE WHEN (SELECT COUNT(*) FROM dbo.vw_AttemptResults) = (SELECT COUNT(*) FROM dbo.ExamAttempts)
           THEN '-> vw_AttemptResults = ExamAttempts: KHỚP' ELSE '-> vw_AttemptResults = ExamAttempts: LỆCH' END;
PRINT CASE WHEN (SELECT COUNT(*) FROM dbo.vw_StudentOverview) = (SELECT COUNT(*) FROM dbo.StudentProfiles)
           THEN '-> vw_StudentOverview = StudentProfiles: KHỚP' ELSE '-> vw_StudentOverview = StudentProfiles: LỆCH' END;
PRINT CASE WHEN (SELECT COUNT(*) FROM dbo.vw_AIStudentFeatures) = (SELECT COUNT(*) FROM dbo.StudentProfiles)
           THEN '-> vw_AIStudentFeatures = StudentProfiles: KHỚP' ELSE '-> vw_AIStudentFeatures = StudentProfiles: LỆCH' END;
PRINT CASE WHEN (SELECT ISNULL(SUM(QuestionCount), 0) FROM dbo.vw_QuestionCountByCompetency) = (SELECT COUNT(*) FROM dbo.Questions)
           THEN '-> vw_QuestionCountByCompetency (indexed) = Questions: KHỚP' ELSE '-> vw_QuestionCountByCompetency (indexed) = Questions: LỆCH' END;
PRINT CASE WHEN (SELECT ISNULL(SUM(Students), 0) FROM dbo.vw_SystemOverview) = (SELECT COUNT(*) FROM dbo.Users u INNER JOIN dbo.Roles r ON r.RoleID = u.RoleID WHERE r.RoleName = 'Student')
           THEN '-> vw_SystemOverview.Students = số user Student: KHỚP' ELSE '-> vw_SystemOverview.Students: LỆCH' END;
PRINT CASE WHEN (SELECT SUM(SubmittedAttempts) FROM dbo.vw_StudentOverview) = (SELECT COUNT(*) FROM dbo.ExamAttempts WHERE SubmittedAt IS NOT NULL)
           THEN '-> Tổng lượt nộp bài trong vw_StudentOverview = ExamAttempts đã nộp: KHỚP' ELSE '-> Tổng lượt nộp bài: LỆCH' END;
GO

-- TEST 5: Xem nhanh kết quả các view / hàm quan trọng
PRINT '';
PRINT '--- TEST 5: Dữ liệu mẫu ---';
SELECT * FROM dbo.vw_StudentOverview ORDER BY StudentID;
SELECT * FROM dbo.vw_AttemptResults ORDER BY AttemptID;
SELECT * FROM dbo.vw_AnswerReview ORDER BY AttemptID, OrderNo;
SELECT * FROM dbo.vw_StudentCompetencyProfile ORDER BY StudentID, WeaknessRank;
SELECT * FROM dbo.vw_CompetencyAccuracy ORDER BY StudentID, CompetencyID;
SELECT * FROM dbo.vw_AnswerHistory ORDER BY StudentID, CompetencyID, SeqNo;
SELECT * FROM dbo.vw_LearningPathProgress;
SELECT * FROM dbo.vw_Recommendations;
SELECT * FROM dbo.vw_RecommendationQuality;
SELECT * FROM dbo.vw_QuestionQuality;
SELECT * FROM dbo.vw_OptionDistribution ORDER BY QuestionID, OptionLabel;
SELECT * FROM dbo.vw_LatestPrediction;
SELECT * FROM dbo.vw_StudyConsistency;
SELECT * FROM dbo.vw_TutorUsage;
SELECT * FROM dbo.vw_StudentAlerts;
SELECT * FROM dbo.vw_AIStudentFeatures;
SELECT * FROM dbo.vw_ExamReadiness;
SELECT * FROM dbo.vw_CompetencyTree ORDER BY SubjectID, SortKey;
SELECT * FROM dbo.vw_UserDirectory ORDER BY UserID;
SELECT * FROM dbo.vw_SystemOverview;

DECLARE @s1 INT = (SELECT UserID FROM dbo.Users WHERE Email = 'student1@gmail.com');
SELECT * FROM dbo.fn_WeakCompetencies(@s1, DEFAULT);
SELECT * FROM dbo.fn_ScoreTrend(@s1);
SELECT * FROM dbo.fn_StudyTimeBetween(@s1, DATEADD(DAY, -7, CAST(SYSDATETIME() AS DATE)), CAST(SYSDATETIME() AS DATE));
DECLARE @algebra INT = (SELECT CompetencyID FROM dbo.Competencies WHERE CompetencyName = N'Đại số');
SELECT * FROM dbo.fn_PracticeCandidates(@s1, @algebra, 1, 5);
GO

-- TEST 6: WITH CHECK OPTION và INSTEAD OF trigger (mọi thay đổi được ROLLBACK)
PRINT '';
PRINT '--- TEST 6: View cập nhật được ---';
DECLARE @stu1 INT = (SELECT UserID FROM dbo.Users WHERE Email = 'student1@gmail.com');

BEGIN TRAN;
BEGIN TRY
    UPDATE dbo.vw_ActiveLearningPaths SET Status = 'DONE' WHERE StudentID = @stu1;
    PRINT '-> THẤT BẠI: WITH CHECK OPTION không chặn việc đổi Status khỏi ACTIVE.';
END TRY
BEGIN CATCH
    PRINT '-> THÀNH CÔNG: WITH CHECK OPTION chặn vw_ActiveLearningPaths: ' + ERROR_MESSAGE();
END CATCH;
IF @@TRANCOUNT > 0 ROLLBACK;

BEGIN TRAN;
BEGIN TRY
    UPDATE dbo.vw_StudentEditableProfile SET TargetScore = 2000 WHERE StudentID = @stu1;
    PRINT '-> THẤT BẠI: cho phép TargetScore = 2000.';
END TRY
BEGIN CATCH
    PRINT '-> THÀNH CÔNG: vw_StudentEditableProfile chặn TargetScore ngoài 0..1200: ' + ERROR_MESSAGE();
END CATCH;
IF @@TRANCOUNT > 0 ROLLBACK;

BEGIN TRAN;
INSERT INTO dbo.Notifications (UserID, StudentID, NotifyType, Message) VALUES (@stu1, @stu1, 'INACTIVITY', N'Thông báo thử nghiệm');
DECLARE @nid BIGINT = SCOPE_IDENTITY();
UPDATE dbo.vw_NotificationInbox SET IsRead = 1 WHERE NotificationID = @nid;
PRINT CASE WHEN (SELECT IsRead FROM dbo.Notifications WHERE NotificationID = @nid) = 1
           THEN '-> THÀNH CÔNG: INSTEAD OF trigger cho phép đánh dấu đã đọc.'
           ELSE '-> THẤT BẠI: không đánh dấu được đã đọc.' END;
BEGIN TRY
    UPDATE dbo.vw_NotificationInbox SET Message = N'sửa trái phép' WHERE NotificationID = @nid;
    PRINT '-> THẤT BẠI: cho phép sửa nội dung thông báo.';
END TRY
BEGIN CATCH
    PRINT '-> THÀNH CÔNG: trigger chặn sửa cột khác IsRead: ' + ERROR_MESSAGE();
END CATCH;
IF @@TRANCOUNT > 0 ROLLBACK;
GO

-- TEST 7: Phân quyền + RLS qua view (chỉ chạy được khi đã có user_student / user_parent / user_teacher)
PRINT '';
PRINT '--- TEST 7: Học sinh / phụ huynh chỉ thấy dữ liệu của mình qua view ---';
IF DATABASE_PRINCIPAL_ID('user_student') IS NULL OR DATABASE_PRINCIPAL_ID('user_parent') IS NULL
    PRINT '   Bỏ qua: chưa có user_student / user_parent (chạy 04_security trước rồi chạy lại 09_view_permissions.sql).';
ELSE
BEGIN
    DECLARE @stu1 INT = (SELECT UserID FROM dbo.Users WHERE Email = 'student1@gmail.com');
    DECLARE @stu2 INT = (SELECT UserID FROM dbo.Users WHERE Email = 'student2@gmail.com');
    DECLARE @par1 INT = (SELECT UserID FROM dbo.Users WHERE Email = 'parent1@gmail.com');

    EXECUTE AS USER = 'user_student';
    EXEC dbo.sp_SetSecurityContext @UserID = @stu1, @RoleName = N'Student';
    SELECT N'student1 xem vw_AttemptResults (mong đợi 1)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_AttemptResults;
    SELECT N'student1 xem vw_StudentOverview (mong đợi 1)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_StudentOverview;
    EXEC dbo.sp_SetSecurityContext @UserID = @stu2, @RoleName = N'Student';
    SELECT N'student2 xem vw_AttemptResults (mong đợi 0)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_AttemptResults;
    SELECT N'student2 xem vw_Recommendations (mong đợi 0)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_Recommendations;
    SELECT N'student2 xem vw_StudentOverview (mong đợi 1 - chính mình)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_StudentOverview;
    REVERT;

    EXECUTE AS USER = 'user_parent';
    EXEC dbo.sp_SetSecurityContext @UserID = @par1, @RoleName = N'Parent';
    SELECT N'parent1 xem vw_ParentDashboard (mong đợi 1 con)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_ParentDashboard;
    SELECT N'parent1 xem vw_StudentAlerts (mong đợi 1 con)' AS Phep_thu, COUNT(*) AS So_dong FROM dbo.vw_StudentAlerts;
    REVERT;

    -- Học sinh / phụ huynh không được xem các view lộ đáp án hoặc quản trị
    DECLARE @blocked TABLE (UserName SYSNAME, ViewName SYSNAME);
    INSERT INTO @blocked VALUES
        ('user_student', 'vw_QuestionBank'), ('user_student', 'vw_QuestionQuality'),
        ('user_student', 'vw_ExamRanking'), ('user_student', 'vw_AIStudentFeatures'),
        ('user_student', 'vw_AuditTrail'), ('user_student', 'vw_SystemSettings'),
        ('user_parent',  'vw_QuestionBank'), ('user_parent',  'vw_UserDirectory');
    DECLARE @u SYSNAME, @bv SYSNAME, @q NVARCHAR(300);
    DECLARE c2 CURSOR LOCAL FAST_FORWARD FOR SELECT UserName, ViewName FROM @blocked;
    OPEN c2; FETCH NEXT FROM c2 INTO @u, @bv;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @q = N'EXECUTE AS USER = ''' + @u + N'''; BEGIN TRY DECLARE @d INT; SELECT TOP 1 @d = 1 FROM dbo.' + QUOTENAME(@bv) +
                 N'; REVERT; PRINT N''-> THẤT BẠI: ' + @u + N' đọc được ' + @bv + N''' ; END TRY BEGIN CATCH REVERT; PRINT N''-> THÀNH CÔNG: ' + @u + N' bị chặn ' + @bv + N''' ; END CATCH;';
        EXEC (@q);
        FETCH NEXT FROM c2 INTO @u, @bv;
    END;
    CLOSE c2; DEALLOCATE c2;
END;
GO

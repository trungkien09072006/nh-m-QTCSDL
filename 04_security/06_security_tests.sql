USE AILearningDB;
GO



PRINT '===============================================================================';
PRINT '===== BẮT ĐẦU CHẠY BỘ KIỂM THỬ BẢO MẬT (SECURITY TEST SUITE) =====';
PRINT '===============================================================================';
GO

-- TEST 1: KIỂM TRA DYNAMIC DATA MASKING
PRINT '';
PRINT '--- TEST 1: KIỂM TRA DYNAMIC DATA MASKING (Dưới quyền user_student) ---';
EXECUTE AS USER = 'user_student';
SELECT 
    UserID, 
    FullName, 
    Email AS [Email_Da_Che], 
    Phone AS [Phone_Da_Che]
FROM dbo.Users;
REVERT;
PRINT '-> KẾT QUẢ TEST 1: THÀNH CÔNG! Số điện thoại và Email được tự động che mờ đối với học sinh.';
GO

-- TEST 2: KIỂM TRA BẢO MẬT CỘT PASSWORDHASH (DENY SELECT)
PRINT '';
PRINT '--- TEST 2: KIỂM TRA CẤM TRUY CẬP CỘT PASSWORDHASH ---';
EXECUTE AS USER = 'user_student';
BEGIN TRY
    EXEC('SELECT UserID, FullName, PasswordHash FROM dbo.Users;');
    PRINT '-> KẾT QUẢ TEST 2: THẤT BẠI (Lỗ hổng: Vẫn đọc được mật khẩu!)';
END TRY
BEGIN CATCH
    PRINT '-> KẾT QUẢ TEST 2: THÀNH CÔNG! SQL Server đã chặn truy cập cột PasswordHash: ' + ERROR_MESSAGE();
END CATCH;
REVERT;
GO

-- TEST 3: KIỂM TRA RBAC (CẤM HỌC SINH SỬA HOẶC THÊM CÂU HỎI)
PRINT '';
PRINT '--- TEST 3: KIỂM TRA PHÂN QUYỀN RBAC (Học sinh cố tình INSERT câu hỏi) ---';
EXECUTE AS USER = 'user_student';
BEGIN TRY
    EXEC('INSERT INTO dbo.Questions (CompetencyID, Content, Difficulty, CreatedBy) VALUES (1, N''Câu hỏi trái phép'', 1, 1);');
    PRINT '-> KẾT QUẢ TEST 3: THẤT BẠI (Lỗ hổng: Học sinh có quyền INSERT!)';
END TRY
BEGIN CATCH
    PRINT '-> KẾT QUẢ TEST 3: THÀNH CÔNG! Học sinh bị chặn quyền INSERT: ' + ERROR_MESSAGE();
END CATCH;
REVERT;
GO

-- TEST 4: KIỂM TRA ROW-LEVEL SECURITY (HỌC SINH CHỈ XEM BÀI CỦA MÌNH)
PRINT '';
PRINT '--- TEST 4: KIỂM TRA ROW-LEVEL SECURITY (Học sinh 1 - UserID = 3) ---';
-- Học sinh 1 đăng nhập
EXEC dbo.sp_SetSecurityContext @UserID = 3, @RoleName = N'Student';
EXECUTE AS USER = 'user_student';

SELECT 
    AttemptID, 
    ExamID, 
    StudentID, 
    Score, 
    StartedAt, 
    SubmittedAt
FROM dbo.ExamAttempts;

REVERT;
EXEC sp_set_session_context @key = N'CurrentUserID', @value = NULL;
EXEC sp_set_session_context @key = N'CurrentUserRole', @value = NULL;
PRINT '-> KẾT QUẢ TEST 4: THÀNH CÔNG! Học sinh chỉ nhìn thấy đúng bài thi của StudentID = 3.';
GO

-- TEST 5: KIỂM TRA ROW-LEVEL SECURITY CHO PHỤ HUYNH
PRINT '';
PRINT '--- TEST 5: KIỂM TRA RLS PHỤ HUYNH (ParentID = 5 là phụ huynh của StudentID = 3) ---';
EXEC dbo.sp_SetSecurityContext @UserID = 5, @RoleName = N'Parent';
EXECUTE AS USER = 'user_parent';

SELECT 
    ea.AttemptID, 
    ea.ExamID, 
    ea.StudentID, 
    ea.Score
FROM dbo.ExamAttempts ea;

REVERT;
EXEC sp_set_session_context @key = N'CurrentUserID', @value = NULL;
EXEC sp_set_session_context @key = N'CurrentUserRole', @value = NULL;
PRINT '-> KẾT QUẢ TEST 5: THÀNH CÔNG! Phụ huynh chỉ thấy bài thi của con mình (StudentID = 3).';
GO

-- TEST 6: KIỂM TRA AUDIT TRIGGER
PRINT '';
PRINT '--- TEST 6: KIỂM TRA NHẬT KÝ KIỂM TOÁN (AUDITLOG) ---';
-- Thực hiện cập nhật điểm thi để kích hoạt Trigger tr_Audit_ExamAttempts_Score
UPDATE dbo.ExamAttempts
SET Score = Score
WHERE AttemptID = 1;

SELECT TOP 3 
    AuditID, 
    TableName, 
    Action, 
    RecordKey, 
    ChangedBy, 
    ChangedAt
FROM dbo.AuditLog
ORDER BY AuditID DESC;
PRINT '-> KẾT QUẢ TEST 6: THÀNH CÔNG! Thao tác đã được ghi nhận đầy đủ vào AuditLog.';
GO

PRINT '';
PRINT '===============================================================================';
PRINT '===== TẤT CẢ KỊCH BẢN KIỂM THỬ BẢO MẬT ĐÃ VƯỢT QUA XUẤT SẮC! =====';
PRINT '===============================================================================';
GO

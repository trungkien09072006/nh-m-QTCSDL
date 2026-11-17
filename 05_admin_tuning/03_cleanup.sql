USE AILearningDB;
GO

PRINT '>>> [03_cleanup.sql] Đang tạo thủ tục dọn dẹp dữ liệu cũ...';
GO

-- Xóa nhật ký hệ thống và thông báo cũ (Mặc định giữ lại 180 ngày)
CREATE OR ALTER PROCEDURE dbo.sp_Admin_CleanupOldData
    @RetentionDays INT = 180
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @CutoffDate DATETIME2 = DATEADD(DAY, -@RetentionDays, SYSDATETIME());
    DECLARE @DeletedAudit INT, @DeletedNotif INT;

    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.AuditLog 
        WHERE ChangedAt < @CutoffDate;
        SET @DeletedAudit = @@ROWCOUNT;

        DELETE FROM dbo.Notifications 
        WHERE CreatedAt < @CutoffDate AND IsRead = 1;
        SET @DeletedNotif = @@ROWCOUNT;

        COMMIT TRANSACTION;
        PRINT CONCAT('>>> Đã dọn dẹp thành công: ', @DeletedAudit, ' dòng AuditLog, ', @DeletedNotif, ' dòng Notifications.');
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        PRINT 'Lỗi khi dọn dẹp dữ liệu: ' + ERROR_MESSAGE();
        THROW;
    END CATCH;
END;
GO
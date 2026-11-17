USE AILearningDB;
GO


PRINT '>>> [05_audit_triggers.sql] Đang tạo các Trigger kiểm toán an ninh...';
GO

-- 1. TRIGGER KIỂM TOÁN BẢNG USERS
CREATE OR ALTER TRIGGER dbo.tr_Audit_Users
ON dbo.Users
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Thao tác UPDATE
    IF EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'Users', 
            'UPDATE', 
            CONCAT('UserID=', i.UserID, '; Email=', i.Email, 
                   CASE WHEN i.IsActive <> d.IsActive THEN CONCAT('; IsActiveChangedTo=', i.IsActive) ELSE '' END,
                   CASE WHEN i.RoleID <> d.RoleID THEN CONCAT('; RoleChangedTo=', i.RoleID) ELSE '' END),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM inserted i
        INNER JOIN deleted d ON d.UserID = i.UserID;
    END
    -- Thao tác INSERT
    ELSE IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'Users', 
            'INSERT', 
            CONCAT('UserID=', i.UserID, '; Email=', i.Email, '; RoleID=', i.RoleID),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM inserted i;
    END
    -- Thao tác DELETE
    ELSE IF EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'Users', 
            'DELETE', 
            CONCAT('UserID=', d.UserID, '; Email=', d.Email),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM deleted d;
    END
END;
GO
PRINT '    + Đã tạo Trigger: tr_Audit_Users';

-- 2. TRIGGER KIỂM TOÁN BẢNG SYSTEMSETTINGS
CREATE OR ALTER TRIGGER dbo.tr_Audit_SystemSettings
ON dbo.SystemSettings
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    
    IF EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'SystemSettings', 
            'UPDATE', 
            CONCAT('Key=', i.SettingKey, '; OldVal=', d.SettingValue, '; NewVal=', i.SettingValue),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM inserted i
        INNER JOIN deleted d ON d.SettingKey = i.SettingKey;
    END
    ELSE IF EXISTS (SELECT 1 FROM inserted)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'SystemSettings', 
            'INSERT', 
            CONCAT('Key=', i.SettingKey, '; Val=', i.SettingValue),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM inserted i;
    END
    ELSE IF EXISTS (SELECT 1 FROM deleted)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'SystemSettings', 
            'DELETE', 
            CONCAT('Key=', d.SettingKey),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM deleted d;
    END
END;
GO
PRINT '    + Đã tạo Trigger: tr_Audit_SystemSettings';

-- 3. TRIGGER KIỂM TOÁN THAY ĐỔI ĐIỂM THI TRONG EXAMATTEMPTS
CREATE OR ALTER TRIGGER dbo.tr_Audit_ExamAttempts_Score
ON dbo.ExamAttempts
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    
    IF UPDATE(Score)
    BEGIN
        INSERT INTO dbo.AuditLog (TableName, Action, RecordKey, ChangedBy, ChangedAt)
        SELECT 
            'ExamAttempts', 
            'UPDATE', 
            CONCAT('AttemptID=', i.AttemptID, '; StudentID=', i.StudentID, 
                   '; OldScore=', ISNULL(CAST(d.Score AS NVARCHAR(20)), N'NULL'), 
                   '; NewScore=', ISNULL(CAST(i.Score AS NVARCHAR(20)), N'NULL')),
            SUSER_SNAME(), 
            SYSDATETIME()
        FROM inserted i
        INNER JOIN deleted d ON d.AttemptID = i.AttemptID
        WHERE ISNULL(i.Score, -1) <> ISNULL(d.Score, -1);
    END
END;
GO
PRINT '    + Đã tạo Trigger: tr_Audit_ExamAttempts_Score';
PRINT '    + Đã hoàn thành cấu hình các Trigger kiểm toán.';
GO

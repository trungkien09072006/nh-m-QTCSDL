USE AILearningDB;
GO



PRINT '>>> [03_dynamic_data_masking.sql] Đang cấu hình Dynamic Data Masking...';
GO

-- 1. Che giấu số điện thoại người dùng
IF EXISTS (
    SELECT 1 FROM sys.masked_columns 
    WHERE object_id = OBJECT_ID('dbo.Users') AND name = 'Phone'
)
BEGIN
    ALTER TABLE dbo.Users ALTER COLUMN Phone DROP MASKED;
END;

ALTER TABLE dbo.Users ALTER COLUMN Phone ADD MASKED WITH (FUNCTION = 'partial(3, "XXXXXX", 2)');
PRINT '    + Đã áp dụng Masking cho Users.Phone: partial(3, "XXXXXX", 2)';

-- 2. Che giấu email người dùng
IF EXISTS (
    SELECT 1 FROM sys.masked_columns 
    WHERE object_id = OBJECT_ID('dbo.Users') AND name = 'Email'
)
BEGIN
    ALTER TABLE dbo.Users ALTER COLUMN Email DROP MASKED;
END;

ALTER TABLE dbo.Users ALTER COLUMN Email ADD MASKED WITH (FUNCTION = 'email()');
PRINT '    + Đã áp dụng Masking cho Users.Email: email()';

-- 3. Cấp quyền UNMASK (Xem dữ liệu nguyên bản)
GRANT UNMASK TO Role_Admin;
GRANT UNMASK TO Role_App;

PRINT '    + Đã hoàn thành cấu hình Dynamic Data Masking.';
GO

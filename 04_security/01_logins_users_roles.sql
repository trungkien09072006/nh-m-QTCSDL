USE AILearningDB;
GO

/*
===============================================================================
PHÂN HỆ 04 - BÀI TOÁN BẢO MẬT: PHẦN 1
CẤU HÌNH SERVER LOGINS, DATABASE USERS VÀ DATABASE ROLES (RBAC)
===============================================================================
*/

PRINT '>>> [01_logins_users_roles.sql] Đang khởi tạo Logins, Users và Roles...';
GO

-- 1. TẠO SERVER LOGINS (Dành cho SQL Server Authentication)
-- Sử dụng TRY-CATCH để an toàn khi chạy với tài khoản không có quyền sysadmin
IF NOT EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_admin')
BEGIN
    BEGIN TRY
        EXEC('CREATE LOGIN novapath_admin WITH PASSWORD = N''Admin@NovaPath2025!'', CHECK_POLICY = OFF;');
        PRINT '    + Đã tạo Server Login: novapath_admin';
    END TRY
    BEGIN CATCH
        PRINT '    ! Bỏ qua tạo Server Login novapath_admin (không đủ quyền sysadmin).';
    END CATCH
END;

IF NOT EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_teacher')
BEGIN
    BEGIN TRY
        EXEC('CREATE LOGIN novapath_teacher WITH PASSWORD = N''Teacher@NovaPath2025!'', CHECK_POLICY = OFF;');
        PRINT '    + Đã tạo Server Login: novapath_teacher';
    END TRY
    BEGIN CATCH
        PRINT '    ! Bỏ qua tạo Server Login novapath_teacher (không đủ quyền sysadmin).';
    END CATCH
END;

IF NOT EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_student')
BEGIN
    BEGIN TRY
        EXEC('CREATE LOGIN novapath_student WITH PASSWORD = N''Student@NovaPath2025!'', CHECK_POLICY = OFF;');
        PRINT '    + Đã tạo Server Login: novapath_student';
    END TRY
    BEGIN CATCH
        PRINT '    ! Bỏ qua tạo Server Login novapath_student (không đủ quyền sysadmin).';
    END CATCH
END;

IF NOT EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_parent')
BEGIN
    BEGIN TRY
        EXEC('CREATE LOGIN novapath_parent WITH PASSWORD = N''Parent@NovaPath2025!'', CHECK_POLICY = OFF;');
        PRINT '    + Đã tạo Server Login: novapath_parent';
    END TRY
    BEGIN CATCH
        PRINT '    ! Bỏ qua tạo Server Login novapath_parent (không đủ quyền sysadmin).';
    END CATCH
END;

IF NOT EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_app')
BEGIN
    BEGIN TRY
        EXEC('CREATE LOGIN novapath_app WITH PASSWORD = N''App@NovaPath2025!'', CHECK_POLICY = OFF;');
        PRINT '    + Đã tạo Server Login: novapath_app';
    END TRY
    BEGIN CATCH
        PRINT '    ! Bỏ qua tạo Server Login novapath_app (không đủ quyền sysadmin).';
    END CATCH
END;
GO

-- 2. TẠO DATABASE USERS TRONG AILearningDB
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'user_admin')
BEGIN
    IF EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_admin')
        CREATE USER user_admin FOR LOGIN novapath_admin;
    ELSE
        CREATE USER user_admin WITHOUT LOGIN;
    PRINT '    + Đã tạo Database User: user_admin';
END;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'user_teacher')
BEGIN
    IF EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_teacher')
        CREATE USER user_teacher FOR LOGIN novapath_teacher;
    ELSE
        CREATE USER user_teacher WITHOUT LOGIN;
    PRINT '    + Đã tạo Database User: user_teacher';
END;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'user_student')
BEGIN
    IF EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_student')
        CREATE USER user_student FOR LOGIN novapath_student;
    ELSE
        CREATE USER user_student WITHOUT LOGIN;
    PRINT '    + Đã tạo Database User: user_student';
END;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'user_parent')
BEGIN
    IF EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_parent')
        CREATE USER user_parent FOR LOGIN novapath_parent;
    ELSE
        CREATE USER user_parent WITHOUT LOGIN;
    PRINT '    + Đã tạo Database User: user_parent';
END;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'user_app')
BEGIN
    IF EXISTS (SELECT 1 FROM sys.server_logins WHERE name = 'novapath_app')
        CREATE USER user_app FOR LOGIN novapath_app;
    ELSE
        CREATE USER user_app WITHOUT LOGIN;
    PRINT '    + Đã tạo Database User: user_app';
END;
GO

-- 3. TẠO DATABASE ROLES (RBAC)
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'Role_Admin' AND type = 'R')
    CREATE ROLE Role_Admin;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'Role_Teacher' AND type = 'R')
    CREATE ROLE Role_Teacher;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'Role_Student' AND type = 'R')
    CREATE ROLE Role_Student;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'Role_Parent' AND type = 'R')
    CREATE ROLE Role_Parent;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'Role_App' AND type = 'R')
    CREATE ROLE Role_App;
GO

-- 4. GÁN USER VÀO ROLE TƯƠNG ỨNG
ALTER ROLE Role_Admin ADD MEMBER user_admin;
ALTER ROLE Role_Teacher ADD MEMBER user_teacher;
ALTER ROLE Role_Student ADD MEMBER user_student;
ALTER ROLE Role_Parent ADD MEMBER user_parent;
ALTER ROLE Role_App ADD MEMBER user_app;
PRINT '    + Đã hoàn thành cấu hình Logins, Users và Role Mapping.';
GO

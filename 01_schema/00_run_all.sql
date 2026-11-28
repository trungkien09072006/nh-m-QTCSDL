:setvar Root "C:\Users\kinhk\Hệ_QTCSDL\nh-m-QTCSDL"

:on error exit

PRINT '===== BẮT ĐẦU CHẠY SCHEMA ====='
:r $(Root)\01_schema\01_create_database.sql
:r $(Root)\01_schema\02_create_tables.sql

/* BEGIN ParentLinkRequests migration. For existing databases, run this block only. */
USE AILearningDB;
GO

IF OBJECT_ID(N'dbo.ParentLinkRequests', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ParentLinkRequests (
        RequestID INT IDENTITY PRIMARY KEY,
        ParentID INT NOT NULL REFERENCES dbo.Users(UserID),
        StudentID INT NOT NULL REFERENCES dbo.StudentProfiles(StudentID),
        Status VARCHAR(10) NOT NULL CONSTRAINT DF_ParentLinkRequests_Status DEFAULT 'Pending',
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_ParentLinkRequests_CreatedAt DEFAULT SYSDATETIME(),
        ResolvedAt DATETIME2 NULL,
        CONSTRAINT CK_ParentLinkRequests_Status CHECK (Status IN ('Pending', 'Accepted', 'Rejected'))
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.ParentLinkRequests')
      AND name = N'UX_ParentLinkRequests_Pending'
)
    CREATE UNIQUE INDEX UX_ParentLinkRequests_Pending
        ON dbo.ParentLinkRequests (ParentID, StudentID)
        WHERE Status = 'Pending';
GO
/* END ParentLinkRequests migration. */

:r $(Root)\01_schema\03_seed_roles.sql
:r $(Root)\01_schema\04_seed_data.sql
:r $(Root)\01_schema\06_teacher_student_migration.sql
:r $(Root)\01_schema\05_seed_diagnostic_exam.sql
:r $(Root)\03_programmability\02_stored_procedures.sql
:r $(Root)\03_programmability\03_content_rules.sql

PRINT '===== CHẠY SCHEMA THÀNH CÔNG ====='

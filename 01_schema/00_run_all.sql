:setvar Root "C:\Users\kinhk\Hệ_QTCSDL\nh-m-QTCSDL"

:on error exit

PRINT '===== BẮT ĐẦU CHẠY SCHEMA ====='
:r $(Root)\01_schema\01_create_database.sql
:r $(Root)\01_schema\02_create_tables.sql
:r $(Root)\01_schema\03_seed_roles.sql
:r $(Root)\01_schema\04_seed_data.sql
:r $(Root)\01_schema\05_seed_diagnostic_exam.sql
:r $(Root)\03_programmability\02_stored_procedures.sql
:r $(Root)\03_programmability\03_content_rules.sql

PRINT '===== CHẠY SCHEMA THÀNH CÔNG ====='

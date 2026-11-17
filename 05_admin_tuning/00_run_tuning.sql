:on error exit

PRINT '===== BẮT ĐẦU CHẠY PHÂN HỆ TUNING ====='
:r $(Root)\05_admin_tuning\01_indexes.sql
:r $(Root)\05_admin_tuning\02_maintenance.sql
:r $(Root)\05_admin_tuning\03_cleanup.sql
PRINT '===== CHẠY PHÂN HỆ TUNING THÀNH CÔNG ====='
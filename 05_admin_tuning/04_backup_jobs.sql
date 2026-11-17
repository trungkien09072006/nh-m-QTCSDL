USE AILearningDB;
GO

PRINT '>>> [04_backup_jobs.sql] Các lệnh mẫu để cấu hình Backup Jobs...';
GO

/* 
====================================================================
KỊCH BẢN SAO LƯU (BACKUP SCRIPTS)
Đưa các lệnh này vào SQL Server Agent Jobs để chạy theo lịch tự động
====================================================================
*/

/* 1. Full Backup (Sao lưu toàn bộ - Chạy Chủ Nhật hàng tuần) */
/*
BACKUP DATABASE AILearningDB 
TO DISK = 'C:\Backups\AILearningDB_Full.bak' 
WITH FORMAT, INIT, COMPRESSION, 
NAME = 'AILearningDB-Full Database Backup', STATS = 10;
*/

/* 2. Differential Backup (Sao lưu khác biệt - Chạy mỗi đêm T2 - T7) */
/*
BACKUP DATABASE AILearningDB 
TO DISK = 'C:\Backups\AILearningDB_Diff.bak' 
WITH DIFFERENTIAL, COMPRESSION, 
NAME = 'AILearningDB-Differential Database Backup', STATS = 10;
*/

/* 3. Transaction Log Backup (Sao lưu nhật ký giao dịch - Chạy mỗi giờ) */
/*
BACKUP LOG AILearningDB 
TO DISK = 'C:\Backups\AILearningDB_Log.trn' 
WITH COMPRESSION, 
NAME = 'AILearningDB-Transaction Log Backup', STATS = 10;
*/
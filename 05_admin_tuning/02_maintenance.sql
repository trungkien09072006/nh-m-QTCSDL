USE AILearningDB;
GO

PRINT '>>> [02_maintenance.sql] Đang tạo các thủ tục bảo trì hệ thống...';
GO

-- 1. Cập nhật Thống kê (Update Statistics)
CREATE OR ALTER PROCEDURE dbo.sp_Admin_UpdateStatistics
AS
BEGIN
    SET NOCOUNT ON;
    PRINT '>>> Đang cập nhật Statistics cho toàn bộ cơ sở dữ liệu...';
    EXEC sp_updatestats;
    PRINT '>>> Cập nhật Statistics hoàn tất.';
END;
GO

-- 2. Tái thiết lập Chỉ mục (Defragment Indexes)
CREATE OR ALTER PROCEDURE dbo.sp_Admin_DefragmentIndexes
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @TableName VARCHAR(255);
    DECLARE @IndexName VARCHAR(255);
    DECLARE @Fragmentation FLOAT;
    DECLARE @SQL NVARCHAR(MAX);

    DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT 
            OBJECT_NAME(ips.OBJECT_ID) AS TableName,
            i.name AS IndexName,
            ips.avg_fragmentation_in_percent
        FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') ips
        JOIN sys.indexes i ON ips.object_id = i.object_id AND ips.index_id = i.index_id
        WHERE ips.avg_fragmentation_in_percent > 10.0 AND i.name IS NOT NULL;

    OPEN cur;
    FETCH NEXT FROM cur INTO @TableName, @IndexName, @Fragmentation;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF @Fragmentation >= 30.0
            SET @SQL = 'ALTER INDEX ' + @IndexName + ' ON ' + @TableName + ' REBUILD;';
        ELSE
            SET @SQL = 'ALTER INDEX ' + @IndexName + ' ON ' + @TableName + ' REORGANIZE;';
            
        PRINT 'Thực thi: ' + @SQL + ' (Phân mảnh: ' + CAST(ROUND(@Fragmentation, 2) AS VARCHAR) + '%)';
        EXEC sp_executesql @SQL;
        
        FETCH NEXT FROM cur INTO @TableName, @IndexName, @Fragmentation;
    END;

    CLOSE cur;
    DEALLOCATE cur;
END;
GO
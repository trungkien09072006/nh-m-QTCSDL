USE AILearningDB;
GO
-- Chạy sau schema hiện có; có thể chạy lại, không xóa dữ liệu.
CREATE OR ALTER TRIGGER dbo.tr_Content_ExamQuestions
ON dbo.ExamQuestions AFTER INSERT, UPDATE, DELETE
AS
BEGIN
 SET NOCOUNT ON;
 IF EXISTS(SELECT 1 FROM inserted i JOIN dbo.Questions q WITH (UPDLOCK,HOLDLOCK) ON q.QuestionID=i.QuestionID WHERE q.IsApproved=0)
  THROW 51001, N'Chỉ câu hỏi đã duyệt mới được đưa vào đề.', 1;
 IF EXISTS(SELECT 1 FROM (SELECT ExamID FROM inserted UNION SELECT ExamID FROM deleted) x JOIN dbo.ExamAttempts a ON a.ExamID=x.ExamID)
  THROW 51002, N'Không được thay đổi cấu trúc đề đã có lượt làm.', 1;
 IF EXISTS(SELECT 1 FROM inserted WHERE OrderNo<=0)
  THROW 51003, N'Thứ tự câu hỏi phải dương.', 1;
END;
GO
CREATE OR ALTER TRIGGER dbo.tr_Content_QuestionApproval
ON dbo.Questions AFTER INSERT, UPDATE
AS
BEGIN
 SET NOCOUNT ON;
 IF EXISTS(SELECT 1 FROM inserted i WHERE i.IsApproved=1 AND
 ((SELECT COUNT(*) FROM dbo.QuestionOptions o WHERE o.QuestionID=i.QuestionID)<2 OR
 (SELECT COUNT(*) FROM dbo.QuestionOptions o WHERE o.QuestionID=i.QuestionID AND o.IsCorrect=1)<>1))
  THROW 51004, N'Câu được duyệt phải có ít nhất hai đáp án và đúng một đáp án đúng.', 1;
 IF EXISTS(SELECT 1 FROM inserted i JOIN deleted d ON d.QuestionID=i.QuestionID JOIN dbo.ExamQuestions e ON e.QuestionID=i.QuestionID
 WHERE i.Content<>d.Content OR i.CompetencyID<>d.CompetencyID OR i.Difficulty<>d.Difficulty
 OR ISNULL(i.Explanation,N'')<>ISNULL(d.Explanation,N'') OR i.IsApproved<>d.IsApproved)
  THROW 51005, N'Không được thay đổi câu hỏi đã có trong đề.', 1;
 IF EXISTS(SELECT 1 FROM inserted i JOIN deleted d ON d.QuestionID=i.QuestionID WHERE i.IsApproved=1 AND
 (i.Content<>d.Content OR i.CompetencyID<>d.CompetencyID OR i.Difficulty<>d.Difficulty OR ISNULL(i.Explanation,N'')<>ISNULL(d.Explanation,N'')))
  THROW 51006, N'Sửa câu hỏi phải chuyển về trạng thái chưa duyệt.', 1;
END;
GO
CREATE OR ALTER TRIGGER dbo.tr_Content_Options
ON dbo.QuestionOptions AFTER INSERT, UPDATE, DELETE
AS
BEGIN
 SET NOCOUNT ON;
 IF EXISTS(SELECT 1 FROM (SELECT QuestionID FROM inserted UNION SELECT QuestionID FROM deleted) x JOIN dbo.Questions q ON q.QuestionID=x.QuestionID WHERE q.IsApproved=1)
  THROW 51007, N'Phải chuyển câu hỏi về chưa duyệt trước khi sửa đáp án.', 1;
END;
GO
CREATE OR ALTER TRIGGER dbo.tr_Content_CompetencyParent
ON dbo.Competencies AFTER INSERT, UPDATE
AS
BEGIN
 SET NOCOUNT ON;
 IF EXISTS(SELECT 1 FROM dbo.Competencies c JOIN dbo.Competencies p ON p.CompetencyID=c.ParentCompID WHERE c.SubjectID<>p.SubjectID)
  THROW 51008, N'Năng lực cha và con phải cùng môn học.', 1;
 DECLARE @cycle BIT=0;
 ;WITH chain AS (
  SELECT CompetencyID AS StartID,CompetencyID,ParentCompID,
   CAST('/'+CAST(CompetencyID AS VARCHAR(12))+'/' AS VARCHAR(MAX)) AS Visited,0 AS IsCycle
  FROM inserted
  UNION ALL
  SELECT c.StartID,p.CompetencyID,p.ParentCompID,
   CAST(c.Visited+CAST(p.CompetencyID AS VARCHAR(12))+'/' AS VARCHAR(MAX)),
   CASE WHEN CHARINDEX('/'+CAST(p.CompetencyID AS VARCHAR(12))+'/',c.Visited)>0 THEN 1 ELSE 0 END
  FROM chain c JOIN dbo.Competencies p ON p.CompetencyID=c.ParentCompID WHERE c.IsCycle=0
 )
 SELECT TOP 1 @cycle=1 FROM chain WHERE IsCycle=1 OPTION(MAXRECURSION 32767);
 IF @cycle=1 THROW 51009, N'Cây năng lực không được có vòng lặp.', 1;
END;
GO

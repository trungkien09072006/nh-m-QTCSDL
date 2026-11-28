USE AILearningDB;
GO

IF OBJECT_ID(N'dbo.TeacherStudent', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TeacherStudent (
        TeacherID INT NOT NULL REFERENCES dbo.Users(UserID),
        StudentID INT NOT NULL REFERENCES dbo.StudentProfiles(StudentID),
        AssignedAt DATETIME2 NOT NULL CONSTRAINT DF_TeacherStudent_AssignedAt DEFAULT SYSDATETIME(),
        CONSTRAINT PK_TeacherStudent PRIMARY KEY (TeacherID, StudentID)
    );
END;
GO

INSERT INTO dbo.TeacherStudent (TeacherID, StudentID)
SELECT teacher.UserID, student.UserID
FROM dbo.Users AS teacher
INNER JOIN dbo.Roles AS teacher_role ON teacher_role.RoleID = teacher.RoleID
INNER JOIN dbo.Users AS student ON student.Email = 'student1@gmail.com'
INNER JOIN dbo.Roles AS student_role ON student_role.RoleID = student.RoleID
INNER JOIN dbo.StudentProfiles AS profile ON profile.StudentID = student.UserID
WHERE teacher.Email = 'teacher@ai-edu.vn'
  AND teacher_role.RoleName = N'Teacher'
  AND student_role.RoleName = N'Student'
  AND NOT EXISTS (
      SELECT 1 FROM dbo.TeacherStudent AS assigned
      WHERE assigned.TeacherID = teacher.UserID AND assigned.StudentID = student.UserID
  );
GO

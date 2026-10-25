/*2*/
CREATE TABLE Subjects (
    SubjectID   INT IDENTITY(1,1) PRIMARY KEY,
    SubjectName NVARCHAR(100) NOT NULL UNIQUE,
    Description NVARCHAR(500) NULL
);
CREATE TABLE Competencies (
    CompetencyID   INT IDENTITY(1,1) PRIMARY KEY,
    SubjectID      INT NOT NULL FOREIGN KEY REFERENCES Subjects(SubjectID),
    CompetencyName NVARCHAR(150) NOT NULL,
    ParentCompID   INT NULL FOREIGN KEY REFERENCES Competencies(CompetencyID),
    UNIQUE (SubjectID, CompetencyName)
);
CREATE TABLE LearningResources (
    ResourceID   INT IDENTITY(1,1) PRIMARY KEY,
    CompetencyID INT NOT NULL FOREIGN KEY REFERENCES Competencies(CompetencyID),
    Title        NVARCHAR(200) NOT NULL,
    ResourceType VARCHAR(20) NOT NULL CHECK (ResourceType IN ('VIDEO','ARTICLE','SLIDE','EXERCISE')),
    Url          NVARCHAR(500) NULL,
    EstimatedMin INT NOT NULL DEFAULT 15 CHECK (EstimatedMin > 0),
    CreatedBy    INT NOT NULL FOREIGN KEY REFERENCES Users(UserID)
);
/*7*/
CREATE INDEX IX_ExamAttempts_Student_Time 
ON ExamAttempts (StudentID, StartedAt DESC);
GO

CREATE INDEX IX_Questions_Competency_Difficulty 
ON Questions (CompetencyID, Difficulty);
GO

CREATE INDEX IX_LearningPathItems_Schedule 
ON LearningPathItems (PathID, ScheduledDate);
GO

CREATE INDEX IX_TutorMessages_ChatHistory 
ON TutorMessages (SessionID, SentAt ASC);
GO
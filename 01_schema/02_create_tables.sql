USE AILearningDB;
GO

/* ===== 1. NGƯỜI DÙNG ===== */
CREATE TABLE Roles (
    RoleID   INT IDENTITY PRIMARY KEY,
    RoleName NVARCHAR(50) NOT NULL UNIQUE  
);

CREATE TABLE Users (
    UserID       INT IDENTITY PRIMARY KEY,
    RoleID       INT NOT NULL REFERENCES Roles(RoleID),
    Email        NVARCHAR(150) NOT NULL UNIQUE,
    PasswordHash VARBINARY(256) NOT NULL,
    FullName     NVARCHAR(100) NOT NULL,
    Phone        VARCHAR(15) NULL,
    IsActive     BIT NOT NULL DEFAULT 1,
    CreatedAt    DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE StudentProfiles (
    StudentID     INT PRIMARY KEY REFERENCES Users(UserID),
    SchoolName    NVARCHAR(150) NULL,
    TargetScore   INT NOT NULL CHECK (TargetScore BETWEEN 0 AND 1200),
    ExamDate      DATE NULL,
    DailyStudyMin INT NOT NULL DEFAULT 60 CHECK (DailyStudyMin > 0)
);

CREATE TABLE ParentStudent (
    ParentID  INT NOT NULL REFERENCES Users(UserID),
    StudentID INT NOT NULL REFERENCES StudentProfiles(StudentID),
    PRIMARY KEY (ParentID, StudentID)
);

/* ===== 2. NỘI DUNG HỌC ===== */
CREATE TABLE Subjects (
    SubjectID   INT IDENTITY PRIMARY KEY,
    SubjectName NVARCHAR(100) NOT NULL UNIQUE,
    Description NVARCHAR(500) NULL
);

CREATE TABLE Competencies (
    CompetencyID   INT IDENTITY PRIMARY KEY,
    SubjectID      INT NOT NULL REFERENCES Subjects(SubjectID),
    CompetencyName NVARCHAR(150) NOT NULL,
    ParentCompID   INT NULL REFERENCES Competencies(CompetencyID),
    UNIQUE (SubjectID, CompetencyName),
    CHECK (ParentCompID IS NULL OR ParentCompID <> CompetencyID)
);

CREATE TABLE LearningResources (
    ResourceID   INT IDENTITY PRIMARY KEY,
    CompetencyID INT NOT NULL REFERENCES Competencies(CompetencyID),
    Title        NVARCHAR(200) NOT NULL,
    ResourceType VARCHAR(20) NOT NULL CHECK (ResourceType IN ('VIDEO','ARTICLE','SLIDE','EXERCISE')),
    Url          NVARCHAR(500) NULL,
    EstimatedMin INT NOT NULL DEFAULT 15 CHECK (EstimatedMin > 0),
    CreatedBy    INT NOT NULL REFERENCES Users(UserID),
    CONSTRAINT UQ_LearningResources_Resource_Competency UNIQUE (ResourceID, CompetencyID)
);

CREATE TABLE Questions (
    QuestionID    INT IDENTITY PRIMARY KEY,
    CompetencyID  INT NOT NULL REFERENCES Competencies(CompetencyID),
    Content       NVARCHAR(MAX) NOT NULL,
    Difficulty    TINYINT NOT NULL CHECK (Difficulty BETWEEN 1 AND 5),
    Explanation   NVARCHAR(MAX) NULL,
    IsAIGenerated BIT NOT NULL DEFAULT 0,
    IsApproved    BIT NOT NULL DEFAULT 0,
    CreatedBy     INT NOT NULL REFERENCES Users(UserID),
    CreatedAt     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE QuestionOptions (
    OptionID    INT IDENTITY PRIMARY KEY,
    QuestionID  INT NOT NULL REFERENCES Questions(QuestionID) ON DELETE CASCADE,
    OptionLabel CHAR(1) NOT NULL,
    OptionText  NVARCHAR(1000) NOT NULL,
    IsCorrect   BIT NOT NULL DEFAULT 0,
    UNIQUE (QuestionID, OptionLabel),
    CONSTRAINT UQ_QuestionOptions_Option_Question UNIQUE (OptionID, QuestionID) 
);

CREATE UNIQUE NONCLUSTERED INDEX UX_QuestionOptions_OneCorrect
    ON QuestionOptions(QuestionID)
    WHERE IsCorrect = 1;

CREATE TABLE Exams (
    ExamID      INT IDENTITY PRIMARY KEY,
    Title       NVARCHAR(200) NOT NULL,
    ExamType    VARCHAR(15) NOT NULL CHECK (ExamType IN ('DIAGNOSTIC','MOCK','QUIZ')),
    DurationMin INT NOT NULL CHECK (DurationMin > 0),
    CreatedBy   INT NOT NULL REFERENCES Users(UserID),
    CreatedAt   DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE ExamQuestions (
    ExamID     INT NOT NULL REFERENCES Exams(ExamID) ON DELETE CASCADE,
    QuestionID INT NOT NULL REFERENCES Questions(QuestionID),
    OrderNo    INT NOT NULL,
    PRIMARY KEY (ExamID, QuestionID),
    UNIQUE (ExamID, OrderNo)
);

/* ===== 3. LÀM BÀI ===== */
CREATE TABLE ExamAttempts (
    AttemptID   INT IDENTITY PRIMARY KEY,
    ExamID      INT NOT NULL REFERENCES Exams(ExamID),
    StudentID   INT NOT NULL REFERENCES StudentProfiles(StudentID),
    StartedAt   DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    SubmittedAt DATETIME2 NULL,
    Score       DECIMAL(6,2) NULL,
    CHECK (SubmittedAt IS NULL OR SubmittedAt >= StartedAt)
);

CREATE TABLE AttemptAnswers (
    AttemptID      INT NOT NULL REFERENCES ExamAttempts(AttemptID) ON DELETE CASCADE,
    QuestionID     INT NOT NULL REFERENCES Questions(QuestionID),
    SelectedOption INT NULL,
    IsCorrect      BIT NULL,
    TimeSpentSec   INT NULL CHECK (TimeSpentSec >= 0),
    PRIMARY KEY (AttemptID, QuestionID),
    CONSTRAINT FK_AttemptAnswers_Option_Question
        FOREIGN KEY (SelectedOption, QuestionID)
        REFERENCES QuestionOptions(OptionID, QuestionID)
);

/* ===== 4. CÁ NHÂN HÓA ===== */
CREATE TABLE StudentCompetency (       -- Learning Profile
    StudentID    INT NOT NULL REFERENCES StudentProfiles(StudentID),
    CompetencyID INT NOT NULL REFERENCES Competencies(CompetencyID),
    Mastery      DECIMAL(5,4) NOT NULL DEFAULT 0.5 CHECK (Mastery BETWEEN 0 AND 1),
    AttemptCount INT NOT NULL DEFAULT 0,
    UpdatedAt    DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    PRIMARY KEY (StudentID, CompetencyID)
);

CREATE TABLE LearningPaths (
    PathID      INT IDENTITY PRIMARY KEY,
    StudentID   INT NOT NULL REFERENCES StudentProfiles(StudentID),
    StartDate   DATE NOT NULL,
    EndDate     DATE NOT NULL,
    Status      VARCHAR(10) NOT NULL DEFAULT 'ACTIVE' CHECK (Status IN ('ACTIVE','DONE','REPLACED')),
    GeneratedAt DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    CHECK (EndDate >= StartDate)
);

CREATE TABLE LearningPathItems (
    ItemID        INT IDENTITY PRIMARY KEY,
    PathID        INT NOT NULL REFERENCES LearningPaths(PathID) ON DELETE CASCADE,
    CompetencyID  INT NOT NULL REFERENCES Competencies(CompetencyID),
    ResourceID    INT NULL,
    ScheduledDate DATE NOT NULL,
    Priority      TINYINT NOT NULL DEFAULT 3 CHECK (Priority BETWEEN 1 AND 5),
    Status        VARCHAR(10) NOT NULL DEFAULT 'TODO' CHECK (Status IN ('TODO','DOING','DONE','SKIPPED')),
    CONSTRAINT FK_LearningPathItems_ResourceCompetency
        FOREIGN KEY (ResourceID, CompetencyID)
        REFERENCES LearningResources(ResourceID, CompetencyID)
);

CREATE TABLE Recommendations (
    RecID      INT IDENTITY PRIMARY KEY,
    StudentID  INT NOT NULL REFERENCES StudentProfiles(StudentID),
    QuestionID INT NULL REFERENCES Questions(QuestionID),
    ResourceID INT NULL REFERENCES LearningResources(ResourceID),
    Reason     NVARCHAR(300) NULL,
    CreatedAt  DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    IsAccepted BIT NULL,
    CHECK (QuestionID IS NOT NULL OR ResourceID IS NOT NULL)
);

CREATE TABLE ScorePredictions (
    PredictionID    INT IDENTITY PRIMARY KEY,
    StudentID       INT NOT NULL REFERENCES StudentProfiles(StudentID),
    PredictedScore  DECIMAL(6,2) NOT NULL CHECK (PredictedScore BETWEEN 0 AND 1200),
    ProbReachTarget DECIMAL(5,4) NOT NULL CHECK (ProbReachTarget BETWEEN 0 AND 1),
    RiskNote        NVARCHAR(300) NULL,
    PredictedAt     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

/* ===== 5. AI TUTOR ===== */
CREATE TABLE TutorSessions (
    SessionID INT IDENTITY PRIMARY KEY,
    StudentID INT NOT NULL REFERENCES StudentProfiles(StudentID),
    StartedAt DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE TutorMessages (
    MessageID  BIGINT IDENTITY PRIMARY KEY,
    SessionID  INT NOT NULL REFERENCES TutorSessions(SessionID) ON DELETE CASCADE,
    Sender     VARCHAR(5) NOT NULL CHECK (Sender IN ('USER','AI')),
    Content    NVARCHAR(MAX) NOT NULL,
    QuestionID INT NULL REFERENCES Questions(QuestionID),
    SentAt     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

/* ===== 6. ANALYTICS & HỆ THỐNG ===== */
CREATE TABLE StudyLogs (
    LogID        BIGINT IDENTITY PRIMARY KEY,
    StudentID    INT NOT NULL REFERENCES StudentProfiles(StudentID),
    ActivityType VARCHAR(20) NOT NULL CHECK (ActivityType IN ('LESSON','QUIZ','MOCK','TUTOR')),
    DurationMin  INT NOT NULL CHECK (DurationMin >= 0),
    LoggedAt     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE SystemSettings (
    SettingKey   VARCHAR(100) PRIMARY KEY,
    SettingValue NVARCHAR(500) NOT NULL,
    UpdatedBy    INT NULL REFERENCES Users(UserID),
    UpdatedAt    DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE AuditLog (
    AuditID   BIGINT IDENTITY PRIMARY KEY,
    TableName SYSNAME NOT NULL,
    Action    VARCHAR(10) NOT NULL CHECK (Action IN ('INSERT','UPDATE','DELETE')),
    RecordKey NVARCHAR(100) NULL,
    ChangedBy SYSNAME NOT NULL DEFAULT SUSER_SNAME(),
    ChangedAt DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

/* ===== 6b. THÔNG BÁO  ===== */
CREATE TABLE Notifications (
    NotificationID BIGINT IDENTITY PRIMARY KEY,
    UserID         INT NOT NULL REFERENCES Users(UserID),             
    StudentID      INT NULL REFERENCES StudentProfiles(StudentID),     
    NotifyType     VARCHAR(20) NOT NULL
                   CHECK (NotifyType IN ('INACTIVITY','BEHIND_SCHEDULE','LOW_PROBABILITY')),
    Message        NVARCHAR(500) NOT NULL,
    IsRead         BIT NOT NULL DEFAULT 0,
    CreatedAt      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_LearningPaths_Student_Active
    ON LearningPaths(StudentID)
    WHERE Status = 'ACTIVE';
GO

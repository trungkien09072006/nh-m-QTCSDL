import os
from contextlib import closing
from datetime import date, datetime

import pyodbc


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _connection_string() -> str:
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("SQL_SERVER", r"localhost\SQLEXPRESS")
    database = os.getenv("SQL_DATABASE", "AILearningDB")
    trusted_connection = os.getenv("SQL_TRUSTED_CONNECTION", "true").lower()

    parts = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(server)}",
        f"DATABASE={_odbc_value(database)}",
        "TrustServerCertificate=yes",
    ]

    if trusted_connection in {"1", "true", "yes"}:
        parts.append("Trusted_Connection=yes")
    elif trusted_connection in {"0", "false", "no"}:
        username = os.getenv("SQL_USERNAME")
        password = os.getenv("SQL_PASSWORD")
        if not username or password is None:
            raise ValueError(
                "SQL_USERNAME and SQL_PASSWORD are required when "
                "SQL_TRUSTED_CONNECTION is disabled."
            )
        parts.extend(
            [
                f"UID={_odbc_value(username)}",
                f"PWD={_odbc_value(password)}",
            ]
        )
    else:
        raise ValueError(
            "SQL_TRUSTED_CONNECTION must be true or false."
        )

    return ";".join(parts) + ";"


def _row_as_dict(cursor, row):
    if row is None:
        return None
    return dict(zip((column[0] for column in cursor.description), row))


def _display_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    return value


def _display_datetime(value):
    if isinstance(value, datetime):
        return value.strftime("%H:%M %d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return value


def _fetch_all(cursor, query, parameters=()):
    cursor.execute(query, parameters)
    return [_row_as_dict(cursor, row) for row in cursor.fetchall()]


def _get_active_student(cursor, student_email: str):
    cursor.execute(
        """
        SELECT TOP 1
            u.UserID,
            u.FullName,
            sp.TargetScore,
            sp.ExamDate,
            sp.DailyStudyMin
        FROM Users AS u
        INNER JOIN Roles AS role ON role.RoleID = u.RoleID
        INNER JOIN StudentProfiles AS sp ON sp.StudentID = u.UserID
        WHERE u.Email = ? AND role.RoleName = N'Student' AND u.IsActive = 1
        """,
        (student_email,),
    )
    return _row_as_dict(cursor, cursor.fetchone())


def load_dashboard_data(student_email: str) -> dict:
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            student = _get_active_student(cursor, student_email)

            if student is None:
                return {
                    "student": None,
                    "weekly_minutes": 0,
                    "latest_exam": None,
                    "prediction": None,
                    "competencies": [],
                    "tasks": [],
                    "recommendations": [],
                    "exams": [],
                    "notifications": [],
                    "unread_notification_count": 0,
                    "tutor_messages": [],
                    "tutor_questions": [],
                }

            student_id = student["UserID"]

            cursor.execute(
                """
                SELECT
                    COALESCE((
                        SELECT SUM(DurationMin)
                        FROM StudyLogs
                        WHERE StudentID = ?
                          AND LoggedAt >= DATEADD(DAY, -6, CONVERT(date, SYSDATETIME()))
                    ), 0) AS WeeklyMinutes,
                    (
                        SELECT TOP 1 e.Title
                        FROM ExamAttempts AS ea
                        INNER JOIN Exams AS e ON e.ExamID = ea.ExamID
                        WHERE ea.StudentID = ? AND ea.SubmittedAt IS NOT NULL
                        ORDER BY ea.SubmittedAt DESC
                    ) AS LatestExamTitle,
                    (
                        SELECT TOP 1 ea.Score
                        FROM ExamAttempts AS ea
                        WHERE ea.StudentID = ? AND ea.SubmittedAt IS NOT NULL
                        ORDER BY ea.SubmittedAt DESC
                    ) AS LatestExamScore,
                    (
                        SELECT TOP 1 PredictedScore
                        FROM ScorePredictions
                        WHERE StudentID = ?
                        ORDER BY PredictedAt DESC, PredictionID DESC
                    ) AS PredictedScore,
                    (
                        SELECT TOP 1 ProbReachTarget
                        FROM ScorePredictions
                        WHERE StudentID = ?
                        ORDER BY PredictedAt DESC, PredictionID DESC
                    ) AS ProbReachTarget,
                    (
                        SELECT TOP 1 RiskNote
                        FROM ScorePredictions
                        WHERE StudentID = ?
                        ORDER BY PredictedAt DESC, PredictionID DESC
                    ) AS RiskNote
                """,
                (
                    student_id,
                    student_id,
                    student_id,
                    student_id,
                    student_id,
                    student_id,
                ),
            )
            summary = _row_as_dict(cursor, cursor.fetchone())

            competencies = _fetch_all(
                cursor,
                """
                SELECT
                    subject.SubjectName,
                    competency.CompetencyName,
                    CONVERT(int, COALESCE(profile.Mastery, 0) * 100) AS MasteryPercent
                FROM Competencies AS competency
                INNER JOIN Subjects AS subject
                    ON subject.SubjectID = competency.SubjectID
                LEFT JOIN StudentCompetency AS profile
                    ON profile.CompetencyID = competency.CompetencyID
                   AND profile.StudentID = ?
                ORDER BY subject.SubjectName, competency.CompetencyName
                """,
                (student_id,),
            )

            tasks = _fetch_all(
                cursor,
                """
                SELECT TOP 5
                    competency.CompetencyName,
                    resource.Title AS ResourceTitle,
                    item.ScheduledDate,
                    item.Status,
                    item.Priority
                FROM LearningPaths AS path
                INNER JOIN LearningPathItems AS item ON item.PathID = path.PathID
                INNER JOIN Competencies AS competency
                    ON competency.CompetencyID = item.CompetencyID
                LEFT JOIN LearningResources AS resource
                    ON resource.ResourceID = item.ResourceID
                WHERE path.StudentID = ?
                  AND path.Status = 'ACTIVE'
                  AND item.Status IN ('TODO', 'DOING')
                ORDER BY item.ScheduledDate, item.Priority
                """,
                (student_id,),
            )

            recommendations = _fetch_all(
                cursor,
                """
                SELECT TOP 5
                    recommendation.RecID,
                    recommendation.Reason,
                    recommendation.IsAccepted,
                    resource.Title AS ResourceTitle,
                    resource.ResourceType,
                    resource.Url AS ResourceUrl,
                    resource.EstimatedMin,
                    question.QuestionID,
                    question.Content AS QuestionContent,
                    COALESCE(res_comp.CompetencyName, q_comp.CompetencyName) AS CompetencyName
                FROM Recommendations AS recommendation
                LEFT JOIN LearningResources AS resource
                    ON resource.ResourceID = recommendation.ResourceID
                LEFT JOIN Competencies AS res_comp
                    ON res_comp.CompetencyID = resource.CompetencyID
                LEFT JOIN Questions AS question
                    ON question.QuestionID = recommendation.QuestionID
                LEFT JOIN Competencies AS q_comp
                    ON q_comp.CompetencyID = question.CompetencyID
                WHERE recommendation.StudentID = ?
                  AND COALESCE(recommendation.IsAccepted, -1) <> 0
                ORDER BY
                    CASE WHEN recommendation.IsAccepted IS NULL THEN 0 ELSE 1 END,
                    recommendation.CreatedAt DESC
                """,
                (student_id,),
            )

            exams = _fetch_all(
                cursor,
                """
                SELECT TOP 3
                    exam.Title,
                    exam.DurationMin,
                    exam.ExamType,
                    COUNT(exam_question.QuestionID) AS QuestionCount
                FROM Exams AS exam
                LEFT JOIN ExamQuestions AS exam_question
                    ON exam_question.ExamID = exam.ExamID
                GROUP BY exam.ExamID, exam.Title, exam.DurationMin, exam.ExamType,
                         exam.CreatedAt
                ORDER BY exam.CreatedAt DESC
                """,
            )

            notifications = _fetch_all(
                cursor,
                """
                SELECT TOP 5
                    NotificationID,
                    NotifyType,
                    Message,
                    IsRead,
                    CreatedAt
                FROM Notifications
                WHERE UserID = ? OR StudentID = ?
                ORDER BY IsRead ASC, CreatedAt DESC
                """,
                (student_id, student_id),
            )

            unread_count = sum(1 for n in notifications if not n.get("IsRead"))

            tutor_messages = _fetch_all(
                cursor,
                """
                SELECT TOP 10
                    tm.MessageID,
                    tm.Sender,
                    tm.Content,
                    tm.QuestionID,
                    tm.SentAt,
                    q.Content AS QuestionTitle
                FROM TutorMessages AS tm
                INNER JOIN TutorSessions AS ts ON ts.SessionID = tm.SessionID
                LEFT JOIN Questions AS q ON q.QuestionID = tm.QuestionID
                WHERE ts.StudentID = ?
                ORDER BY tm.SentAt DESC, tm.MessageID DESC
                """,
                (student_id,),
            )
            tutor_messages.reverse()

            tutor_questions = _fetch_all(
                cursor,
                """
                SELECT
                    q.QuestionID,
                    c.CompetencyName,
                    q.Content,
                    q.Difficulty
                FROM Questions AS q
                INNER JOIN Competencies AS c ON c.CompetencyID = q.CompetencyID
                WHERE q.IsApproved = 1
                ORDER BY q.QuestionID ASC
                """,
            )

    student["ExamDate"] = _display_date(student["ExamDate"])
    return {
        "student": student,
        "weekly_minutes": summary["WeeklyMinutes"],
        "latest_exam": (
            {
                "title": summary["LatestExamTitle"],
                "score": summary["LatestExamScore"],
            }
            if summary["LatestExamTitle"] is not None
            else None
        ),
        "prediction": (
            {
                "score": summary["PredictedScore"],
                "probability": summary["ProbReachTarget"],
                "risk_note": summary.get("RiskNote"),
            }
            if summary["PredictedScore"] is not None
            else None
        ),
        "competencies": competencies,
        "tasks": [
            {**task, "ScheduledDate": _display_date(task["ScheduledDate"])}
            for task in tasks
        ],
        "recommendations": recommendations,
        "exams": exams,
        "notifications": [
            {**item, "CreatedAt": _display_datetime(item.get("CreatedAt"))}
            for item in notifications
        ],
        "unread_notification_count": unread_count,
        "tutor_messages": [
            {**msg, "SentAt": _display_datetime(msg.get("SentAt"))}
            for msg in tutor_messages
        ],
        "tutor_questions": tutor_questions,
    }


def refresh_ai_insights(student_email: str) -> bool:
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            student = _get_active_student(cursor, student_email)
            if student is None:
                return False

            student_id = student["UserID"]
            cursor.execute("SELECT OBJECT_ID('dbo.sp_GenerateRecommendations', 'P')")
            has_sp = cursor.fetchone()[0] is not None

            if has_sp:
                cursor.execute("EXEC dbo.sp_GenerateRecommendations @StudentID = ?", (student_id,))
                cursor.execute("EXEC dbo.sp_CalculateScorePrediction @StudentID = ?", (student_id,))
                cursor.execute("EXEC dbo.sp_GenerateNotifications @StudentID = ?", (student_id,))
            else:
                cursor.execute(
                    """
                    INSERT INTO Recommendations (StudentID, ResourceID, Reason, IsAccepted)
                    SELECT
                        sc.StudentID,
                        lr.ResourceID,
                        CONCAT(
                            N'Mức độ thành thạo chủ đề "', c.CompetencyName, N'" hiện đạt ',
                            CAST(CAST(ROUND(sc.Mastery * 100, 0) AS INT) AS NVARCHAR(10)),
                            N'% qua ', sc.AttemptCount,
                            N' lượt làm bài. Gợi ý học liệu "', lr.Title, N'" để cải thiện.'
                        ),
                        NULL
                    FROM StudentCompetency AS sc
                    INNER JOIN Competencies AS c ON c.CompetencyID = sc.CompetencyID
                    CROSS APPLY (
                        SELECT TOP 1 r.ResourceID, r.Title
                        FROM LearningResources AS r
                        WHERE r.CompetencyID = sc.CompetencyID
                        ORDER BY r.EstimatedMin ASC
                    ) AS lr
                    WHERE sc.StudentID = ? AND sc.Mastery < 0.65
                      AND NOT EXISTS (
                          SELECT 1 FROM Recommendations AS rec
                          WHERE rec.StudentID = sc.StudentID
                            AND rec.ResourceID = lr.ResourceID
                            AND COALESCE(rec.IsAccepted, -1) <> 0
                      )
                    """,
                    (student_id,),
                )

                cursor.execute(
                    """
                    DECLARE @Target INT = (SELECT TargetScore FROM StudentProfiles WHERE StudentID = ?);
                    DECLARE @Mastery DECIMAL(5,4) = ISNULL((SELECT AVG(Mastery) FROM StudentCompetency WHERE StudentID = ?), 0.5);
                    DECLARE @Pred DECIMAL(6,2) = ROUND(@Mastery * 1200.0 * 0.85 + 120.0, 2);
                    IF @Pred > 1200 SET @Pred = 1200;
                    DECLARE @Prob DECIMAL(5,4) = CASE WHEN @Target > 0 AND @Pred < @Target THEN ROUND((@Pred / @Target) * 0.85, 4) ELSE 0.9000 END;
                    INSERT INTO ScorePredictions (StudentID, PredictedScore, ProbReachTarget, RiskNote)
                    VALUES (?, @Pred, @Prob, N'Dự đoán cập nhật dựa trên mức độ thành thạo năng lực và lịch sử luyện đề.');
                    """,
                    (student_id, student_id, student_id),
                )

            connection.commit()
            return True


def respond_to_recommendation(student_email: str, rec_id: int, accepted: bool) -> bool:
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            student = _get_active_student(cursor, student_email)
            if student is None:
                return False

            student_id = student["UserID"]
            cursor.execute(
                """
                UPDATE Recommendations
                SET IsAccepted = ?
                WHERE RecID = ? AND StudentID = ?
                """,
                (1 if accepted else 0, rec_id, student_id),
            )
            connection.commit()
            return cursor.rowcount > 0


def ask_ai_tutor(student_email: str, message_content: str, question_id: int | None = None) -> bool:
    cleaned_message = (message_content or "").strip()
    if not cleaned_message:
        return False

    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            student = _get_active_student(cursor, student_email)
            if student is None:
                return False

            student_id = student["UserID"]
            cursor.execute("SELECT OBJECT_ID('dbo.sp_AskTutor', 'P')")
            has_sp = cursor.fetchone()[0] is not None

            if has_sp:
                cursor.execute(
                    "EXEC dbo.sp_AskTutor @StudentID = ?, @UserMessage = ?, @QuestionID = ?",
                    (student_id, cleaned_message, question_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT TOP 1 SessionID
                    FROM TutorSessions
                    WHERE StudentID = ?
                    ORDER BY StartedAt DESC, SessionID DESC
                    """,
                    (student_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        "INSERT INTO TutorSessions (StudentID) OUTPUT INSERTED.SessionID VALUES (?)",
                        (student_id,),
                    )
                    session_id = cursor.fetchone()[0]
                else:
                    session_id = row[0]

                cursor.execute(
                    """
                    INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID)
                    VALUES (?, 'USER', ?, ?)
                    """,
                    (session_id, cleaned_message, question_id),
                )

                reply = "Trợ lý AI đã ghi nhận câu hỏi của bạn."
                if question_id is not None:
                    cursor.execute(
                        """
                        SELECT c.CompetencyName, q.Explanation, o.OptionLabel, o.OptionText
                        FROM Questions AS q
                        INNER JOIN Competencies AS c ON c.CompetencyID = q.CompetencyID
                        LEFT JOIN QuestionOptions AS o ON o.QuestionID = q.QuestionID AND o.IsCorrect = 1
                        WHERE q.QuestionID = ?
                        """,
                        (question_id,),
                    )
                    q_info = _row_as_dict(cursor, cursor.fetchone())
                    if q_info:
                        reply = (
                            f"Giải thích câu hỏi chủ đề \"{q_info['CompetencyName']}\": "
                            f"{q_info['Explanation'] or 'Chưa có giải thích chi tiết.'} "
                            f"Đáp án đúng là {q_info['OptionLabel']}: {q_info['OptionText']}."
                        )

                cursor.execute(
                    """
                    INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID)
                    VALUES (?, 'AI', ?, ?)
                    """,
                    (session_id, reply, question_id),
                )

            connection.commit()
            return True


def mark_notifications_read(student_email: str, notification_id: int | None = None) -> bool:
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            student = _get_active_student(cursor, student_email)
            if student is None:
                return False

            student_id = student["UserID"]
            if notification_id is not None:
                cursor.execute(
                    """
                    UPDATE Notifications
                    SET IsRead = 1
                    WHERE NotificationID = ? AND (UserID = ? OR StudentID = ?)
                    """,
                    (notification_id, student_id, student_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE Notifications
                    SET IsRead = 1
                    WHERE (UserID = ? OR StudentID = ?) AND IsRead = 0
                    """,
                    (student_id, student_id),
                )
            connection.commit()
            return True
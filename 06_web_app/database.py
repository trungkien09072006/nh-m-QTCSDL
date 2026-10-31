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


def _fetch_all(cursor, query, parameters=()):
    cursor.execute(query, parameters)
    return [_row_as_dict(cursor, row) for row in cursor.fetchall()]


def load_dashboard_data(student_email: str) -> dict:
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
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
            student = _row_as_dict(cursor, cursor.fetchone())

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
                        ORDER BY PredictedAt DESC
                    ) AS PredictedScore,
                    (
                        SELECT TOP 1 ProbReachTarget
                        FROM ScorePredictions
                        WHERE StudentID = ?
                        ORDER BY PredictedAt DESC
                    ) AS ProbReachTarget
                """,
                (student_id, student_id, student_id, student_id, student_id),
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
                SELECT TOP 3
                    recommendation.Reason,
                    resource.Title AS ResourceTitle,
                    question.Content AS QuestionContent
                FROM Recommendations AS recommendation
                LEFT JOIN LearningResources AS resource
                    ON resource.ResourceID = recommendation.ResourceID
                LEFT JOIN Questions AS question
                    ON question.QuestionID = recommendation.QuestionID
                WHERE recommendation.StudentID = ?
                  AND COALESCE(recommendation.IsAccepted, 0) = 0
                ORDER BY recommendation.CreatedAt DESC
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
    }

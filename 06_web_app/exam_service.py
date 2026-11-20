from contextlib import closing
from datetime import date, datetime
from decimal import Decimal

import pyodbc

from database import _connection_string, _fetch_all


class ExamNotFound(Exception):
    pass


class AttemptNotFound(Exception):
    pass


class AttemptSubmitted(Exception):
    pass


class AttemptExpired(Exception):
    pass


def _iso(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def list_exams():
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            return _fetch_all(
                cursor,
                """
                SELECT e.ExamID AS id, e.Title AS title, e.ExamType AS exam_type,
                       e.DurationMin AS duration_min, COUNT(eq.QuestionID) AS question_count
                FROM dbo.Exams AS e
                INNER JOIN dbo.ExamQuestions AS eq ON eq.ExamID = e.ExamID
                INNER JOIN dbo.Questions AS q ON q.QuestionID = eq.QuestionID
                WHERE q.IsApproved = 1
                GROUP BY e.ExamID, e.Title, e.ExamType, e.DurationMin, e.CreatedAt
                ORDER BY e.CreatedAt DESC, e.ExamID DESC
                """,
            )


def _attempt_questions(cursor, attempt_id):
    rows = _fetch_all(
        cursor,
        """
        SELECT q.QuestionID AS question_id, q.Content AS content,
               q.Difficulty AS difficulty, aa.SelectedOption AS selected_option_id,
               CASE WHEN ea.SubmittedAt IS NOT NULL THEN aa.IsCorrect ELSE NULL END AS is_correct,
               CASE WHEN ea.SubmittedAt IS NOT NULL THEN q.Explanation ELSE NULL END AS explanation,
               o.OptionID AS option_id, o.OptionLabel AS option_label,
               o.OptionText AS option_text,
               CASE WHEN ea.SubmittedAt IS NOT NULL THEN o.IsCorrect ELSE NULL END AS option_is_correct
        FROM dbo.AttemptAnswers AS aa
        INNER JOIN dbo.ExamAttempts AS ea ON ea.AttemptID = aa.AttemptID
        INNER JOIN dbo.ExamQuestions AS eq
            ON eq.ExamID = aa.ExamID AND eq.QuestionID = aa.QuestionID
        INNER JOIN dbo.Questions AS q ON q.QuestionID = aa.QuestionID
        LEFT JOIN dbo.QuestionOptions AS o ON o.QuestionID = q.QuestionID
        WHERE aa.AttemptID = ?
        ORDER BY eq.OrderNo, o.OptionLabel
        """,
        (attempt_id,),
    )
    questions = {}
    for row in rows:
        question = questions.setdefault(
            row["question_id"],
            {
                "id": row["question_id"],
                "content": row["content"],
                "difficulty": row["difficulty"],
                "selected_option_id": row["selected_option_id"],
                "is_correct": row["is_correct"],
                "explanation": row["explanation"],
                "options": [],
            },
        )
        if row["option_id"] is not None:
            question["options"].append(
                {
                    "id": row["option_id"],
                    "label": row["option_label"],
                    "text": row["option_text"],
                    "is_correct": row["option_is_correct"],
                }
            )
    return list(questions.values())


def start_attempt(student_id, exam_id):
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                """
                SELECT e.Title, e.DurationMin
                FROM dbo.Exams AS e
                WHERE e.ExamID = ?
                  AND EXISTS (
                      SELECT 1
                      FROM dbo.ExamQuestions AS eq
                      INNER JOIN dbo.Questions AS q ON q.QuestionID = eq.QuestionID
                      WHERE eq.ExamID = e.ExamID AND q.IsApproved = 1
                  )
                """,
                (exam_id,),
            )
            exam = cursor.fetchone()
            if exam is None:
                raise ExamNotFound()

            cursor.execute(
                """
                INSERT INTO dbo.ExamAttempts (ExamID, StudentID)
                OUTPUT INSERTED.AttemptID, INSERTED.StartedAt
                VALUES (?, ?)
                """,
                (exam_id, student_id),
            )
            attempt_id, started_at = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO dbo.AttemptAnswers (AttemptID, ExamID, QuestionID)
                SELECT ?, eq.ExamID, eq.QuestionID
                FROM dbo.ExamQuestions AS eq
                INNER JOIN dbo.Questions AS q ON q.QuestionID = eq.QuestionID
                WHERE eq.ExamID = ? AND q.IsApproved = 1
                """,
                (attempt_id, exam_id),
            )
            connection.commit()
            return {
                "attempt": {
                    "id": attempt_id,
                    "exam_id": exam_id,
                    "exam_title": exam[0],
                    "duration_min": exam[1],
                    "started_at": _iso(started_at),
                    "remaining_seconds": exam[1] * 60,
                    "submitted_at": None,
                    "score": None,
                },
                "questions": _attempt_questions(cursor, attempt_id),
            }


def get_attempt(student_id, attempt_id):
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            rows = _fetch_all(
                cursor,
                """
                SELECT ea.AttemptID AS id, ea.ExamID AS exam_id, e.Title AS exam_title,
                       e.DurationMin AS duration_min, ea.StartedAt AS started_at,
                       ea.SubmittedAt AS submitted_at, ea.Score AS score,
                       DATEDIFF(SECOND, SYSDATETIME(),
                           DATEADD(MINUTE, e.DurationMin, ea.StartedAt)) AS remaining_seconds
                FROM dbo.ExamAttempts AS ea
                INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
                WHERE ea.AttemptID = ? AND ea.StudentID = ?
                """,
                (attempt_id, student_id),
            )
            if not rows:
                raise AttemptNotFound()
            attempt = rows[0]
            attempt["started_at"] = _iso(attempt["started_at"])
            attempt["submitted_at"] = _iso(attempt["submitted_at"])
            attempt["score"] = float(attempt["score"]) if attempt["score"] is not None else None
            attempt["remaining_seconds"] = max(0, attempt["remaining_seconds"] or 0)
            attempt["questions"] = _attempt_questions(cursor, attempt_id)
            if attempt["submitted_at"] is not None:
                attempt["correct_count"] = sum(
                    q["is_correct"] is True or q["is_correct"] == 1
                    for q in attempt["questions"]
                )
                attempt["question_count"] = len(attempt["questions"])
            return attempt


def _save_answers(cursor, attempt_id, exam_id, answers):
    for question_id, option_id in answers.items():
        cursor.execute(
            """
            SELECT 1 FROM dbo.AttemptAnswers
            WHERE AttemptID = ? AND ExamID = ? AND QuestionID = ?
            """,
            (attempt_id, exam_id, question_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("Có câu trả lời không thuộc đề thi này.")
        cursor.execute(
            """
            SELECT 1 FROM dbo.QuestionOptions
            WHERE OptionID = ? AND QuestionID = ?
            """,
            (option_id, question_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("Lựa chọn không thuộc câu hỏi đã chọn.")
        cursor.execute(
            """
            UPDATE dbo.AttemptAnswers
            SET SelectedOption = ?
            WHERE AttemptID = ? AND ExamID = ? AND QuestionID = ?
            """,
            (option_id, attempt_id, exam_id, question_id),
        )


def save_attempt_answers(student_id, attempt_id, answers):
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                """
                SELECT ea.ExamID, ea.SubmittedAt,
                       DATEDIFF(SECOND, SYSDATETIME(),
                           DATEADD(MINUTE, e.DurationMin, ea.StartedAt))
                FROM dbo.ExamAttempts AS ea WITH (UPDLOCK, HOLDLOCK)
                INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
                WHERE ea.AttemptID = ? AND ea.StudentID = ?
                """,
                (attempt_id, student_id),
            )
            attempt = cursor.fetchone()
            if attempt is None:
                raise AttemptNotFound()
            exam_id, submitted_at, remaining_seconds = attempt
            if submitted_at is not None:
                raise AttemptSubmitted()
            if remaining_seconds <= 0:
                raise AttemptExpired()

            _save_answers(cursor, attempt_id, exam_id, answers)
            connection.commit()


def submit_attempt(student_id, attempt_id, answers):
    with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                """
                SELECT ea.ExamID, ea.SubmittedAt,
                       DATEDIFF(SECOND, SYSDATETIME(),
                           DATEADD(MINUTE, e.DurationMin, ea.StartedAt))
                FROM dbo.ExamAttempts AS ea WITH (UPDLOCK, HOLDLOCK)
                INNER JOIN dbo.Exams AS e ON e.ExamID = ea.ExamID
                WHERE ea.AttemptID = ? AND ea.StudentID = ?
                """,
                (attempt_id, student_id),
            )
            attempt = cursor.fetchone()
            if attempt is None:
                raise AttemptNotFound()
            exam_id, submitted_at, remaining_seconds = attempt
            if submitted_at is not None:
                raise AttemptSubmitted()

            timed_out = remaining_seconds <= 0
            if not timed_out:
                _save_answers(cursor, attempt_id, exam_id, answers)

            cursor.execute(
                """
                UPDATE dbo.AttemptAnswers
                SET IsCorrect = CASE WHEN EXISTS (
                    SELECT 1 FROM dbo.QuestionOptions AS o
                    WHERE o.OptionID = dbo.AttemptAnswers.SelectedOption
                      AND o.QuestionID = dbo.AttemptAnswers.QuestionID
                      AND o.IsCorrect = 1
                ) THEN 1 ELSE 0 END
                WHERE AttemptID = ?
                """,
                (attempt_id,),
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS QuestionCount,
                       SUM(CASE WHEN IsCorrect = 1 THEN 1 ELSE 0 END) AS CorrectCount
                FROM dbo.AttemptAnswers
                WHERE AttemptID = ?
                """,
                (attempt_id,),
            )
            question_count, correct_count = cursor.fetchone()
            score = (
                Decimal(correct_count or 0) * Decimal(100) / Decimal(question_count)
                if question_count
                else Decimal(0)
            )
            cursor.execute(
                """
                UPDATE dbo.ExamAttempts
                SET SubmittedAt = SYSDATETIME(), Score = ?
                WHERE AttemptID = ? AND StudentID = ? AND SubmittedAt IS NULL
                """,
                (round(score, 2), attempt_id, student_id),
            )
            connection.commit()
    result = get_attempt(student_id, attempt_id)
    result["timed_out"] = timed_out
    return result

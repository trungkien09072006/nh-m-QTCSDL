"""Dịch vụ Lộ trình học và Tiến độ cho học sinh (Phần 4)."""

from contextlib import closing
from datetime import date, datetime

import pyodbc

from database import _connection_string, _fetch_all

VALID_STATUSES = {"TODO", "DOING", "DONE", "SKIPPED"}


class LearningPathItemNotFound(Exception):
    pass


def _iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _display_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    return value


def _safe_url(url):
    if isinstance(url, str) and url.lower().startswith(("http://", "https://")):
        return url
    return None


def _connect():
    return closing(pyodbc.connect(_connection_string(), timeout=5))


def _load_active_path(cursor, student_id):
    rows = _fetch_all(
        cursor,
        """
        SELECT TOP 1
            lp.PathID,
            lp.StartDate,
            lp.EndDate,
            lp.Status,
            lp.GeneratedAt,
            DATEDIFF(DAY, CAST(SYSDATETIME() AS DATE), lp.EndDate) AS DaysLeft
        FROM dbo.LearningPaths AS lp
        WHERE lp.StudentID = ? AND lp.Status = 'ACTIVE'
        ORDER BY lp.GeneratedAt DESC, lp.PathID DESC
        """,
        (student_id,),
    )
    return rows[0] if rows else None


def _load_path_items(cursor, path_id):
    rows = _fetch_all(
        cursor,
        """
        SELECT
            i.ItemID,
            i.PathID,
            i.ScheduledDate,
            i.Priority,
            i.Status,
            CASE
                WHEN i.Status IN ('TODO', 'DOING')
                     AND i.ScheduledDate < CAST(SYSDATETIME() AS DATE)
                THEN 1 ELSE 0
            END AS IsOverdue,
            c.CompetencyID,
            c.CompetencyName,
            s.SubjectName,
            r.ResourceID,
            r.Title AS ResourceTitle,
            r.ResourceType,
            r.Url AS ResourceUrl,
            r.EstimatedMin
        FROM dbo.LearningPathItems AS i
        INNER JOIN dbo.Competencies AS c ON c.CompetencyID = i.CompetencyID
        INNER JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
        LEFT JOIN dbo.LearningResources AS r ON r.ResourceID = i.ResourceID
        WHERE i.PathID = ?
        ORDER BY
            CASE i.Status
                WHEN 'DOING' THEN 1
                WHEN 'TODO' THEN 2
                WHEN 'DONE' THEN 3
                ELSE 4
            END,
            i.ScheduledDate ASC,
            i.Priority ASC,
            i.ItemID ASC
        """,
        (path_id,),
    )
    return [
        {
            "id": row["ItemID"],
            "path_id": row["PathID"],
            "scheduled_date": _iso(row["ScheduledDate"]),
            "scheduled_date_display": _display_date(row["ScheduledDate"]),
            "priority": row["Priority"],
            "status": row["Status"],
            "is_overdue": bool(row["IsOverdue"]),
            "competency_id": row["CompetencyID"],
            "competency_name": row["CompetencyName"],
            "subject_name": row["SubjectName"],
            "resource_id": row["ResourceID"],
            "resource_title": row["ResourceTitle"],
            "resource_type": row["ResourceType"],
            "resource_url": _safe_url(row["ResourceUrl"]),
            "estimated_min": row["EstimatedMin"] or 15,
        }
        for row in rows
    ]


def _summarize(items):
    total = len(items)
    done = sum(1 for item in items if item["status"] == "DONE")
    doing = sum(1 for item in items if item["status"] == "DOING")
    todo = sum(1 for item in items if item["status"] == "TODO")
    skipped = sum(1 for item in items if item["status"] == "SKIPPED")
    overdue = sum(1 for item in items if item["is_overdue"])
    progress = round(100.0 * done / total, 1) if total > 0 else 0.0
    return {
        "total_items": total,
        "done_items": done,
        "doing_items": doing,
        "todo_items": todo,
        "skipped_items": skipped,
        "overdue_items": overdue,
        "progress_percent": progress,
    }


def get_learning_path(student_id):
    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            path = _load_active_path(cursor, student_id)
            if path is None:
                return {
                    "path": None,
                    "summary": _summarize([]),
                    "items": [],
                }

            items = _load_path_items(cursor, path["PathID"])
            return {
                "path": {
                    "id": path["PathID"],
                    "start_date": _iso(path["StartDate"]),
                    "start_date_display": _display_date(path["StartDate"]),
                    "end_date": _iso(path["EndDate"]),
                    "end_date_display": _display_date(path["EndDate"]),
                    "status": path["Status"],
                    "days_left": path["DaysLeft"],
                    "generated_at": _iso(path["GeneratedAt"]),
                },
                "summary": _summarize(items),
                "items": items,
            }


def update_item_status(student_id, item_id, new_status):
    if new_status not in VALID_STATUSES:
        raise ValueError("Trạng thái nhiệm vụ không hợp lệ.")

    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                """
                SELECT i.Status, ISNULL(r.EstimatedMin, 15) AS EstimatedMin
                FROM dbo.LearningPathItems AS i
                INNER JOIN dbo.LearningPaths AS lp ON lp.PathID = i.PathID
                LEFT JOIN dbo.LearningResources AS r ON r.ResourceID = i.ResourceID
                WHERE i.ItemID = ? AND lp.StudentID = ?
                """,
                (item_id, student_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise LearningPathItemNotFound()

            old_status, estimated_min = row[0], row[1]

            cursor.execute(
                """
                UPDATE dbo.LearningPathItems
                SET Status = ?
                WHERE ItemID = ?
                """,
                (new_status, item_id),
            )

            # Ghi nhận thời gian học lên Dashboard khi chuyển sang hoàn thành
            if new_status == "DONE" and old_status != "DONE":
                cursor.execute(
                    """
                    INSERT INTO dbo.StudyLogs (StudentID, ActivityType, DurationMin)
                    VALUES (?, 'LESSON', ?)
                    """,
                    (student_id, estimated_min),
                )

            connection.commit()

    data = get_learning_path(student_id)
    data["updated_item"] = {"id": item_id, "status": new_status}
    return data
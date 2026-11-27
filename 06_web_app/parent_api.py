"""API dành cho Phụ huynh (Parent) theo dõi tiến độ và cảnh báo của con em."""

from contextlib import closing
import pyodbc
from flask import Blueprint, current_app, jsonify

from auth_utils import require_api_roles, serialize_rows
from database import _connection_string, _fetch_all

bp = Blueprint("parent", __name__, url_prefix="/api/parent")


def _connect():
    return closing(pyodbc.connect(_connection_string(), timeout=5))


@bp.get("/children")
def list_children():
    user, err = require_api_roles("Parent")
    if err:
        return err

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            rows = _fetch_all(
                cur,
                """
                SELECT StudentID, StudentName, SchoolName, TargetScore, ExamDate, DailyStudyMin
                FROM dbo.vw_ParentChildren
                WHERE ParentID = ?
                ORDER BY StudentID
                """,
                (user["id"],),
            )
        return jsonify(children=serialize_rows(rows))
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải danh sách con em của phụ huynh")
        return jsonify(error="Không thể tải dữ liệu từ SQL Server."), 503


@bp.get("/dashboard")
def parent_dashboard():
    user, err = require_api_roles("Parent")
    if err:
        return err

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            rows = _fetch_all(
                cur,
                """
                SELECT *
                FROM dbo.vw_ParentDashboard
                WHERE ParentID = ?
                ORDER BY StudentID
                """,
                (user["id"],),
            )
        return jsonify(children=serialize_rows(rows))
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải dashboard phụ huynh")
        return jsonify(error="Không thể tải dữ liệu từ SQL Server."), 503


@bp.get("/children/<int:student_id>/progress")
def child_progress(student_id):
    user, err = require_api_roles("Parent")
    if err:
        return err

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            # Kiểm tra quan hệ phụ huynh - học sinh
            cur.execute(
                "SELECT 1 FROM dbo.ParentStudent WHERE ParentID = ? AND StudentID = ?",
                (user["id"], student_id),
            )
            if cur.fetchone() is None:
                return jsonify(error="Không tìm thấy học sinh liên kết với tài khoản của bạn."), 404

            overview = _fetch_all(
                cur,
                "SELECT * FROM dbo.vw_StudentOverview WHERE StudentID = ?",
                (student_id,),
            )
            competencies = _fetch_all(
                cur,
                """
                SELECT SubjectName, CompetencyID, CompetencyName, Mastery, MasteryPercent,
                       MasteryLevel, NeedsReview, AttemptCount, WeaknessRank
                FROM dbo.vw_StudentCompetencyProfile
                WHERE StudentID = ?
                ORDER BY WeaknessRank
                """,
                (student_id,),
            )
            alerts = _fetch_all(
                cur,
                "SELECT * FROM dbo.vw_StudentAlerts WHERE StudentID = ?",
                (student_id,),
            )
            readiness = _fetch_all(
                cur,
                "SELECT * FROM dbo.vw_ExamReadiness WHERE StudentID = ?",
                (student_id,),
            )

        return jsonify(
            overview=serialize_rows(overview)[0] if overview else None,
            competencies=serialize_rows(competencies),
            alerts=serialize_rows(alerts)[0] if alerts else None,
            readiness=serialize_rows(readiness)[0] if readiness else None,
        )
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải tiến độ học sinh cho phụ huynh")
        return jsonify(error="Không thể tải dữ liệu từ SQL Server."), 503
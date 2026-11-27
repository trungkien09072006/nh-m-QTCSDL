"""Parent dashboard and student-approved parent/student account linking."""

from contextlib import closing

import pyodbc
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from database import _connection_string, _fetch_all, register_user

bp = Blueprint("parent_portal", __name__)


def _require_role(role):
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") != role:
        abort(403)
    return None


@bp.route("/parent/register", methods=["GET", "POST"])
def register_parent():
    if request.method == "POST":
        fullname = (request.form.get("fullname") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        if (
            not fullname
            or len(fullname) > 100
            or not email
            or len(email) > 150
            or len(password) < 8
            or len(password) > 128
        ):
            flash("Vui lòng nhập họ tên, email hợp lệ và mật khẩu từ 8 đến 128 ký tự.", "error")
            return render_template("parent_portal.html", portal_page="register"), 400
        try:
            if register_user(email, password, fullname, role_name="Parent"):
                flash("Tạo tài khoản phụ huynh thành công. Hãy đăng nhập để tiếp tục.", "success")
                return redirect(url_for("login"))
            flash("Email đã tồn tại hoặc không thể tạo tài khoản.", "error")
        except pyodbc.Error:
            current_app.logger.exception("Không thể tạo tài khoản phụ huynh")
            return render_template(
                "parent_portal.html",
                portal_page="register",
                db_error="Không thể kết nối SQL Server để tạo tài khoản.",
            ), 503
    return render_template("parent_portal.html", portal_page="register")


@bp.get("/parent")
def dashboard():
    denied = _require_role("Parent")
    if denied:
        return denied
    parent_id = session["user_id"]
    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                children = _fetch_all(
                    cursor,
                    """
                    SELECT StudentID, StudentName, SchoolName, TargetScore, ExamDate,
                           AvgMastery, SubmittedAttempts, LatestScore, StudyMin7d,
                           WeeklyGoalMin, LastActivityAt, PredictedScore, ProbReachTarget,
                           UnreadNotifications
                    FROM dbo.vw_ParentDashboard
                    WHERE ParentID = ?
                    ORDER BY StudentName
                    """,
                    (parent_id,),
                )
                alerts = _fetch_all(
                    cursor,
                    """
                    SELECT a.StudentID, a.StudentName, a.AlertLevel, a.AlertSummary
                    FROM dbo.vw_StudentAlerts AS a
                    INNER JOIN dbo.ParentStudent AS ps ON ps.StudentID = a.StudentID
                    WHERE ps.ParentID = ? AND a.AlertCount > 0
                    ORDER BY a.AlertCount DESC, a.StudentName
                    """,
                    (parent_id,),
                )
                requests = _fetch_all(
                    cursor,
                    """
                    SELECT request.Status, request.CreatedAt, student.FullName AS StudentName,
                           student.Email AS StudentEmail
                    FROM dbo.ParentLinkRequests AS request
                    INNER JOIN dbo.Users AS student ON student.UserID = request.StudentID
                    WHERE request.ParentID = ?
                    ORDER BY request.CreatedAt DESC
                    """,
                    (parent_id,),
                )
    except pyodbc.Error:
        current_app.logger.exception("Không thể tải cổng phụ huynh")
        return render_template(
            "parent_portal.html",
            portal_page="dashboard",
            db_error="Không thể tải dữ liệu phụ huynh từ SQL Server.",
            children=[],
            alerts=[],
            requests=[],
        ), 503
    return render_template(
        "parent_portal.html",
        portal_page="dashboard",
        children=children,
        alerts=alerts,
        requests=requests,
        db_error=None,
    )


@bp.post("/parent/link-requests")
def request_link():
    denied = _require_role("Parent")
    if denied:
        return denied
    student_email = (request.form.get("student_email") or "").strip()
    if not student_email or len(student_email) > 150:
        flash("Vui lòng nhập email học sinh hợp lệ.", "error")
        return redirect(url_for("parent_portal.dashboard"))

    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT u.UserID
                    FROM dbo.Users AS u
                    INNER JOIN dbo.Roles AS role ON role.RoleID = u.RoleID
                    INNER JOIN dbo.StudentProfiles AS profile ON profile.StudentID = u.UserID
                    WHERE LOWER(u.Email) = LOWER(?) AND role.RoleName = N'Student' AND u.IsActive = 1
                    """,
                    (student_email,),
                )
                student = cursor.fetchone()
                if student:
                    student_id = student[0]
                    cursor.execute(
                        "SELECT 1 FROM dbo.ParentStudent WHERE ParentID = ? AND StudentID = ?",
                        (session["user_id"], student_id),
                    )
                    already_linked = cursor.fetchone() is not None
                    cursor.execute(
                        """
                        SELECT 1 FROM dbo.ParentLinkRequests
                        WHERE ParentID = ? AND StudentID = ? AND Status = 'Pending'
                        """,
                        (session["user_id"], student_id),
                    )
                    pending = cursor.fetchone() is not None
                    if not already_linked and not pending:
                        cursor.execute(
                            """
                            INSERT INTO dbo.ParentLinkRequests (ParentID, StudentID)
                            VALUES (?, ?)
                            """,
                            (session["user_id"], student_id),
                        )
                        connection.commit()
        flash(
            "Nếu email thuộc tài khoản học sinh hợp lệ, yêu cầu sẽ chờ học sinh chấp thuận.",
            "success",
        )
    except pyodbc.Error:
        current_app.logger.exception("Không thể gửi yêu cầu liên kết phụ huynh")
        return render_template(
            "parent_portal.html",
            portal_page="dashboard",
            db_error="Không thể gửi yêu cầu liên kết do lỗi SQL Server.",
            children=[],
            alerts=[],
            requests=[],
        ), 503
    return redirect(url_for("parent_portal.dashboard"))


@bp.post("/parent/link-requests/<int:request_id>/respond")
def respond_to_link(request_id):
    denied = _require_role("Student")
    if denied:
        return denied
    decision = request.form.get("decision")
    if decision not in ("accept", "reject"):
        abort(400)
    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT ParentID, Status
                    FROM dbo.ParentLinkRequests WITH (UPDLOCK, HOLDLOCK)
                    WHERE RequestID = ? AND StudentID = ?
                    """,
                    (request_id, session["user_id"]),
                )
                link_request = cursor.fetchone()
                if link_request is None:
                    abort(404)
                parent_id, status = link_request
                if status != "Pending":
                    flash("Yêu cầu này đã được xử lý trước đó.", "error")
                elif decision == "accept":
                    cursor.execute(
                        """
                        IF NOT EXISTS (
                            SELECT 1 FROM dbo.ParentStudent
                            WHERE ParentID = ? AND StudentID = ?
                        )
                            INSERT INTO dbo.ParentStudent (ParentID, StudentID) VALUES (?, ?)
                        """,
                        (parent_id, session["user_id"], parent_id, session["user_id"]),
                    )
                    cursor.execute(
                        """
                        UPDATE dbo.ParentLinkRequests
                        SET Status = 'Accepted', ResolvedAt = SYSDATETIME()
                        WHERE RequestID = ?
                        """,
                        (request_id,),
                    )
                    connection.commit()
                    flash("Đã chấp thuận liên kết phụ huynh.", "success")
                else:
                    cursor.execute(
                        """
                        UPDATE dbo.ParentLinkRequests
                        SET Status = 'Rejected', ResolvedAt = SYSDATETIME()
                        WHERE RequestID = ?
                        """,
                        (request_id,),
                    )
                    connection.commit()
                    flash("Đã từ chối yêu cầu liên kết.", "success")
    except pyodbc.Error:
        current_app.logger.exception("Không thể xử lý yêu cầu liên kết phụ huynh")
        flash("Không thể xử lý yêu cầu do lỗi SQL Server.", "error")
    return redirect(url_for("dashboard"))

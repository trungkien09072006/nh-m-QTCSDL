"""Admin pages for reviewing parent/student link requests."""

from contextlib import closing

import pyodbc
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from database import _connection_string, _fetch_all, verify_login

bp = Blueprint("admin_portal", __name__)


def _require_admin():
    if "user_id" not in session:
        return redirect(url_for("admin_portal.admin_login"))
    if session.get("role") != "Admin":
        abort(403)
    return None


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("role") == "Admin":
        return redirect(url_for("admin_portal.parent_link_requests"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        user = verify_login(email, password)
        if user and user["RoleName"] == "Admin":
            session.clear()
            session["user_id"] = user["UserID"]
            session["email"] = user["Email"]
            session["fullname"] = user["FullName"]
            session["role"] = user["RoleName"]
            return redirect(url_for("admin_portal.parent_link_requests"))

        flash("Email/mật khẩu không đúng hoặc tài khoản không có quyền Admin.", "error")

    return render_template("admin_login.html")


@bp.post("/admin/logout")
def admin_logout():
    denied = _require_admin()
    if denied:
        return denied
    session.clear()
    return redirect(url_for("admin_portal.admin_login"))


@bp.get("/admin")
def admin_home():
    denied = _require_admin()
    if denied:
        return denied
    return redirect(url_for("admin_portal.parent_link_requests"))


@bp.get("/admin/parent-link-requests")
def parent_link_requests():
    denied = _require_admin()
    if denied:
        return denied

    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                requests_to_review = _fetch_all(
                    cursor,
                    """
                    SELECT link.RequestID, link.CreatedAt,
                           parent.FullName AS ParentName, parent.Email AS ParentEmail,
                           student.FullName AS StudentName, student.Email AS StudentEmail
                    FROM dbo.ParentLinkRequests AS link
                    INNER JOIN dbo.Users AS parent ON parent.UserID = link.ParentID
                    INNER JOIN dbo.Users AS student ON student.UserID = link.StudentID
                    WHERE link.Status = 'Pending'
                    ORDER BY link.CreatedAt, link.RequestID
                    """,
                )
    except pyodbc.Error:
        current_app.logger.exception("Không thể tải yêu cầu liên kết phụ huynh")
        return render_template(
            "admin_parent_link_requests.html",
            requests=[],
            db_error="Không thể tải yêu cầu xác minh từ SQL Server.",
        ), 503

    return render_template(
        "admin_parent_link_requests.html",
        requests=requests_to_review,
        db_error=None,
    )


@bp.post("/admin/parent-link-requests/<int:request_id>")
def review_parent_link_request(request_id):
    denied = _require_admin()
    if denied:
        return denied

    decision = request.form.get("decision")
    if decision not in {"approve", "reject"}:
        abort(400)

    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT ParentID, StudentID, Status
                    FROM dbo.ParentLinkRequests WITH (UPDLOCK, HOLDLOCK)
                    WHERE RequestID = ?
                    """,
                    (request_id,),
                )
                link_request = cursor.fetchone()
                if link_request is None:
                    abort(404)

                parent_id, student_id, status = link_request
                if status != "Pending":
                    flash("Yêu cầu này đã được xử lý trước đó.", "error")
                    return redirect(url_for("admin_portal.parent_link_requests"))

                cursor.execute(
                    """
                    SELECT 1
                    FROM dbo.Users AS parent
                    INNER JOIN dbo.Roles AS parent_role ON parent_role.RoleID = parent.RoleID
                    INNER JOIN dbo.Users AS student ON student.UserID = ?
                    INNER JOIN dbo.Roles AS student_role ON student_role.RoleID = student.RoleID
                    INNER JOIN dbo.StudentProfiles AS profile ON profile.StudentID = student.UserID
                    WHERE parent.UserID = ?
                      AND parent_role.RoleName = N'Parent' AND parent.IsActive = 1
                      AND student_role.RoleName = N'Student' AND student.IsActive = 1
                    """,
                    (student_id, parent_id),
                )
                if cursor.fetchone() is None:
                    flash("Không thể xác minh: tài khoản phụ huynh hoặc học sinh không còn hợp lệ.", "error")
                    return redirect(url_for("admin_portal.parent_link_requests"))

                if decision == "approve":
                    cursor.execute(
                        """
                        IF NOT EXISTS (
                            SELECT 1 FROM dbo.ParentStudent
                            WHERE ParentID = ? AND StudentID = ?
                        )
                            INSERT INTO dbo.ParentStudent (ParentID, StudentID) VALUES (?, ?)
                        """,
                        (parent_id, student_id, parent_id, student_id),
                    )
                    status = "Accepted"
                else:
                    status = "Rejected"

                cursor.execute(
                    """
                    UPDATE dbo.ParentLinkRequests
                    SET Status = ?, ResolvedAt = SYSDATETIME()
                    WHERE RequestID = ? AND Status = 'Pending'
                    """,
                    (status, request_id),
                )
                connection.commit()
    except pyodbc.Error:
        current_app.logger.exception("Không thể xử lý yêu cầu liên kết phụ huynh")
        flash("Không thể xử lý yêu cầu do lỗi SQL Server.", "error")
        return redirect(url_for("admin_portal.parent_link_requests"))

    flash(
        "Đã xác minh và liên kết tài khoản." if decision == "approve"
        else "Đã từ chối yêu cầu liên kết.",
        "success",
    )
    return redirect(url_for("admin_portal.parent_link_requests"))

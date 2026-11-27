"""API Quản trị hệ thống (Admin): Tài khoản, phân quyền, Parent-Student, cấu hình, AuditLog."""

from contextlib import closing
import pyodbc
from flask import Blueprint, current_app, jsonify, request

from auth_utils import require_api_roles, serialize_rows
from database import _connection_string, _fetch_all

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _connect():
    return closing(pyodbc.connect(_connection_string(), timeout=5))


@bp.get("/overview")
def system_overview():
    _, err = require_api_roles("Admin")
    if err:
        return err

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            overview = _fetch_all(cur, "SELECT * FROM dbo.vw_SystemOverview")
            activity = _fetch_all(
                cur,
                "SELECT TOP 14 * FROM dbo.vw_PlatformActivityDaily ORDER BY ActivityDate DESC",
            )
        return jsonify(
            overview=serialize_rows(overview)[0] if overview else None,
            daily_activity=serialize_rows(activity),
        )
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải tổng quan hệ thống")
        return jsonify(error="Không thể tải dữ liệu từ SQL Server."), 503


@bp.get("/users")
def list_users():
    _, err = require_api_roles("Admin")
    if err:
        return err

    role_filter = (request.args.get("role") or "").strip()
    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            if role_filter:
                rows = _fetch_all(
                    cur,
                    "SELECT * FROM dbo.vw_UserDirectory WHERE RoleName = ? ORDER BY UserID",
                    (role_filter,),
                )
            else:
                rows = _fetch_all(cur, "SELECT * FROM dbo.vw_UserDirectory ORDER BY UserID")
        return jsonify(users=serialize_rows(rows))
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải danh sách người dùng")
        return jsonify(error="Không thể tải dữ liệu từ SQL Server."), 503


@bp.patch("/users/<int:user_id>/role")
def update_user_role(user_id):
    admin, err = require_api_roles("Admin")
    if err:
        return err

    data = request.get_json(silent=True)
    role_name = (data.get("role_name") or "").strip() if isinstance(data, dict) else ""
    if role_name not in {"Admin", "Teacher", "Student", "Parent"}:
        return jsonify(error="Vai trò không hợp lệ."), 400
    if user_id == admin["id"] and role_name != "Admin":
        return jsonify(error="Không thể tự hạ quyền của chính mình."), 400

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            cur.execute("SELECT RoleID FROM dbo.Roles WHERE RoleName = ?", (role_name,))
            role_row = cur.fetchone()
            if not role_row:
                return jsonify(error="Không tìm thấy vai trò trong hệ thống."), 404

            cur.execute("UPDATE dbo.Users SET RoleID = ? WHERE UserID = ?", (role_row[0], user_id))
            if cur.rowcount == 0:
                return jsonify(error="Không tìm thấy người dùng."), 404

            # Nếu chuyển sang Student mà chưa có hồ sơ thì tạo mặc định
            if role_name == "Student":
                cur.execute(
                    """
                    IF NOT EXISTS (SELECT 1 FROM dbo.StudentProfiles WHERE StudentID = ?)
                        INSERT INTO dbo.StudentProfiles (StudentID, TargetScore, DailyStudyMin)
                        VALUES (?, 0, 60)
                    """,
                    (user_id, user_id),
                )
            conn.commit()
        return jsonify(ok=True, user_id=user_id, role_name=role_name)
    except pyodbc.Error:
        current_app.logger.exception("Lỗi cập nhật vai trò người dùng")
        return jsonify(error="Không thể cập nhật vai trò."), 503


@bp.patch("/users/<int:user_id>/status")
def update_user_status(user_id):
    admin, err = require_api_roles("Admin")
    if err:
        return err

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("is_active"), bool):
        return jsonify(error="Cần truyền is_active dạng boolean (true/false)."), 400
    if user_id == admin["id"] and not data["is_active"]:
        return jsonify(error="Không thể tự khóa tài khoản của chính mình."), 400

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            cur.execute(
                "UPDATE dbo.Users SET IsActive = ? WHERE UserID = ?",
                (1 if data["is_active"] else 0, user_id),
            )
            if cur.rowcount == 0:
                return jsonify(error="Không tìm thấy người dùng."), 404
            conn.commit()
        return jsonify(ok=True, user_id=user_id, is_active=data["is_active"])
    except pyodbc.Error:
        current_app.logger.exception("Lỗi cập nhật trạng thái người dùng")
        return jsonify(error="Không thể cập nhật trạng thái tài khoản."), 503


@bp.post("/parent-student")
def link_parent_student():
    _, err = require_api_roles("Admin")
    if err:
        return err

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Dữ liệu không hợp lệ."), 400

    parent_id = data.get("parent_id")
    student_id = data.get("student_id")
    if not isinstance(parent_id, int) or not isinstance(student_id, int):
        return jsonify(error="parent_id và student_id phải là số nguyên."), 400

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            cur.execute(
                """
                SELECT 1 FROM dbo.Users u
                INNER JOIN dbo.Roles r ON r.RoleID = u.RoleID
                WHERE u.UserID = ? AND r.RoleName = N'Parent'
                """,
                (parent_id,),
            )
            if cur.fetchone() is None:
                return jsonify(error="Tài khoản phụ huynh không hợp lệ."), 400

            cur.execute("SELECT 1 FROM dbo.StudentProfiles WHERE StudentID = ?", (student_id,))
            if cur.fetchone() is None:
                return jsonify(error="Không tìm thấy hồ sơ học sinh."), 404

            cur.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.ParentStudent WHERE ParentID = ? AND StudentID = ?)
                    INSERT INTO dbo.ParentStudent (ParentID, StudentID) VALUES (?, ?)
                """,
                (parent_id, student_id, parent_id, student_id),
            )
            conn.commit()
        return jsonify(ok=True, parent_id=parent_id, student_id=student_id), 201
    except pyodbc.Error:
        current_app.logger.exception("Lỗi liên kết phụ huynh - học sinh")
        return jsonify(error="Không thể liên kết tài khoản."), 503


@bp.delete("/parent-student")
def unlink_parent_student():
    _, err = require_api_roles("Admin")
    if err:
        return err

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Dữ liệu không hợp lệ."), 400

    parent_id = data.get("parent_id")
    student_id = data.get("student_id")
    if not isinstance(parent_id, int) or not isinstance(student_id, int):
        return jsonify(error="parent_id và student_id phải là số nguyên."), 400

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            cur.execute(
                "DELETE FROM dbo.ParentStudent WHERE ParentID = ? AND StudentID = ?",
                (parent_id, student_id),
            )
            conn.commit()
        return jsonify(ok=True, deleted=cur.rowcount > 0)
    except pyodbc.Error:
        current_app.logger.exception("Lỗi hủy liên kết phụ huynh - học sinh")
        return jsonify(error="Không thể hủy liên kết."), 503


@bp.get("/settings")
def list_settings():
    _, err = require_api_roles("Admin")
    if err:
        return err

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            rows = _fetch_all(cur, "SELECT * FROM dbo.vw_SystemSettings ORDER BY SettingKey")
        return jsonify(settings=serialize_rows(rows))
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải cấu hình hệ thống")
        return jsonify(error="Không thể tải cấu hình từ SQL Server."), 503


@bp.put("/settings/<string:setting_key>")
def upsert_setting(setting_key):
    admin, err = require_api_roles("Admin")
    if err:
        return err

    key = setting_key.strip()
    data = request.get_json(silent=True)
    value = data.get("value") if isinstance(data, dict) else None
    if not key or len(key) > 100 or not isinstance(value, str) or len(value) > 500:
        return jsonify(error="Key hoặc giá trị cấu hình không hợp lệ."), 400

    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            cur.execute(
                """
                IF EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE SettingKey = ?)
                    UPDATE dbo.SystemSettings
                    SET SettingValue = ?, UpdatedBy = ?, UpdatedAt = SYSDATETIME()
                    WHERE SettingKey = ?
                ELSE
                    INSERT INTO dbo.SystemSettings (SettingKey, SettingValue, UpdatedBy)
                    VALUES (?, ?, ?)
                """,
                (key, value, admin["id"], key, key, value, admin["id"]),
            )
            conn.commit()
        return jsonify(ok=True, setting_key=key)
    except pyodbc.Error:
        current_app.logger.exception("Lỗi lưu cấu hình hệ thống")
        return jsonify(error="Không thể lưu cấu hình."), 503


@bp.get("/audit-logs")
def list_audit_logs():
    _, err = require_api_roles("Admin")
    if err:
        return err

    table_name = (request.args.get("table") or "").strip()
    action = (request.args.get("action") or "").strip().upper()
    try:
        limit = min(200, max(1, int(request.args.get("limit", 50))))
    except ValueError:
        limit = 50

    conditions, params = [], []
    if table_name:
        conditions.append("TableName = ?")
        params.append(table_name)
    if action in {"INSERT", "UPDATE", "DELETE"}:
        conditions.append("Action = ?")
        params.append(action)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    try:
        with _connect() as conn, closing(conn.cursor()) as cur:
            rows = _fetch_all(
                cur,
                f"SELECT TOP ({limit}) * FROM dbo.vw_AuditTrail {where_clause} ORDER BY AuditID DESC",
                tuple(params),
            )
        return jsonify(logs=serialize_rows(rows))
    except pyodbc.Error:
        current_app.logger.exception("Lỗi tải nhật ký kiểm toán")
        return jsonify(error="Không thể tải nhật ký kiểm toán."), 503
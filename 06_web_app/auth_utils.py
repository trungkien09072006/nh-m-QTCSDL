"""Tiện ích phân quyền API và chuẩn hóa JSON dùng chung cho 4 vai trò."""

from datetime import date, datetime
from decimal import Decimal
from flask import jsonify, session


def require_api_roles(*allowed_roles):
    """Trả về (user_dict, None) nếu hợp lệ, ngược lại trả (None, response_error)."""
    if "user_id" not in session:
        return None, (jsonify(error="Vui lòng đăng nhập."), 401)

    role = session.get("role")
    if allowed_roles and role not in allowed_roles:
        return None, (jsonify(error="Bạn không có quyền thực hiện chức năng này."), 403)

    return {
        "id": session["user_id"],
        "email": session.get("email"),
        "fullname": session.get("fullname"),
        "role": role,
    }, None


def serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_rows(rows):
    return [{k: serialize_value(v) for k, v in row.items()} for row in rows]
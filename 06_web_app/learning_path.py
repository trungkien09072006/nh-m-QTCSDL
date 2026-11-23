"""API Lộ trình học và Tiến độ cho học sinh (Phần 4)."""

import pyodbc
from flask import Blueprint, current_app, jsonify, request, session

import learning_path_service as service
from learning_path_service import LearningPathItemNotFound

bp = Blueprint("learning_path", __name__)


def _student_access():
    if "user_id" not in session:
        return None, (jsonify(error="Vui lòng đăng nhập."), 401)
    if session.get("role") != "Student":
        return None, (jsonify(error="Chức năng này chỉ dành cho học sinh."), 403)
    return session["user_id"], None


def _run(operation):
    try:
        return operation()
    except LearningPathItemNotFound:
        return jsonify(error="Không tìm thấy nhiệm vụ trong lộ trình của bạn."), 404
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except pyodbc.Error:
        current_app.logger.exception("Lỗi SQL Server trong module lộ trình học")
        return jsonify(error="Không thể xử lý lộ trình học từ SQL Server."), 503


@bp.get("/api/learning-path")
def api_get_learning_path():
    student_id, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(service.get_learning_path(student_id)))


@bp.patch("/api/learning-path/items/<int:item_id>/status")
def api_update_item_status(item_id):
    student_id, error = _student_access()
    if error:
        return error

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("status"), str):
        return jsonify(error="Vui lòng gửi trạng thái nhiệm vụ hợp lệ."), 400

    status = data["status"].strip().upper()
    return _run(lambda: jsonify(service.update_item_status(student_id, item_id, status)))
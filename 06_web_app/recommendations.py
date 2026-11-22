"""API gợi ý học và dự đoán điểm cho học sinh (phần 2).

Đăng ký trong app.py (người 4 ghép project):
    from recommendations import bp as recommendations_bp
    app.register_blueprint(recommendations_bp)
"""

import pyodbc
from flask import Blueprint, current_app, jsonify, request, session

import recommendation_service as service
from recommendation_service import RecommendationNotFound, StudentProfileNotFound

bp = Blueprint("recommendations", __name__)


def _student_access():
    if "user_id" not in session:
        return None, (jsonify(error="Vui lòng đăng nhập."), 401)
    if session.get("role") != "Student":
        return None, (jsonify(error="Chức năng này chỉ dành cho học sinh."), 403)
    return session["user_id"], None


def _run(operation):
    try:
        return operation()
    except RecommendationNotFound:
        return jsonify(error="Không tìm thấy gợi ý."), 404
    except StudentProfileNotFound:
        return jsonify(error="Chưa có hồ sơ học sinh. Hãy cập nhật hồ sơ trước."), 404
    except pyodbc.Error:
        current_app.logger.exception("Lỗi SQL Server trong module gợi ý và dự đoán")
        return jsonify(error="Không thể xử lý gợi ý hoặc dự đoán từ SQL Server."), 503


@bp.get("/api/recommendations")
def api_recommendations():
    student_id, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(service.list_recommendations(student_id)))


@bp.post("/api/recommendations/generate")
def api_generate_recommendations():
    student_id, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(service.generate_recommendations(student_id)))


@bp.post("/api/recommendations/<int:rec_id>/respond")
def api_respond_recommendation(rec_id):
    student_id, error = _student_access()
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("accepted"), bool):
        return jsonify(error="Cần cho biết bạn chấp nhận (true) hay bỏ qua (false) gợi ý."), 400
    return _run(
        lambda: jsonify(service.respond_to_recommendation(student_id, rec_id, data["accepted"]))
    )


@bp.get("/api/predictions/latest")
def api_latest_prediction():
    student_id, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(service.get_prediction_overview(student_id)))


@bp.post("/api/predictions/refresh")
def api_refresh_prediction():
    student_id, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(service.refresh_prediction(student_id)))

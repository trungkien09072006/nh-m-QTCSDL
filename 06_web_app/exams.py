import pyodbc
from flask import Blueprint, current_app, jsonify, request, session

import exam_service
from exam_service import AttemptExpired, AttemptNotFound, AttemptSubmitted, ExamNotFound

bp = Blueprint("exams", __name__)


def _student_access():
    if "user_id" not in session:
        return None, (jsonify(error="Vui lòng đăng nhập."), 401)
    if session.get("role") != "Student":
        return None, (jsonify(error="Chức năng này chỉ dành cho học sinh."), 403)
    return session["user_id"], None


def _error_response(error):
    if isinstance(error, (ExamNotFound, AttemptNotFound)):
        return jsonify(error="Không tìm thấy đề thi hoặc lượt làm bài."), 404
    if isinstance(error, AttemptSubmitted):
        return jsonify(error="Lượt thi này đã được nộp."), 409
    if isinstance(error, AttemptExpired):
        return jsonify(error="Đã hết giờ làm bài."), 409
    if isinstance(error, ValueError):
        return jsonify(error=str(error)), 400
    if isinstance(error, pyodbc.Error):
        current_app.logger.exception("Lỗi SQL Server trong luồng làm bài thi")
        return jsonify(error="Không thể xử lý bài thi từ SQL Server."), 503
    raise error


def _run(operation):
    try:
        return operation()
    except (
        ExamNotFound,
        AttemptNotFound,
        AttemptSubmitted,
        AttemptExpired,
        ValueError,
        pyodbc.Error,
    ) as error:
        return _error_response(error)


def _positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _parse_answers(data):
    if not isinstance(data, dict) or not isinstance(data.get("answers"), list):
        raise ValueError("Danh sách câu trả lời không hợp lệ.")
    answers = {}
    for item in data["answers"]:
        if not isinstance(item, dict):
            raise ValueError("Câu trả lời không hợp lệ.")
        question_id = item.get("question_id")
        option_id = item.get("option_id")
        if not _positive_int(question_id) or not _positive_int(option_id):
            raise ValueError("Mỗi câu trả lời cần mã câu hỏi và lựa chọn hợp lệ.")
        if question_id in answers:
            raise ValueError("Không được gửi trùng câu trả lời.")
        answers[question_id] = option_id
    return answers


@bp.get("/api/exams")
def api_exams():
    _, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(exams=exam_service.list_exams()))


@bp.post("/api/exams/<int:exam_id>/attempts")
def api_start_attempt(exam_id):
    student_id, error = _student_access()
    if error:
        return error
    return _run(
        lambda: (jsonify(exam_service.start_attempt(student_id, exam_id)), 201)
    )


@bp.get("/api/exam-attempts/<int:attempt_id>")
def api_get_attempt(attempt_id):
    student_id, error = _student_access()
    if error:
        return error
    return _run(lambda: jsonify(attempt=exam_service.get_attempt(student_id, attempt_id)))


@bp.post("/api/exam-attempts/<int:attempt_id>/answers")
def api_save_attempt_answers(attempt_id):
    student_id, error = _student_access()
    if error:
        return error

    try:
        answers = _parse_answers(request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    def save():
        exam_service.save_attempt_answers(student_id, attempt_id, answers)
        return jsonify(saved=True)

    return _run(save)


@bp.post("/api/exam-attempts/<int:attempt_id>/submit")
def api_submit_attempt(attempt_id):
    student_id, error = _student_access()
    if error:
        return error

    try:
        answers = _parse_answers(request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    return _run(
        lambda: jsonify(
            attempt=exam_service.submit_attempt(student_id, attempt_id, answers)
        )
    )

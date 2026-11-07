import os
from datetime import datetime

import pyodbc
from flask import Flask, redirect, render_template, request, url_for

from database import (
    ask_ai_tutor,
    load_dashboard_data,
    mark_notifications_read,
    refresh_ai_insights,
    respond_to_recommendation,
)


app = Flask(__name__)


def _current_student_email() -> str:
    return os.getenv("STUDENT_EMAIL", "student1@gmail.com")


@app.get("/")
def dashboard():
    student_email = _current_student_email()
    current_date = datetime.now().strftime("%d/%m/%Y")

    try:
        data = load_dashboard_data(student_email)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể tải dashboard NovaPath từ SQL Server")
        return (
            render_template(
                "dashboard.html",
                dashboard=None,
                student_email=student_email,
                current_date=current_date,
                db_error=(
                    "Không thể kết nối SQL Server. Hãy kiểm tra cấu hình kết nối, "
                    "ODBC Driver và trạng thái dịch vụ SQL Server."
                ),
            ),
            503,
        )

    return render_template(
        "dashboard.html",
        dashboard=data,
        student_email=student_email,
        current_date=current_date,
        db_error=None,
    )


@app.post("/ai/refresh")
def trigger_ai_refresh():
    student_email = _current_student_email()
    try:
        refresh_ai_insights(student_email)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể cập nhật phân tích AI")
    return redirect(url_for("dashboard") + "#goi-y")


@app.post("/recommendations/<int:rec_id>/respond")
def handle_recommendation_response(rec_id: int):
    student_email = _current_student_email()
    action = request.form.get("action", "accept")
    accepted = action == "accept"
    try:
        respond_to_recommendation(student_email, rec_id, accepted)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể cập nhật trạng thái gợi ý")
    return redirect(url_for("dashboard") + "#goi-y")


@app.post("/tutor/ask")
def handle_tutor_question():
    student_email = _current_student_email()
    message_content = request.form.get("message", "")
    raw_question_id = request.form.get("question_id", "").strip()
    question_id = int(raw_question_id) if raw_question_id.isdigit() else None

    try:
        ask_ai_tutor(student_email, message_content, question_id)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể gửi câu hỏi tới AI Tutor")
    return redirect(url_for("dashboard") + "#tro-ly-ai")


@app.post("/notifications/read")
def handle_notifications_read():
    student_email = _current_student_email()
    raw_id = request.form.get("notification_id", "").strip()
    notification_id = int(raw_id) if raw_id.isdigit() else None
    try:
        mark_notifications_read(student_email, notification_id)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể cập nhật trạng thái thông báo")
    return redirect(url_for("dashboard") + "#thong-bao")


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() == "true",
    )
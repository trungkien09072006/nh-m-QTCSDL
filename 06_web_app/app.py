import os
from datetime import datetime

import pyodbc
from flask import Flask, render_template

from database import load_dashboard_data


app = Flask(__name__)


@app.get("/")
def dashboard():
    student_email = os.getenv("STUDENT_EMAIL", "student1@gmail.com")
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


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() == "true",
    )

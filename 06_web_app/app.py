import os
import secrets
import hmac
from datetime import datetime
from functools import wraps

import pyodbc
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from database import (
    get_student_profile,
    load_dashboard_data,
    register_user,
    update_student_profile,
    verify_login,
)

from content import bp as content_bp

app = Flask(__name__)
app.register_blueprint(content_bp)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        expected = session.get("_csrf_token")
        submitted = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(
            expected.encode("utf-8"), submitted.encode("utf-8")
        ):
            abort(400)


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        token = session.get("_csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    return {"csrf_token": csrf_token}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') != role:
                flash("Bạn không có quyền truy cập trang này.", "error")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        user = verify_login(email, password)

        if user:
            session.clear()
            session['user_id'] = user['UserID']
            session['email'] = user['Email']
            session['fullname'] = user['FullName']
            session['role'] = user['RoleName']

            if user['RoleName'] in ('Teacher', 'Admin'):
                return redirect(url_for('content.listing'))
            if user['RoleName'] == 'Student':
                return redirect(url_for('dashboard'))
            else:
                flash(f"Đăng nhập thành công với vai trò {user['RoleName']}. Tính năng đang phát triển.", "success")
                return redirect(url_for('login'))

        flash("Email hoặc mật khẩu không đúng.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        fullname = (request.form.get("fullname") or "").strip()

        if (
            not email
            or len(email) > 150
            or not fullname
            or len(fullname) > 100
            or len(password) < 8
            or len(password) > 128
        ):
            flash(
                "Vui lòng nhập email, họ tên hợp lệ và mật khẩu từ 8 đến 128 ký tự.",
                "error",
            )
            return render_template("register.html"), 400

        if register_user(email, password, fullname):
            flash("Đăng ký thành công, vui lòng đăng nhập.", "success")
            return redirect(url_for('login'))
        flash("Email đã tồn tại hoặc có lỗi xảy ra.", "error")
    return render_template("register.html")


@app.get("/")
@login_required
@role_required("Student")
def dashboard():
    user_id = session['user_id']
    current_date = datetime.now().strftime("%d/%m/%Y")

    try:
        data = load_dashboard_data(user_id)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể tải dashboard NovaPath từ SQL Server")
        return (
            render_template(
                "dashboard.html",
                dashboard=None,
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
        current_date=current_date,
        db_error=None,
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("Student")
def profile():
    user_id = session['user_id']
    if request.method == "POST":
        fullname = (request.form.get("fullname") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        school = (request.form.get("school") or "").strip()
        exam_date = request.form.get("exam_date") or ""

        try:
            target_score = int(request.form.get("target_score") or "")
            daily_study_min = int(request.form.get("daily_study_min") or "")
            if exam_date:
                datetime.strptime(exam_date, "%Y-%m-%d")
        except ValueError:
            flash("Điểm mục tiêu, thời lượng học hoặc ngày thi không hợp lệ.", "error")
            return redirect(url_for("profile"))

        if (
            not fullname
            or len(fullname) > 100
            or len(phone) > 15
            or len(school) > 150
            or not 0 <= target_score <= 1200
            or daily_study_min <= 0
        ):
            flash("Vui lòng kiểm tra lại thông tin hồ sơ.", "error")
            return redirect(url_for("profile"))

        update_student_profile(
            user_id,
            fullname,
            phone or None,
            school or None,
            target_score,
            exam_date,
            daily_study_min,
        )
        session['fullname'] = fullname
        flash("Cập nhật hồ sơ thành công.", "success")
        return redirect(url_for('profile'))

    user_profile = get_student_profile(user_id)
    return render_template("profile.html", profile=user_profile)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() == "true",
    )

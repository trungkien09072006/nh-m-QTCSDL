import os
import secrets
import hmac
from datetime import date, datetime
from functools import wraps

import pyodbc
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

from database import (
    get_student_profile,
    load_dashboard_data,
    register_user,
    update_student_profile,
    verify_login,
)

from content import bp as content_bp
from exams import bp as exams_bp
from recommendations import bp as recommendations_bp
from tutor_api import bp as tutor_bp
from learning_path import bp as learning_path_bp
from parent_api import bp as parent_bp
from admin_api import bp as admin_bp

app = Flask(__name__)
app.register_blueprint(content_bp)
app.register_blueprint(exams_bp)
app.register_blueprint(recommendations_bp)
app.register_blueprint(tutor_bp)
app.register_blueprint(learning_path_bp)
app.register_blueprint(parent_bp)
app.register_blueprint(admin_bp)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


@app.before_request
def protect_post_requests():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = session.get("_csrf_token")
        submitted = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(
            expected.encode("utf-8"), submitted.encode("utf-8")
        ):
            abort(400)


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": _csrf_token}


def _csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _api_user():
    if "user_id" not in session:
        return None, (jsonify(error="Vui lòng đăng nhập."), 401)
    if session.get("role") != "Student":
        return None, (jsonify(error="Ứng dụng Vite hiện hỗ trợ tài khoản học sinh."), 403)
    return {
        "id": session["user_id"],
        "email": session.get("email"),
        "fullname": session.get("fullname"),
        "role": session.get("role"),
    }, None


@app.get("/api/csrf-token")
def api_csrf_token():
    return jsonify(csrf_token=_csrf_token())


@app.get("/api/session")
def api_session():
    if "user_id" not in session:
        return jsonify(user=None)
    return jsonify(
        user={
            "id": session["user_id"],
            "email": session.get("email"),
            "fullname": session.get("fullname"),
            "role": session.get("role"),
        }
    )


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Dữ liệu đăng nhập không hợp lệ."), 400
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify(error="Vui lòng nhập email và mật khẩu hợp lệ."), 400
    try:
        user = verify_login(email.strip(), password)
    except pyodbc.Error:
        app.logger.exception("Không thể xác thực NovaPath qua Vite API")
        return jsonify(error="Không thể kết nối SQL Server để đăng nhập."), 503

    if not user:
        return jsonify(error="Email hoặc mật khẩu không đúng."), 401
    if user["RoleName"] not in {"Student", "Parent", "Teacher", "Admin"}:
        return jsonify(error="Vai trò tài khoản không được hỗ trợ."), 403

    session.clear()
    session["user_id"] = user["UserID"]
    session["email"] = user["Email"]
    session["fullname"] = user["FullName"]
    session["role"] = user["RoleName"]
    return jsonify(
        user={
            "id": user["UserID"],
            "email": user["Email"],
            "fullname": user["FullName"],
            "role": user["RoleName"],
        },
        csrf_token=_csrf_token(),
    )


@app.post("/api/logout")
def api_logout():
    session.clear()
    session["_csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(ok=True, csrf_token=session["_csrf_token"])


@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Dữ liệu đăng ký không hợp lệ."), 400
    email = data.get("email")
    password = data.get("password")
    fullname = data.get("fullname")
    if (
        not isinstance(email, str)
        or not email.strip()
        or len(email) > 150
        or not isinstance(fullname, str)
        or not fullname.strip()
        or len(fullname) > 100
        or not isinstance(password, str)
        or len(password) < 8
        or len(password) > 128
    ):
        return (
            jsonify(error="Vui lòng nhập email, họ tên hợp lệ và mật khẩu từ 8 đến 128 ký tự."),
            400,
        )
    try:
        registered = register_user(email.strip(), password, fullname.strip())
    except pyodbc.Error:
        app.logger.exception("Không thể đăng ký NovaPath qua Vite API")
        return jsonify(error="Không thể kết nối SQL Server để đăng ký."), 503
    if not registered:
        return jsonify(error="Email đã tồn tại hoặc có lỗi xảy ra."), 409
    return jsonify(message="Đăng ký thành công, vui lòng đăng nhập."), 201


@app.get("/api/dashboard")
def api_dashboard():
    user, error = _api_user()
    if error:
        return error
    try:
        return jsonify(load_dashboard_data(user["id"]))
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể tải dashboard NovaPath qua Vite API")
        return jsonify(error="Không thể tải dữ liệu từ SQL Server."), 503


@app.get("/api/profile")
def api_profile():
    user, error = _api_user()
    if error:
        return error
    try:
        profile = get_student_profile(user["id"])
        if profile and isinstance(profile.get("ExamDate"), (date, datetime)):
            profile["ExamDate"] = profile["ExamDate"].strftime("%Y-%m-%d")
        return jsonify(profile)
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể tải hồ sơ NovaPath qua Vite API")
        return jsonify(error="Không thể tải hồ sơ từ SQL Server."), 503


@app.put("/api/profile")
def api_update_profile():
    user, error = _api_user()
    if error:
        return error

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Dữ liệu hồ sơ không hợp lệ."), 400
    fullname = data.get("fullname")
    phone = data.get("phone", "")
    school = data.get("school", "")
    if not all(isinstance(value, str) for value in (fullname, phone, school)):
        return jsonify(error="Họ tên, số điện thoại hoặc trường học không hợp lệ."), 400
    fullname = fullname.strip()
    phone = phone.strip()
    school = school.strip()
    exam_date = data.get("exam_date") or ""
    try:
        target_score = int(data.get("target_score", ""))
        daily_study_min = int(data.get("daily_study_min", ""))
        if exam_date:
            datetime.strptime(exam_date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return jsonify(error="Điểm mục tiêu, thời lượng học hoặc ngày thi không hợp lệ."), 400

    if (
        not fullname
        or len(fullname) > 100
        or len(phone) > 15
        or len(school) > 150
        or not 0 <= target_score <= 1200
        or daily_study_min <= 0
    ):
        return jsonify(error="Vui lòng kiểm tra lại thông tin hồ sơ."), 400

    try:
        update_student_profile(
            user["id"],
            fullname,
            phone or None,
            school or None,
            target_score,
            exam_date,
            daily_study_min,
        )
    except (pyodbc.Error, ValueError):
        app.logger.exception("Không thể cập nhật hồ sơ NovaPath qua Vite API")
        return jsonify(error="Không thể lưu hồ sơ vào SQL Server."), 503

    session["fullname"] = fullname
    return jsonify(message="Cập nhật hồ sơ thành công.", fullname=fullname)


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
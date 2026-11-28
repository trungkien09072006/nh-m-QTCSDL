import hashlib
import unittest
from unittest.mock import MagicMock, patch

import pyodbc
import database

import app as web_app
from database import _hash_password, _verify_password


class NovaPathRouteTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="test-key")
        self.client = web_app.app.test_client()
        for path in ("/", "/login/parent", "/login/teacher", "/admin"):
            with self.client.session_transaction(path) as session:
                session["_csrf_token"] = "test-csrf-token"

    def test_dashboard_requires_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_post_without_csrf_token_is_rejected(self):
        with patch("app.verify_login") as verify_login:
            response = self.client.post(
                "/login",
                data={"email": "student@example.test", "password": "password"},
            )

        self.assertEqual(response.status_code, 400)
        verify_login.assert_not_called()

    def test_logout_requires_post_and_clears_session(self):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student")

        response = self.client.post(
            "/logout",
            data={"csrf_token": "test-csrf-token"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_password_hash_supports_new_and_seed_hashes(self):
        password = "seed-password"
        new_hash = _hash_password(password)
        legacy_hash = hashlib.sha256(password.encode("utf-16le")).digest()

        self.assertTrue(_verify_password(new_hash, password)[0])
        self.assertFalse(_verify_password(new_hash, "wrong-password")[0])
        self.assertEqual(_verify_password(legacy_hash, password), (True, True))
        self.assertEqual(_verify_password(legacy_hash, "wrong-password"), (False, True))

    def test_role_restricted_routes_redirect_other_roles(self):
        with self.client.session_transaction() as session:
            session.update(user_id=2, role="Teacher")

        response = self.client.get("/profile")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    @patch("app.verify_login")
    def test_login_success(self, verify_login):
        with self.client.session_transaction() as session:
            session["stale_value"] = "remove after authentication"
        verify_login.return_value = {
            "UserID": 3,
            "Email": "student1@gmail.com",
            "FullName": "Trần Văn Học",
            "RoleName": "Student",
        }

        response = self.client.post(
            "/login",
            data={
                "csrf_token": "test-csrf-token",
                "email": "student1@gmail.com",
                "password": "valid-password",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.location)
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], 3)
            self.assertEqual(session["role"], "Student")
            self.assertNotIn("stale_value", session)

    def test_role_specific_login_pages_render(self):
        for portal, label in (
            ("student", "học sinh"),
            ("parent", "phụ huynh"),
            ("teacher", "giáo viên"),
        ):
            with self.subTest(portal=portal):
                response = self.client.get(f"/login/{portal}")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"Đăng nhập · {label}", response.get_data(as_text=True))

    @patch("app.verify_login")
    def test_role_specific_login_rejects_another_role(self, verify_login):
        verify_login.return_value = {
            "UserID": 3,
            "Email": "student1@gmail.com",
            "FullName": "Trần Văn Học",
            "RoleName": "Student",
        }

        response = self.client.post(
            "/login/teacher",
            data={
                "csrf_token": "test-csrf-token",
                "email": "student1@gmail.com",
                "password": "valid-password",
            },
        )

        self.assertEqual(response.status_code, 403)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    @patch("app.verify_login")
    def test_teacher_login_redirects_to_assigned_students(self, verify_login):
        verify_login.return_value = {
            "UserID": 2,
            "Email": "teacher@ai-edu.vn",
            "FullName": "Giáo viên",
            "RoleName": "Teacher",
        }

        response = self.client.post(
            "/login/teacher",
            data={
                "csrf_token": "test-csrf-token",
                "email": "teacher@ai-edu.vn",
                "password": "valid-password",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/teacher/students"))

    @patch("app.verify_login")
    def test_admin_login_via_shared_portal_points_to_separate_login(self, verify_login):
        verify_login.return_value = {
            "UserID": 1,
            "Email": "admin@ai-edu.vn",
            "FullName": "Quản trị viên",
            "RoleName": "Admin",
        }

        response = self.client.post(
            "/login",
            data={
                "csrf_token": "test-csrf-token",
                "email": "admin@ai-edu.vn",
                "password": "valid-password",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("cổng Admin riêng", response.get_data(as_text=True))
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_registration_rejects_weak_password_before_database_access(self):
        with patch("app.register_user") as register_user:
            response = self.client.post(
                "/register",
                data={
                    "csrf_token": "test-csrf-token",
                    "email": "new@student.test",
                    "fullname": "New Student",
                    "password": "short",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("mật khẩu từ 8 đến 128 ký tự", response.get_data(as_text=True))
        register_user.assert_not_called()

    @patch("app.update_student_profile")
    def test_profile_rejects_invalid_score_without_database_write(self, update_profile):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student")

        response = self.client.post(
            "/profile",
            data={
                "csrf_token": "test-csrf-token",
                "fullname": "Student",
                "target_score": "not-a-number",
                "daily_study_min": "60",
            },
        )

        self.assertEqual(response.status_code, 302)
        update_profile.assert_not_called()

    @patch("app.load_dashboard_data")
    def test_dashboard_renders_student_data(self, load_data):
        with self.client.session_transaction() as session:
            session.update(
                user_id=3,
                role="Student",
                fullname="Trần Văn Học",
            )
        load_data.return_value = {
            "student": {
                "FullName": "Trần Văn Học",
                "TargetScore": 950,
                "DailyStudyMin": 120,
                "ExamDate": "15/06/2027",
            },
            "weekly_minutes": 180,
            "latest_exam": {"title": "Đề thi thử ĐGNL", "score": 50},
            "prediction": {"score": 880.5, "probability": 0.65},
            "competencies": [
                {
                    "SubjectName": "Định lượng",
                    "CompetencyName": "Đại số",
                    "MasteryPercent": 20,
                }
            ],
            "tasks": [],
            "recommendations": [],
            "exams": [],
        }

        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Chào Học", html)
        self.assertIn("950", html)
        self.assertIn("20%", html)
        self.assertNotIn("Yêu cầu liên kết phụ huynh", html)
        self.assertIn("mobile-logout", html)
        load_data.assert_called_once_with(3)

    @patch("app.load_dashboard_data")
    def test_missing_student_shows_setup_message(self, load_data):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student", fullname="Trần Văn Học")
        load_data.return_value = {
            "student": None,
            "weekly_minutes": 0,
            "latest_exam": None,
            "prediction": None,
            "competencies": [],
            "tasks": [],
            "recommendations": [],
            "exams": [],
        }

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Chưa tìm thấy hồ sơ chi tiết", response.get_data(as_text=True))

    @patch("app.load_dashboard_data", side_effect=pyodbc.Error("database unavailable"))
    def test_database_error_is_reported(self, _load_data):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student", fullname="Trần Văn Học")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("Chưa tải được dữ liệu học tập", response.get_data(as_text=True))
        self.assertIn("SQL Server", response.get_data(as_text=True))


class RegisterUserTests(unittest.TestCase):
    @patch("database.pyodbc.connect")
    def test_student_profile_uses_user_id_returned_by_insert(self, connect):
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.side_effect = [(4,), (73,)]
        cursor.description = None

        def advance_to_inserted_id():
            cursor.description = (("UserID",),)
            return True

        cursor.nextset.side_effect = advance_to_inserted_id

        registered = database.register_user(
            "student@example.test",
            "valid-password",
            "Test Student",
        )

        self.assertTrue(registered)
        self.assertEqual(cursor.execute.call_count, 3)
        insert_sql = cursor.execute.call_args_list[1].args[0]
        self.assertIn("OUTPUT INSERTED.UserID INTO @InsertedUsers", insert_sql)
        self.assertNotIn("SCOPE_IDENTITY", insert_sql)
        self.assertEqual(cursor.execute.call_args_list[2].args[1], (73,))
        cursor.nextset.assert_called_once()
        connect.return_value.commit.assert_called_once()


class PortalRouteTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="portal-test-key")
        self.client = web_app.app.test_client()
        for path in ("/", "/login/parent", "/login/teacher", "/admin"):
            with self.client.session_transaction(path) as session:
                session["_csrf_token"] = "portal-csrf-token"

    def login_as(self, role, user_id=4):
        paths = {
            "Parent": "/parent",
            "Teacher": "/teacher",
            "Admin": "/admin",
        }
        with self.client.session_transaction(paths.get(role, "/")) as session:
            session.update(user_id=user_id, role=role, fullname="Người dùng")

    def csrf(self):
        return {"csrf_token": "portal-csrf-token"}

    def test_parent_dashboard_requires_parent_role(self):
        self.login_as("Student")

        response = self.client.get("/parent")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/parent", response.location)

    def test_parent_registration_page_renders(self):
        response = self.client.get("/parent/register")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Tạo tài khoản phụ huynh", response.get_data(as_text=True))

    @patch("app.verify_login")
    def test_parent_login_redirects_to_parent_dashboard(self, verify_login):
        verify_login.return_value = {
            "UserID": 9,
            "Email": "parent@example.test",
            "FullName": "Parent",
            "RoleName": "Parent",
        }

        response = self.client.post(
            "/login/parent",
            data={
                **self.csrf(),
                "email": "parent@example.test",
                "password": "valid-password",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/parent", response.location)

    @patch("parent_portal.register_user", return_value=True)
    def test_parent_registration_creates_parent_role(self, register):
        response = self.client.post(
            "/parent/register",
            data={
                **self.csrf(),
                "fullname": "Parent",
                "email": "parent@example.test",
                "password": "valid-password",
            },
        )

        self.assertEqual(response.status_code, 302)
        register.assert_called_once_with(
            "parent@example.test", "valid-password", "Parent", role_name="Parent"
        )

    @patch("parent_portal._fetch_all", side_effect=[
        [{"StudentName": "Học sinh", "TargetScore": 900, "PredictedScore": 800}],
        [],
        [],
    ])
    @patch("parent_portal.pyodbc.connect")
    def test_parent_dashboard_uses_parent_views(self, connect, fetch_all):
        self.login_as("Parent")

        response = self.client.get("/parent")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Học sinh", response.get_data(as_text=True))
        self.assertEqual(fetch_all.call_count, 3)
        self.assertEqual(fetch_all.call_args_list[0].args[2], (4,))
        self.assertEqual(fetch_all.call_args_list[1].args[2], (4,))
        self.assertTrue(connect.called)

    @patch("parent_portal.pyodbc.connect")
    def test_parent_link_request_waits_for_school_verification(self, connect):
        self.login_as("Parent", user_id=4)
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.side_effect = [(8,), None, None]

        response = self.client.post(
            "/parent/link-requests",
            data={**self.csrf(), "student_email": "student@example.test"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(cursor.execute.call_count, 4)
        self.assertEqual(cursor.execute.call_args_list[-1].args[1], (4, 8))
        connect.return_value.commit.assert_called_once()

    @patch("parent_portal.pyodbc.connect")
    def test_parent_link_request_does_not_reveal_unknown_student_email(self, connect):
        self.login_as("Parent")
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.return_value = None

        response = self.client.post(
            "/parent/link-requests",
            data={**self.csrf(), "student_email": "unknown@example.test"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("nhà trường xác minh", response.get_data(as_text=True))
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(len(statements), 4)
        self.assertIn("LOWER(u.Email)", statements[0])
        self.assertFalse(any("INSERT INTO dbo.ParentLinkRequests" in sql for sql in statements))
        connect.return_value.commit.assert_not_called()

    @patch("parent_portal.pyodbc.connect")
    def test_parent_link_request_requires_csrf(self, connect):
        self.login_as("Parent")

        response = self.client.post(
            "/parent/link-requests",
            data={"student_email": "student@example.test"},
        )

        self.assertEqual(response.status_code, 400)
        connect.assert_not_called()

    @patch("parent_portal.pyodbc.connect")
    def test_student_cannot_approve_parent_link_request(self, connect):
        self.login_as("Student", user_id=8)

        response = self.client.post(
            "/parent/link-requests/3/respond",
            data={**self.csrf(), "decision": "accept"},
        )

        self.assertEqual(response.status_code, 404)
        connect.assert_not_called()

    @patch("parent_portal.pyodbc.connect", side_effect=pyodbc.Error("unavailable"))
    def test_parent_dashboard_reports_database_failure(self, _connect):
        self.login_as("Parent")

        response = self.client.get("/parent")

        self.assertEqual(response.status_code, 503)
        self.assertIn("Không thể tải dữ liệu phụ huynh", response.get_data(as_text=True))

    def test_teacher_analytics_denies_student(self):
        self.login_as("Student")

        response = self.client.get("/teacher/analytics")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/teacher", response.location)

    @patch("content.pyodbc.connect", side_effect=pyodbc.Error("unavailable"))
    def test_teacher_analytics_reports_database_failure(self, _connect):
        self.login_as("Teacher")

        response = self.client.get("/teacher/analytics")

        self.assertEqual(response.status_code, 503)
        self.assertIn("view phân tích", response.get_data(as_text=True))

    @patch("content._fetch_all", side_effect=[
        [{"QualityAssessment": "Đạt", "QuestionCount": 8, "NeedsReviewCount": 0}],
        [{"RecommendationType": "Học liệu", "TotalRecommendations": 5, "AcceptedCount": 2, "AcceptedPercent": 40}],
        [],
    ])
    @patch("content.pyodbc.connect")
    def test_teacher_analytics_renders_sql_view_summaries(self, _connect, fetch_all):
        self.login_as("Teacher")

        response = self.client.get("/teacher/analytics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Chất lượng câu hỏi", response.get_data(as_text=True))
        self.assertIn("Xếp hạng bài thi", response.get_data(as_text=True))
        self.assertEqual(fetch_all.call_count, 3)


class TutorRegressionTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="tutor-regression-key")
        self.client = web_app.app.test_client()
        self.csrf_token = self.client.get("/api/csrf-token").get_json()["csrf_token"]
        with self.client.session_transaction() as session:
            session.update(user_id=3, email="student@test.local", role="Student")

    def test_history_reads_session_messages_before_closing_cursor(self):
        with patch("tutor_api.pyodbc.connect") as connect:
            connection = MagicMock()
            cursor = MagicMock()
            connect.return_value = connection
            connection.cursor.return_value = cursor
            cursor_state = {"closed": False}
            cursor.close.side_effect = lambda: cursor_state.update(closed=True)

            def execute(sql, *args, **kwargs):
                if cursor_state["closed"]:
                    raise AssertionError("query executed after cursor was closed")
                if "SELECT TOP 1 SessionID" in sql:
                    cursor.description = [("SessionID",), ("StartedAt",)]
                else:
                    cursor.description = [("id",), ("sender",), ("content",)]

            cursor.execute.side_effect = execute
            cursor.fetchone.return_value = (10, "2026-11-20 10:00:00")
            cursor.fetchall.return_value = [(1, "USER", "Em chưa hiểu câu này")]

            response = self.client.get("/api/tutor/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["session_id"], 10)
        self.assertEqual(response.get_json()["messages"][0]["content"], "Em chưa hiểu câu này")

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_ask_creates_tutor_session_from_inserted_id(self):
        with patch("tutor_api.pyodbc.connect") as connect:
            connection = MagicMock()
            cursor = MagicMock()
            connect.return_value = connection
            connection.cursor.return_value = cursor
            cursor.fetchone.side_effect = [
                (1, "Cho dãy số 2, 6, 12...", 3, "Quy luật n*(n+1)", "Tư duy logic"),
                (1, "Cho dãy số 2, 6, 12...", 3, "Quy luật n*(n+1)", "Tư duy logic"),
                None,
                (10,),
            ]
            cursor.fetchall.side_effect = [
                [("A", "40", 0), ("B", "42", 1)],
                [("A", "40", 0), ("B", "42", 1)],
            ]
            cursor.description = [
                ("QuestionID",), ("Content",), ("Difficulty",), ("Explanation",), ("CompetencyName",)
            ]

            response = self.client.post(
                "/api/tutor/ask",
                json={"message": "Giải thích chi tiết giúp em câu này", "question_id": 1},
                headers={"X-CSRF-Token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["session_id"], 10)
        self.assertIn("Giải thích chi tiết cho câu hỏi", data["reply"])
        self.assertTrue(any(
            "OUTPUT INSERTED.SessionID" in str(call.args[0])
            for call in cursor.execute.call_args_list
        ))
        connection.commit.assert_called_once()

    def test_clear_tutor_session_uses_inserted_id(self):
        with patch("tutor_api.pyodbc.connect") as connect:
            connection = MagicMock()
            cursor = MagicMock()
            connect.return_value = connection
            connection.cursor.return_value = cursor
            cursor.fetchone.return_value = (99,)

            response = self.client.post(
                "/api/tutor/clear",
                headers={"X-CSRF-Token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["session_id"], 99)
        self.assertIn("OUTPUT INSERTED.SessionID", cursor.execute.call_args.args[0])
        connection.commit.assert_called_once()


class TeacherPortalTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="teacher-portal-test-key")
        self.client = web_app.app.test_client()
        with self.client.session_transaction("/teacher") as session:
            session.update(user_id=12, role="Teacher", fullname="Giáo viên")
            session["_csrf_token"] = "teacher-csrf-token"

    def test_student_cannot_open_teacher_student_list(self):
        with self.client.session_transaction("/teacher") as session:
            session["role"] = "Student"

        response = self.client.get("/teacher/students")

        self.assertEqual(response.status_code, 403)

    @patch("content.pyodbc.connect", side_effect=pyodbc.Error("missing migration"))
    def test_teacher_database_error_does_not_show_empty_student_state(self, _connect):
        response = self.client.get("/teacher/students")

        self.assertEqual(response.status_code, 503)
        html = response.get_data(as_text=True)
        self.assertIn("01_schema/06_teacher_student_migration.sql", html)
        self.assertNotIn("Chưa có học sinh được phân công", html)

    @patch("content._fetch_all", return_value=[
        {
            "StudentID": 3,
            "FullName": "Học sinh mẫu",
            "SchoolName": "Trường mẫu",
            "TargetScore": 950,
            "LatestScore": 720,
            "AvgMastery": 0.6,
            "StudyMin7d": 120,
            "LastActivityAt": None,
        }
    ])
    @patch("content.pyodbc.connect")
    def test_teacher_list_only_queries_assigned_students(self, _connect, fetch_all):
        response = self.client.get("/teacher/students")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Học sinh mẫu", response.get_data(as_text=True))
        self.assertIn("/teacher/students/3", response.get_data(as_text=True))
        self.assertEqual(fetch_all.call_args.args[2], (12,))
        self.assertIn("WHERE assigned.TeacherID=?", fetch_all.call_args.args[1])

    @patch("content._fetch_all", return_value=[])
    @patch("content.pyodbc.connect")
    def test_teacher_cannot_open_unassigned_student(self, _connect, fetch_all):
        response = self.client.get("/teacher/students/99")

        self.assertEqual(response.status_code, 404)
        fetch_all.assert_called_once()
        self.assertEqual(fetch_all.call_args.args[2], (12, 99))

    @patch("content._fetch_all", side_effect=[
        [{
            "StudentID": 3,
            "FullName": "Học sinh mẫu",
            "SchoolName": "Trường mẫu",
            "TargetScore": 950,
            "ExamDate": None,
            "DaysToExam": None,
            "AvgMastery": 0.6,
            "SubmittedAttempts": 2,
            "BestScore": 800,
            "LatestScore": 720,
            "StudyMin7d": 120,
            "LastActivityAt": None,
            "PredictedScore": 810,
            "ProbReachTarget": 0.4,
        }],
        [{"SubjectName": "Logic", "CompetencyName": "Suy luận", "MasteryPercent": 60,
          "MasteryLevel": "Trung bình", "NeedsReview": 1, "AttemptCount": 4}],
        [{"AlertLevel": "Trung bình", "AlertSummary": "Cần ôn tập."}],
        [{"ReadinessScore": 55, "ReadinessLevel": "Cần tăng tốc", "DaysToExam": 30}],
    ])
    @patch("content.pyodbc.connect")
    def test_assigned_student_detail_renders_progress(self, _connect, fetch_all):
        response = self.client.get("/teacher/students/3")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Học sinh mẫu", html)
        self.assertIn("Cần tăng tốc", html)
        self.assertIn("Suy luận", html)
        self.assertEqual(fetch_all.call_count, 4)
        self.assertEqual(fetch_all.call_args_list[0].args[2], (12, 3))


if __name__ == "__main__":
    unittest.main()

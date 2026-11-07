import hashlib
import unittest
from unittest.mock import patch

import pyodbc

import app as web_app
from database import _hash_password, _verify_password


class NovaPathTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY='test-key')
        self.client = web_app.app.test_client()
        with self.client.session_transaction() as sess:
            sess["_csrf_token"] = "test-csrf-token"

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    @patch("app.verify_login")
    def test_post_without_csrf_token_is_rejected(self, verify_login):
        response = self.client.post(
            "/login",
            data={"email": "student@example.test", "password": "password"},
        )

        self.assertEqual(response.status_code, 400)
        verify_login.assert_not_called()

    def test_logout_requires_post_and_clears_session(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 3
            sess["role"] = "Student"

        response = self.client.post(
            "/logout",
            data={"csrf_token": "test-csrf-token"},
        )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_password_hash_supports_new_and_seed_hashes(self):
        password = "seed-password"
        new_hash = _hash_password(password)
        legacy_hash = hashlib.sha256(password.encode("utf-16le")).digest()

        self.assertTrue(_verify_password(new_hash, password)[0])
        self.assertFalse(_verify_password(new_hash, "wrong-password")[0])
        self.assertEqual(_verify_password(legacy_hash, password), (True, True))
        self.assertEqual(_verify_password(legacy_hash, "wrong-password"), (False, True))

    def test_role_restricted_routes_redirect_other_roles(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["role"] = "Teacher"

        response = self.client.get("/profile")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    @patch("app.verify_login")
    def test_login_success(self, mock_verify):
        with self.client.session_transaction() as sess:
            sess["stale_value"] = "remove after authentication"

        mock_verify.return_value = {
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
                "password": "123",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.location)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess["user_id"], 3)
            self.assertEqual(sess["role"], "Student")
            self.assertNotIn("stale_value", sess)

    def test_registration_rejects_weak_password_before_database_access(self):
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

    @patch("app.update_student_profile")
    def test_profile_rejects_invalid_score_without_database_write(self, update_profile):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 3
            sess["role"] = "Student"

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
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['role'] = 'Student'
            sess['fullname'] = 'Trần Văn Học'

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
            "competencies": [{"SubjectName": "Định lượng", "CompetencyName": "Đại số", "MasteryPercent": 20}],
            "tasks": [],
            "recommendations": [],
            "exams": [],
        }

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Chào Học", response.get_data(as_text=True))
        self.assertIn("950", response.get_data(as_text=True))
        load_data.assert_called_once_with(3)


if __name__ == "__main__":
    unittest.main()

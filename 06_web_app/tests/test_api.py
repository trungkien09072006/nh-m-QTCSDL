import unittest
from unittest.mock import patch

import app as web_app


class ApiRouteTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="test-key")
        self.client = web_app.app.test_client()
        self.csrf_token = self.client.get("/api/csrf-token").get_json()["csrf_token"]

    def headers(self, token=None):
        return {"X-CSRF-Token": token or self.csrf_token}

    def role_headers(self, role):
        token = self.client.get(
            "/api/csrf-token",
            headers={"X-Portal-Role": role},
        ).get_json()["csrf_token"]
        return {"X-CSRF-Token": token, "X-Portal-Role": role}

    def test_api_session_starts_unauthenticated(self):
        response = self.client.get("/api/session")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["user"])

    @patch("app.verify_login")
    def test_api_login_rotates_csrf_and_creates_student_session(self, verify_login):
        verify_login.return_value = {
            "UserID": 3,
            "Email": "student@example.test",
            "FullName": "Test Student",
            "RoleName": "Student",
        }

        response = self.client.post(
            "/api/login",
            json={"email": "student@example.test", "password": "valid-password"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["user"]["id"], 3)
        self.assertNotEqual(payload["csrf_token"], self.csrf_token)
        verify_login.assert_called_once_with("student@example.test", "valid-password")
        session_response = self.client.get("/api/session")
        self.assertEqual(session_response.get_json()["user"]["email"], "student@example.test")

    @patch("app.verify_login")
    def test_api_login_rejects_missing_csrf_before_authentication(self, verify_login):
        response = self.client.post(
            "/api/login",
            json={"email": "student@example.test", "password": "valid-password"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "csrf_invalid")
        verify_login.assert_not_called()

    @patch("app.verify_login")
    def test_api_login_allows_all_supported_roles(self, verify_login):
        verify_login.return_value = {
            "UserID": 4,
            "Email": "teacher@example.test",
            "FullName": "Test Teacher",
            "RoleName": "Teacher",
        }

        response = self.client.post(
            "/api/login",
            json={
                "email": "teacher@example.test",
                "password": "valid-password",
                "role": "Teacher",
            },
            headers=self.role_headers("Teacher"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["role"], "Teacher")

    @patch("app.verify_login")
    def test_api_login_rejects_role_mismatch_without_creating_session(self, verify_login):
        verify_login.return_value = {
            "UserID": 4,
            "Email": "teacher@example.test",
            "FullName": "Test Teacher",
            "RoleName": "Teacher",
        }

        response = self.client.post(
            "/api/login",
            json={
                "email": "teacher@example.test",
                "password": "valid-password",
                "role": "Parent",
            },
            headers=self.role_headers("Parent"),
        )

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.client.get("/api/session").get_json()["user"])

    @patch("app.verify_login")
    def test_api_role_sessions_can_stay_signed_in_together(self, verify_login):
        users = [
            {
                "UserID": 3,
                "Email": "student@example.test",
                "FullName": "Student",
                "RoleName": "Student",
            },
            {
                "UserID": 4,
                "Email": "parent@example.test",
                "FullName": "Parent",
                "RoleName": "Parent",
            },
            {
                "UserID": 5,
                "Email": "teacher@example.test",
                "FullName": "Teacher",
                "RoleName": "Teacher",
            },
        ]
        verify_login.side_effect = users

        for user in users:
            response = self.client.post(
                "/api/login",
                json={
                    "email": user["Email"],
                    "password": "valid-password",
                    "role": user["RoleName"],
                },
                headers=self.role_headers(user["RoleName"]),
            )
            self.assertEqual(response.status_code, 200)

        for user in users:
            with self.subTest(role=user["RoleName"]):
                response = self.client.get(
                    "/api/session",
                    headers={"X-Portal-Role": user["RoleName"]},
                )
                self.assertEqual(response.get_json()["user"]["id"], user["UserID"])

    @patch("parent_portal._fetch_all", side_effect=[[], [], []])
    @patch("parent_portal.pyodbc.connect")
    @patch("app.verify_login")
    def test_web_parent_and_vite_teacher_sessions_do_not_conflict(
        self, verify_login, _connect, _fetch_all
    ):
        with self.client.session_transaction("/parent") as parent_session:
            parent_session.update(
                user_id=4,
                role="Parent",
                fullname="Parent",
                _csrf_token="parent-csrf-token",
            )

        teacher = {
            "UserID": 5,
            "Email": "teacher@example.test",
            "FullName": "Teacher",
            "RoleName": "Teacher",
        }
        verify_login.return_value = teacher
        teacher_headers = self.role_headers("Teacher")
        teacher_login = self.client.post(
            "/api/login",
            json={
                "email": teacher["Email"],
                "password": "valid-password",
                "role": "Teacher",
            },
            headers=teacher_headers,
        )

        self.assertEqual(teacher_login.status_code, 200)
        self.assertEqual(self.client.get("/parent").status_code, 200)
        self.assertEqual(
            self.client.get(
                "/api/session",
                headers={"X-Portal-Role": "Teacher"},
            ).get_json()["user"]["id"],
            teacher["UserID"],
        )

        parent_logout = self.client.post(
            "/parent/logout",
            data={"csrf_token": "parent-csrf-token"},
        )
        self.assertEqual(parent_logout.status_code, 302)
        self.assertEqual(
            self.client.get(
                "/api/session",
                headers={"X-Portal-Role": "Teacher"},
            ).get_json()["user"]["id"],
            teacher["UserID"],
        )

    @patch("app.register_user", return_value=True)
    def test_api_register_uses_post_and_returns_created(self, register_user):
        response = self.client.post(
            "/api/register",
            json={
                "fullname": "New Student",
                "email": "new@student.example",
                "password": "valid-password",
            },
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 201)
        register_user.assert_called_once_with(
            "new@student.example",
            "valid-password",
            "New Student",
        )

    def test_student_data_routes_require_login(self):
        for path in ("/api/dashboard", "/api/profile"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_profile_update_requires_csrf(self):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student")

        response = self.client.put(
            "/api/profile",
            json={"fullname": "Test Student", "target_score": 800, "daily_study_min": 60},
        )

        self.assertEqual(response.status_code, 400)

    @patch("app.update_student_profile")
    def test_profile_update_writes_shared_user_id(self, update_profile):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student")

        response = self.client.put(
            "/api/profile",
            json={
                "fullname": "Updated Student",
                "phone": "",
                "school": "",
                "target_score": 900,
                "exam_date": "",
                "daily_study_min": 90,
            },
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        update_profile.assert_called_once_with(3, "Updated Student", None, None, 900, "", 90)
        self.assertEqual(self.client.get("/api/session").get_json()["user"]["fullname"], "Updated Student")

    def test_api_logout_requires_csrf_and_clears_session(self):
        with self.client.session_transaction() as session:
            session.update(user_id=3, role="Student")

        response = self.client.post("/api/logout", headers=self.headers())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["csrf_token"])
        self.assertIsNone(self.client.get("/api/session").get_json()["user"])


if __name__ == "__main__":
    unittest.main()
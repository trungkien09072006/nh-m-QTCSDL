import unittest
from unittest.mock import MagicMock, patch

import app as web_app
from admin_api import bp as admin_bp

if "admin" not in web_app.app.blueprints:
    web_app.app.register_blueprint(admin_bp)


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="admin-test-key")
        self.client = web_app.app.test_client()
        self.csrf_token = self.client.get("/api/csrf-token").get_json()["csrf_token"]

    def headers(self):
        return {"X-CSRF-Token": self.csrf_token}

    def login_as(self, user_id=1, role="Admin"):
        with self.client.session_transaction() as sess:
            sess.update(user_id=user_id, role=role, fullname="Quản trị viên")

    def test_admin_routes_require_admin_role(self):
        self.assertEqual(self.client.get("/api/admin/users").status_code, 401)

        self.login_as(user_id=2, role="Teacher")
        self.assertEqual(self.client.get("/api/admin/users").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/audit-logs").status_code, 403)

    def test_mutations_require_csrf(self):
        self.login_as(user_id=1, role="Admin")
        res = self.client.patch("/api/admin/users/3/status", json={"is_active": False})
        self.assertEqual(res.status_code, 400)

    def test_admin_cannot_lock_or_demote_self(self):
        self.login_as(user_id=1, role="Admin")
        res_lock = self.client.patch(
            "/api/admin/users/1/status",
            json={"is_active": False},
            headers=self.headers(),
        )
        self.assertEqual(res_lock.status_code, 400)

        res_role = self.client.patch(
            "/api/admin/users/1/role",
            json={"role_name": "Teacher"},
            headers=self.headers(),
        )
        self.assertEqual(res_role.status_code, 400)

    @patch("admin_api.pyodbc.connect")
    def test_update_user_status_succeeds(self, mock_connect):
        self.login_as(user_id=1, role="Admin")
        mock_cur = MagicMock()
        mock_cur.rowcount = 1
        mock_connect.return_value.cursor.return_value = mock_cur

        res = self.client.patch(
            "/api/admin/users/3/status",
            json={"is_active": False},
            headers=self.headers(),
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["is_active"])
        mock_connect.return_value.commit.assert_called_once()

    @patch("admin_api.pyodbc.connect")
    def test_link_parent_student_succeeds(self, mock_connect):
        self.login_as(user_id=1, role="Admin")
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [(1,), (1,)]  # Parent hợp lệ + StudentProfile tồn tại
        mock_connect.return_value.cursor.return_value = mock_cur

        res = self.client.post(
            "/api/admin/parent-student",
            json={"parent_id": 5, "student_id": 3},
            headers=self.headers(),
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["parent_id"], 5)
        mock_connect.return_value.commit.assert_called_once()

    @patch("admin_api.pyodbc.connect")
    def test_upsert_setting_succeeds(self, mock_connect):
        self.login_as(user_id=1, role="Admin")
        mock_cur = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cur

        res = self.client.put(
            "/api/admin/settings/AI_MODEL",
            json={"value": "gemini-1.5-flash"},
            headers=self.headers(),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["setting_key"], "AI_MODEL")
        mock_connect.return_value.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
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
        self.csrf_token = self.client.get("/api/admin/csrf-token").get_json()["csrf_token"]

    def headers(self):
        return {"X-CSRF-Token": self.csrf_token}

    def login_as(self, user_id=1, role="Admin"):
        with self.client.session_transaction("/admin") as sess:
            sess.update(user_id=user_id, role=role, fullname="Quản trị viên")

    def test_admin_routes_require_admin_role(self):
        self.assertEqual(self.client.get("/api/admin/users").status_code, 401)

        self.login_as(user_id=2, role="Teacher")
        self.assertEqual(self.client.get("/api/admin/users").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/audit-logs").status_code, 403)
        self.assertEqual(self.client.get("/admin/parent-link-requests").status_code, 403)

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

    def test_parent_link_request_queue_requires_admin(self):
        self.assertEqual(self.client.get("/admin/parent-link-requests").status_code, 302)

        self.login_as(user_id=2, role="Parent")
        self.assertEqual(self.client.get("/admin/parent-link-requests").status_code, 403)

    def test_admin_home_redirects_to_verification_queue(self):
        self.login_as()

        response = self.client.get("/admin")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/parent-link-requests"))

    @patch("admin_portal.verify_login")
    def test_admin_login_uses_separate_cookie_from_student_session(self, verify_admin):
        student = {
            "UserID": 3,
            "Email": "student@example.test",
            "FullName": "Học sinh",
            "RoleName": "Student",
        }
        admin = {
            "UserID": 1,
            "Email": "admin@ai-edu.vn",
            "FullName": "Quản trị viên",
            "RoleName": "Admin",
        }
        with patch("app.verify_login", return_value=student):
            student_token = self.client.get("/api/csrf-token").get_json()["csrf_token"]
            student_login = self.client.post(
                "/login/student",
                data={
                    "email": student["Email"],
                    "password": "valid-password",
                    "csrf_token": student_token,
                },
            )
        self.assertEqual(student_login.status_code, 302)

        admin_token = self.client.get("/api/admin/csrf-token").get_json()["csrf_token"]
        verify_admin.return_value = admin
        admin_login = self.client.post(
            "/admin/login",
            data={
                "email": admin["Email"],
                "password": "valid-password",
                "csrf_token": admin_token,
            },
        )

        self.assertEqual(admin_login.status_code, 302)
        self.assertEqual(self.client.get("/api/session").get_json()["user"]["role"], "Student")
        self.assertEqual(self.client.get("/admin").status_code, 302)

    @patch("admin_portal.verify_login")
    def test_admin_login_rejects_non_admin_accounts(self, verify_login):
        verify_login.return_value = {
            "UserID": 3,
            "Email": "student@example.test",
            "FullName": "Học sinh",
            "RoleName": "Student",
        }

        response = self.client.post(
            "/admin/login",
            data={
                "email": "student@example.test",
                "password": "valid-password",
                "csrf_token": self.csrf_token,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("không có quyền Admin", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/api/session").get_json()["user"], None)

    @patch("admin_portal._fetch_all", return_value=[
        {
            "RequestID": 7,
            "CreatedAt": "2026-11-28",
            "ParentName": "Phụ huynh mẫu",
            "ParentEmail": "parent@example.test",
            "StudentName": "Học sinh mẫu",
            "StudentEmail": "student@example.test",
        }
    ])
    @patch("admin_portal.pyodbc.connect")
    def test_admin_can_view_parent_link_requests(self, mock_connect, fetch_all):
        self.login_as()

        response = self.client.get("/admin/parent-link-requests")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Phụ huynh mẫu", response.get_data(as_text=True))
        self.assertIn("Học sinh mẫu", response.get_data(as_text=True))
        fetch_all.assert_called_once()
        mock_connect.assert_called_once()

    @patch("admin_portal.pyodbc.connect")
    def test_admin_approval_links_parent_without_student_approval(self, mock_connect):
        self.login_as()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [(5, 8, "Pending"), (1,)]
        mock_connect.return_value.cursor.return_value = mock_cur

        response = self.client.post(
            "/admin/parent-link-requests/7",
            data={"decision": "approve"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_cur.execute.call_count, 4)
        self.assertIn("INSERT INTO dbo.ParentStudent", mock_cur.execute.call_args_list[2].args[0])
        self.assertIn("UPDATE dbo.ParentLinkRequests", mock_cur.execute.call_args_list[3].args[0])
        mock_connect.return_value.commit.assert_called_once()

    @patch("admin_portal.pyodbc.connect")
    def test_admin_rejection_does_not_link_parent(self, mock_connect):
        self.login_as()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [(5, 8, "Pending"), (1,)]
        mock_connect.return_value.cursor.return_value = mock_cur

        response = self.client.post(
            "/admin/parent-link-requests/7",
            data={"decision": "reject"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_cur.execute.call_count, 3)
        self.assertIn("UPDATE dbo.ParentLinkRequests", mock_cur.execute.call_args_list[-1].args[0])
        mock_connect.return_value.commit.assert_called_once()

    @patch("admin_portal.pyodbc.connect")
    def test_admin_cannot_approve_invalid_parent_student_accounts(self, mock_connect):
        self.login_as()
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [(5, 8, "Pending"), None]
        mock_connect.return_value.cursor.return_value = mock_cur

        response = self.client.post(
            "/admin/parent-link-requests/7",
            data={"decision": "approve"},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_cur.execute.call_count, 2)
        mock_connect.return_value.commit.assert_not_called()

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
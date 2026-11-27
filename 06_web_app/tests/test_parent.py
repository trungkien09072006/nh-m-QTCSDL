import unittest
from unittest.mock import MagicMock, patch

import app as web_app
from parent_api import bp as parent_bp

if "parent" not in web_app.app.blueprints:
    web_app.app.register_blueprint(parent_bp)


class ParentApiTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="parent-test-key")
        self.client = web_app.app.test_client()

    def login_as(self, user_id=5, role="Parent"):
        with self.client.session_transaction() as sess:
            sess.update(user_id=user_id, role=role, fullname="Phụ huynh mẫu")

    def test_parent_routes_require_parent_role(self):
        self.assertEqual(self.client.get("/api/parent/children").status_code, 401)
        self.assertEqual(self.client.get("/api/parent/dashboard").status_code, 401)

        self.login_as(user_id=3, role="Student")
        self.assertEqual(self.client.get("/api/parent/children").status_code, 403)
        self.assertEqual(self.client.get("/api/parent/dashboard").status_code, 403)

    @patch("parent_api.pyodbc.connect")
    @patch("parent_api._fetch_all")
    def test_list_children_returns_linked_students(self, mock_fetch, mock_connect):
        self.login_as(user_id=5, role="Parent")
        mock_fetch.return_value = [
            {"StudentID": 3, "StudentName": "Trần Văn Học", "TargetScore": 950}
        ]

        res = self.client.get("/api/parent/children")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["children"][0]["StudentID"], 3)

    @patch("parent_api.pyodbc.connect")
    def test_child_progress_blocks_unlinked_student(self, mock_connect):
        self.login_as(user_id=5, role="Parent")
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None  # Không có trong ParentStudent
        mock_connect.return_value.cursor.return_value = mock_cur

        res = self.client.get("/api/parent/children/99/progress")
        self.assertEqual(res.status_code, 404)

    @patch("parent_api.pyodbc.connect")
    @patch("parent_api._fetch_all")
    def test_child_progress_returns_data_for_linked_student(self, mock_fetch, mock_connect):
        self.login_as(user_id=5, role="Parent")
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1,)  # Đã liên kết trong ParentStudent
        mock_connect.return_value.cursor.return_value = mock_cur
        mock_fetch.side_effect = [
            [{"StudentID": 3, "FullName": "Trần Văn Học"}],
            [{"CompetencyName": "Đại số", "MasteryPercent": 20}],
            [{"AlertLevel": "Trung bình"}],
            [{"ReadinessScore": 62.5}],
        ]

        res = self.client.get("/api/parent/children/3/progress")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["overview"]["StudentID"], 3)
        self.assertEqual(len(data["competencies"]), 1)
        self.assertEqual(data["alerts"]["AlertLevel"], "Trung bình")


if __name__ == "__main__":
    unittest.main()
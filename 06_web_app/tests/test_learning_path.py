import unittest
from unittest.mock import patch

import app as web_app
from learning_path import bp as learning_path_bp
from learning_path_service import LearningPathItemNotFound

if "learning_path" not in web_app.app.blueprints:
    web_app.app.register_blueprint(learning_path_bp)


class LearningPathApiTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="lp-test-key")
        self.client = web_app.app.test_client()
        self.csrf_token = self.client.get("/api/csrf-token").get_json()["csrf_token"]

    def headers(self):
        return {"X-CSRF-Token": self.csrf_token}

    def student(self, user_id=3):
        with self.client.session_transaction() as sess:
            sess.update(user_id=user_id, role="Student")

    def test_routes_require_student_login(self):
        self.assertEqual(self.client.get("/api/learning-path").status_code, 401)
        self.assertEqual(
            self.client.patch(
                "/api/learning-path/items/1/status",
                json={"status": "DONE"},
                headers=self.headers(),
            ).status_code,
            401,
        )

        with self.client.session_transaction() as sess:
            sess.update(user_id=2, role="Teacher")
        self.assertEqual(self.client.get("/api/learning-path").status_code, 403)

    @patch(
        "learning_path.service.get_learning_path",
        return_value={"path": {"id": 1}, "summary": {"total_items": 2, "done_items": 1}, "items": []},
    )
    def test_get_learning_path_returns_student_data(self, get_path):
        self.student(3)
        res = self.client.get("/api/learning-path")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["path"]["id"], 1)
        get_path.assert_called_once_with(3)

    @patch("learning_path.service.update_item_status")
    def test_update_status_requires_csrf(self, update_status):
        self.student(3)
        res = self.client.patch("/api/learning-path/items/1/status", json={"status": "DONE"})
        self.assertEqual(res.status_code, 400)
        update_status.assert_not_called()

    @patch("learning_path.service.update_item_status", side_effect=ValueError("Trạng thái nhiệm vụ không hợp lệ."))
    def test_update_status_rejects_invalid_value(self, update_status):
        self.student(3)
        res = self.client.patch(
            "/api/learning-path/items/1/status",
            json={"status": "INVALID"},
            headers=self.headers(),
        )
        self.assertEqual(res.status_code, 400)
        update_status.assert_called_once_with(3, 1, "INVALID")

    @patch("learning_path.service.update_item_status", side_effect=LearningPathItemNotFound())
    def test_update_other_students_item_returns_404(self, _update_status):
        self.student(3)
        res = self.client.patch(
            "/api/learning-path/items/99/status",
            json={"status": "DONE"},
            headers=self.headers(),
        )
        self.assertEqual(res.status_code, 404)

    @patch(
        "learning_path.service.update_item_status",
        return_value={"updated_item": {"id": 1, "status": "DONE"}, "summary": {"done_items": 1}, "items": []},
    )
    def test_update_status_succeeds(self, update_status):
        self.student(3)
        res = self.client.patch(
            "/api/learning-path/items/1/status",
            json={"status": "done"},
            headers=self.headers(),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["updated_item"]["status"], "DONE")
        update_status.assert_called_once_with(3, 1, "DONE")


if __name__ == "__main__":
    unittest.main()
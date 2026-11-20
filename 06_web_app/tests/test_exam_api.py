import unittest
from unittest.mock import patch

import app as web_app
from exam_service import AttemptExpired


class ExamApiTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="exam-test-key")
        self.client = web_app.app.test_client()
        self.csrf_token = self.client.get("/api/csrf-token").get_json()["csrf_token"]

    def headers(self):
        return {"X-CSRF-Token": self.csrf_token}

    def student(self):
        with self.client.session_transaction() as session:
            session.update(user_id=13, role="Student")

    def test_exam_routes_require_student_login(self):
        response = self.client.get("/api/exams")
        self.assertEqual(response.status_code, 401)

        with self.client.session_transaction() as session:
            session.update(user_id=2, role="Teacher")
        response = self.client.get("/api/exams")
        self.assertEqual(response.status_code, 403)

    @patch("exams.exam_service.list_exams", return_value=[{"id": 4, "title": "Bài mẫu"}])
    def test_student_can_list_available_exams(self, list_exams):
        self.student()

        response = self.client.get("/api/exams")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["exams"][0]["id"], 4)
        list_exams.assert_called_once_with()

    @patch("exams.exam_service.start_attempt", return_value={"attempt": {"id": 8}, "questions": []})
    def test_start_creates_attempt_for_signed_in_student(self, start_attempt):
        self.student()

        response = self.client.post("/api/exams/4/attempts", headers=self.headers())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["attempt"]["id"], 8)
        start_attempt.assert_called_once_with(13, 4)

    @patch("exams.exam_service.start_attempt")
    def test_start_requires_csrf_token(self, start_attempt):
        self.student()

        response = self.client.post("/api/exams/4/attempts")

        self.assertEqual(response.status_code, 400)
        start_attempt.assert_not_called()

    @patch("exams.exam_service.submit_attempt")
    def test_submit_rejects_duplicate_question_answers(self, submit_attempt):
        self.student()

        response = self.client.post(
            "/api/exam-attempts/8/submit",
            json={
                "answers": [
                    {"question_id": 1, "option_id": 2},
                    {"question_id": 1, "option_id": 3},
                ]
            },
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 400)
        submit_attempt.assert_not_called()

    @patch("exams.exam_service.save_attempt_answers")
    def test_student_answer_is_saved_during_attempt(self, save_answers):
        self.student()

        response = self.client.post(
            "/api/exam-attempts/8/answers",
            json={"answers": [{"question_id": 1, "option_id": 2}]},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["saved"])
        save_answers.assert_called_once_with(13, 8, {1: 2})

    @patch("exams.exam_service.save_attempt_answers", side_effect=AttemptExpired())
    def test_answer_save_is_rejected_after_deadline(self, save_answers):
        self.student()

        response = self.client.post(
            "/api/exam-attempts/8/answers",
            json={"answers": [{"question_id": 1, "option_id": 2}]},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("hết giờ", response.get_json()["error"])
        save_answers.assert_called_once()

    @patch("exams.exam_service.submit_attempt", return_value={"id": 8, "score": 50.0})
    def test_submit_delegates_answers_and_returns_result(self, submit_attempt):
        self.student()

        response = self.client.post(
            "/api/exam-attempts/8/submit",
            json={"answers": [{"question_id": 1, "option_id": 2}]},
            headers=self.headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["attempt"]["score"], 50.0)
        submit_attempt.assert_called_once_with(13, 8, {1: 2})


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

import pyodbc

import app as web_app


class DashboardRouteTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()

    @patch("app.load_dashboard_data")
    def test_dashboard_renders_student_data(self, load_data):
        load_data.return_value = {
            "student": {
                "FullName": "Trần Văn Học",
                "TargetScore": 950,
                "DailyStudyMin": 120,
                "ExamDate": "15/06/2027",
            },
            "weekly_minutes": 180,
            "latest_exam": {"title": "Đề thi thử ĐGNL", "score": 50},
            "prediction": {
                "score": 880.5,
                "probability": 0.65,
                "risk_note": "Nguy cơ không đạt mục tiêu nếu không cải thiện Định lượng.",
            },
            "competencies": [
                {
                    "SubjectName": "Định lượng",
                    "CompetencyName": "Đại số",
                    "MasteryPercent": 20,
                }
            ],
            "tasks": [],
            "recommendations": [
                {
                    "RecID": 1,
                    "ResourceTitle": "Chuyên đề: Hàm số và Đồ thị",
                    "Reason": "Điểm số phần Đại số của bạn đang thấp (20%).",
                    "IsAccepted": 0,
                    "CompetencyName": "Đại số",
                }
            ],
            "exams": [],
            "notifications": [
                {
                    "NotificationID": 10,
                    "NotifyType": "LOW_PROBABILITY",
                    "Message": "Dự đoán điểm hiện tại là 880.5.",
                    "IsRead": 0,
                    "CreatedAt": "10:00 07/11/2026",
                }
            ],
            "unread_notification_count": 1,
            "tutor_messages": [
                {
                    "MessageID": 1,
                    "Sender": "AI",
                    "Content": "Quy luật dãy số là n*(n+1), vậy 6*7=42.",
                    "QuestionID": 1,
                    "QuestionTitle": "Cho dãy số: 2, 6, 12, 20, 30.",
                    "SentAt": "09:50 07/11/2026",
                }
            ],
            "tutor_questions": [],
        }

        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Chào Học", html)
        self.assertIn("950", html)
        self.assertIn("20%", html)
        self.assertIn("Nguy cơ không đạt mục tiêu", html)
        self.assertIn("Quy luật dãy số là n*(n+1)", html)
        load_data.assert_called_once_with("student1@gmail.com")

    @patch("app.load_dashboard_data", return_value={"student": None})
    def test_missing_student_shows_setup_message(self, _load_data):
        _load_data.return_value = {
            "student": None,
            "weekly_minutes": 0,
            "latest_exam": None,
            "prediction": None,
            "competencies": [],
            "tasks": [],
            "recommendations": [],
            "exams": [],
            "notifications": [],
            "unread_notification_count": 0,
            "tutor_messages": [],
            "tutor_questions": [],
        }
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Chưa tìm thấy hồ sơ học sinh", response.get_data(as_text=True))

    @patch("app.load_dashboard_data", side_effect=pyodbc.Error("database unavailable"))
    def test_database_error_is_reported(self, _load_data):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("Chưa tải được dữ liệu học tập", response.get_data(as_text=True))
        self.assertIn("SQL Server", response.get_data(as_text=True))

    @patch("app.refresh_ai_insights", return_value=True)
    def test_ai_refresh_route_redirects(self, mock_refresh):
        response = self.client.post("/ai/refresh")
        self.assertEqual(response.status_code, 302)
        mock_refresh.assert_called_once_with("student1@gmail.com")

    @patch("app.respond_to_recommendation", return_value=True)
    def test_recommendation_response_route(self, mock_respond):
        response = self.client.post(
            "/recommendations/1/respond", data={"action": "accept"}
        )
        self.assertEqual(response.status_code, 302)
        mock_respond.assert_called_once_with("student1@gmail.com", 1, True)

    @patch("app.ask_ai_tutor", return_value=True)
    def test_tutor_ask_route(self, mock_ask):
        response = self.client.post(
            "/tutor/ask",
            data={"message": "Giải thích câu 1 giúp mình", "question_id": "1"},
        )
        self.assertEqual(response.status_code, 302)
        mock_ask.assert_called_once_with(
            "student1@gmail.com", "Giải thích câu 1 giúp mình", 1
        )

    @patch("app.mark_notifications_read", return_value=True)
    def test_notifications_read_route(self, mock_read):
        response = self.client.post(
            "/notifications/read", data={"notification_id": "10"}
        )
        self.assertEqual(response.status_code, 302)
        mock_read.assert_called_once_with("student1@gmail.com", 10)


if __name__ == "__main__":
    unittest.main()
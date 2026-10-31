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

        self.assertEqual(response.status_code, 200)
        self.assertIn("Chào Học", response.get_data(as_text=True))
        self.assertIn("950", response.get_data(as_text=True))
        self.assertIn("20%", response.get_data(as_text=True))
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


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import app as web_app
import recommendation_service as service
from recommendations import bp as recommendations_bp
from recommendation_service import RecommendationNotFound, StudentProfileNotFound


# Đăng ký ngay khi import (trước mọi request của bộ test) để không lỗi khi chạy cả bộ.
# Khi người 4 đã đăng ký blueprint trong app.py thì bước này tự bỏ qua.
if "recommendations" not in web_app.app.blueprints:
    web_app.app.register_blueprint(recommendations_bp)


def make_inputs(**overrides):
    inputs = {
        "target_score": 900,
        "exam_date": "2027-02-01",
        "days_to_exam": 70,
        "daily_study_min": 60,
        "avg_mastery": 0.5,
        "competency_count": 4,
        "latest_score": None,
        "submitted_attempts": 2,
        "answered_count": 20,
        "minutes_7d": 210,
    }
    inputs.update(overrides)
    return inputs


class PredictionFormulaTests(unittest.TestCase):
    """Công thức phải trùng sp_CalculateScorePrediction (đã tính tay)."""

    def test_without_exam_uses_mastery_for_exam_part(self):
        result = service.compute_prediction(make_inputs())
        # 0.5*1200*0.55 + 600*0.30 + 0.5*1200*0.15 = 330 + 180 + 90
        self.assertEqual(result["score"], 600.0)
        self.assertEqual(result["exam_source"], "mastery")
        self.assertEqual(result["parts"], {"mastery": 330.0, "exam": 180.0, "study": 90.0})
        self.assertEqual(result["probability"], round(600 / 900 * 0.85, 4))

    def test_exam_score_on_hundred_scale_is_multiplied_by_twelve(self):
        result = service.compute_prediction(
            make_inputs(avg_mastery=0.8, latest_score=80.0, minutes_7d=420, target_score=950)
        )
        # 0.8*1200*0.55 + 960*0.30 + 1*1200*0.15 = 528 + 288 + 180
        self.assertEqual(result["score"], 996.0)
        self.assertEqual(result["probability"], 0.9)

    def test_exam_score_above_hundred_is_used_as_is(self):
        result = service.compute_prediction(make_inputs(latest_score=700.0, minutes_7d=0))
        self.assertEqual(result["exam_points"], 700.0)
        self.assertEqual(result["study_ratio"], 0.0)

    def test_missing_mastery_defaults_to_half_and_is_flagged(self):
        result = service.compute_prediction(make_inputs(avg_mastery=None))
        self.assertTrue(result["mastery_defaulted"])
        self.assertEqual(result["avg_mastery"], 0.5)

    def test_study_ratio_is_capped_at_one(self):
        result = service.compute_prediction(make_inputs(minutes_7d=5000))
        self.assertEqual(result["study_ratio"], 1.0)

    def test_no_target_means_no_probability(self):
        result = service.compute_prediction(make_inputs(target_score=0))
        self.assertIsNone(result["probability"])

    def test_risk_levels_match_view_thresholds(self):
        self.assertEqual(service.risk_level(0.85), "An toàn")
        self.assertEqual(service.risk_level(0.60), "Cần theo dõi")
        self.assertEqual(service.risk_level(0.59), "Nguy cơ cao")
        self.assertIsNone(service.risk_level(None))


class ImprovementTests(unittest.TestCase):
    def tips(self, inputs=None, weak=None):
        inputs = inputs or make_inputs()
        current = service.compute_prediction(inputs)
        return service.build_improvements(inputs, current, weak or [])

    def test_gap_tip_states_required_mastery_when_reachable(self):
        tips = self.tips(make_inputs(target_score=700))
        gap = next(t for t in tips if t["kind"] == "gap")
        self.assertIn("Còn thiếu khoảng 100 điểm", gap["title"])
        self.assertIn("mức thành thạo", gap["detail"])

    def test_gap_tip_admits_mastery_alone_is_not_enough(self):
        tips = self.tips(make_inputs(target_score=1200, avg_mastery=0.3, latest_score=30.0))
        gap = next(t for t in tips if t["kind"] == "gap")
        self.assertIn("chưa đủ", gap["detail"])

    def test_weak_competency_names_resource(self):
        weak = [{"name": "Đại số", "mastery": 0.2, "resource_title": "Hàm số", "resource_min": 15}]
        tip = next(t for t in self.tips(weak=weak) if t["kind"] == "competency")
        self.assertIn("Đại số", tip["title"])
        self.assertIn("20%", tip["detail"])
        self.assertIn("Hàm số", tip["detail"])

    def test_study_time_tip_reports_missing_minutes(self):
        tip = next(t for t in self.tips() if t["kind"] == "study")
        self.assertIn("210/420", tip["detail"])
        self.assertIn("210 phút", tip["detail"])

    def test_profile_tips_for_missing_target_and_past_exam(self):
        kinds = [t["title"] for t in self.tips(make_inputs(target_score=0, days_to_exam=-5))]
        self.assertIn("Chưa đặt điểm mục tiêu", kinds)
        self.assertIn("Ngày thi dự kiến đã qua", kinds)

    def test_no_data_tip(self):
        inputs = make_inputs(competency_count=0, submitted_attempts=0, avg_mastery=None, answered_count=0)
        self.assertEqual(self.tips(inputs)[0]["kind"], "data")

    def test_data_quality_levels(self):
        self.assertEqual(service.data_quality(make_inputs(answered_count=3))["level"], "low")
        self.assertEqual(service.data_quality(make_inputs(answered_count=20))["level"], "medium")
        self.assertEqual(service.data_quality(make_inputs(answered_count=50))["level"], "good")

    def test_only_http_links_are_exposed(self):
        self.assertEqual(service._safe_url("https://a.vn/x"), "https://a.vn/x")
        self.assertIsNone(service._safe_url("javascript:alert(1)"))
        self.assertIsNone(service._safe_url(None))


class FakeCursor:
    """Trả kết quả theo chuỗi con của câu SQL, ghi lại mọi lệnh đã chạy."""

    def __init__(self, script):
        self.script = script
        self.executed = []
        self.description = []
        self._rows = []

    def execute(self, sql, params=()):
        self.executed.append((" ".join(sql.split()), tuple(params)))
        for needle, columns, rows in self.script:
            if needle in sql:
                self.description = [(name,) for name in columns]
                self._rows = [tuple(row) for row in rows]
                return
        self.description = []
        self._rows = []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, script):
        self.cursor_obj = FakeCursor(script)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def close(self):
        pass


INPUT_COLUMNS = [
    "TargetScore", "ExamDate", "DailyStudyMin", "DaysToExam", "AvgMastery", "CompetencyCount",
    "LatestScore", "SubmittedAttempts", "AnsweredCount", "Minutes7d",
]
INPUT_ROW = (900, datetime(2027, 2, 1), 60, 70, Decimal("0.5000"), 4, None, 2, 20, 210)
PRED_COLUMNS = ["PredictionID", "PredictedScore", "ProbReachTarget", "RiskNote", "PredictedAt", "AgeSeconds"]


def prediction_script(age_seconds, stored_score="600.00"):
    return [
        ("FROM dbo.StudentProfiles AS sp", INPUT_COLUMNS, [INPUT_ROW]),
        ("SELECT TOP 1 PredictionID", PRED_COLUMNS,
         [(7, Decimal(stored_score), Decimal("0.5667"), "Ghi chú", datetime(2026, 11, 22, 9, 0), age_seconds)]),
        ("SELECT TOP (8)", ["PredictedScore", "ProbReachTarget", "PredictedAt"],
         [(Decimal(stored_score), Decimal("0.5667"), datetime(2026, 11, 22, 9, 0))]),
        ("FROM dbo.StudentCompetency AS sc INNER JOIN", ["CompetencyName", "Mastery", "ResourceTitle", "EstimatedMin"], []),
    ]


class ServiceDatabaseTests(unittest.TestCase):
    def run_with(self, script, function, *args):
        connection = FakeConnection(script)
        with patch("recommendation_service.pyodbc.connect", return_value=connection):
            return function(*args), connection

    def executed_sql(self, connection):
        return [sql for sql, _ in connection.cursor_obj.executed]

    def test_overview_marks_prediction_stale_when_data_changed(self):
        result, _ = self.run_with(prediction_script(5000, stored_score="400.00"),
                                  service.get_prediction_overview, 13)
        self.assertTrue(result["prediction"]["is_stale"])
        self.assertEqual(result["prediction"]["probability_percent"], 57)
        self.assertEqual(result["prediction"]["risk_level"], "Nguy cơ cao")
        self.assertEqual(result["method"]["type"], "heuristic_formula")
        self.assertIsInstance(result["prediction"]["score"], float)

    def test_overview_without_prediction_still_explains_factors(self):
        script = [row for row in prediction_script(0) if "TOP 1 PredictionID" not in row[0]]
        script.append(("TOP 1 PredictionID", PRED_COLUMNS, []))
        result, _ = self.run_with(script, service.get_prediction_overview, 13)
        self.assertIsNone(result["prediction"])
        self.assertEqual(result["factors"]["parts"]["mastery"], 330.0)

    def test_overview_for_unknown_student_raises(self):
        script = [("FROM dbo.StudentProfiles AS sp", INPUT_COLUMNS, [])]
        with self.assertRaises(StudentProfileNotFound):
            self.run_with(script, service.get_prediction_overview, 99)

    def test_refresh_runs_procedure_when_prediction_is_old(self):
        result, connection = self.run_with(prediction_script(3600), service.refresh_prediction, 13)
        sql = self.executed_sql(connection)
        self.assertTrue(any("EXEC dbo.sp_CalculateScorePrediction" in s for s in sql))
        self.assertTrue(any("sp_SyncMasteryFromAnswers" in s for s in sql))
        self.assertFalse(result["reused"])
        self.assertEqual(connection.commits, 1)

    def test_refresh_reuses_fresh_unchanged_prediction(self):
        result, connection = self.run_with(prediction_script(5), service.refresh_prediction, 13)
        self.assertFalse(any("sp_CalculateScorePrediction" in s for s in self.executed_sql(connection)))
        self.assertTrue(result["reused"])

    def test_refresh_recalculates_when_data_changed_even_if_recent(self):
        result, connection = self.run_with(prediction_script(5, stored_score="400.00"),
                                           service.refresh_prediction, 13)
        self.assertTrue(any("sp_CalculateScorePrediction" in s for s in self.executed_sql(connection)))
        self.assertFalse(result["reused"])

    def test_respond_updates_only_own_recommendation(self):
        script = [("SELECT 1 FROM dbo.Recommendations", ["x"], [(1,)])]
        result, connection = self.run_with(script, service.respond_to_recommendation, 13, 5, True)
        self.assertEqual(result, {"id": 5, "status": "accepted"})
        update = [item for item in connection.cursor_obj.executed if item[0].startswith("UPDATE")][0]
        self.assertEqual(update[1], (1, 5, 13))
        self.assertIn("StudentID = ?", update[0])

    def test_respond_to_someone_elses_recommendation_is_not_found(self):
        script = [("SELECT 1 FROM dbo.Recommendations", ["x"], [])]
        with self.assertRaises(RecommendationNotFound):
            self.run_with(script, service.respond_to_recommendation, 13, 5, False)

    def test_generate_reports_created_count_and_explanations(self):
        counts = iter([(1,), (3,)])

        class CountingCursor(FakeCursor):
            def execute(self, sql, params=()):
                super().execute(sql, params)
                if "SELECT COUNT(*) FROM dbo.Recommendations" in sql:
                    self._rows = [next(counts)]
                elif "SELECT COUNT(*) FROM dbo.StudentProfiles" in sql:
                    self._rows = [(1,)]

        rec_columns = [
            "RecID", "ResourceID", "QuestionID", "Reason", "CreatedAt", "IsAccepted",
            "ResourceTitle", "ResourceType", "Url", "EstimatedMin", "QuestionContent",
            "Difficulty", "CompetencyName", "SubjectName", "Mastery",
        ]
        rows = [
            (2, 4, None, "Lý do A", datetime(2026, 11, 22), None, "Hàm số", "ARTICLE",
             "javascript:alert(1)", 15, None, None, "Đại số", "Định lượng", Decimal("0.2000")),
            (3, None, 9, "Lý do B", datetime(2026, 11, 22), 1, None, None, None, None,
             "Câu hỏi?", 2, "Đại số", "Định lượng", Decimal("0.2000")),
        ]
        connection = FakeConnection([("FROM dbo.Recommendations AS rec", rec_columns, rows)])
        connection.cursor_obj = CountingCursor(connection.cursor_obj.script)
        with patch("recommendation_service.pyodbc.connect", return_value=connection):
            result = service.generate_recommendations(13)

        self.assertEqual(result["created"], 2)
        resource, question = result["recommendations"]
        self.assertEqual(resource["type"], "resource")
        self.assertEqual(resource["status"], "pending")
        self.assertIsNone(resource["resource_url"])
        self.assertEqual(resource["priority"], "Ưu tiên cao")
        self.assertIn("15 phút", resource["how_to_improve"])
        self.assertEqual(question["type"], "question")
        self.assertEqual(question["status"], "accepted")
        self.assertEqual(result["method"]["type"], "rule_based")


class RecommendationApiTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="recommendation-test-key")
        self.client = web_app.app.test_client()
        self.csrf = self.client.get("/api/csrf-token").get_json()["csrf_token"]

    def headers(self):
        return {"X-CSRF-Token": self.csrf}

    def student(self):
        with self.client.session_transaction() as session:
            session.update(user_id=13, role="Student")

    def test_routes_require_student_login(self):
        for method, path in [
            ("get", "/api/recommendations"),
            ("get", "/api/predictions/latest"),
            ("post", "/api/recommendations/generate"),
            ("post", "/api/predictions/refresh"),
        ]:
            response = getattr(self.client, method)(path, headers=self.headers())
            self.assertEqual(response.status_code, 401, path)

        with self.client.session_transaction() as session:
            session.update(user_id=2, role="Teacher")
        self.assertEqual(self.client.get("/api/recommendations").status_code, 403)
        self.assertEqual(self.client.get("/api/predictions/latest").status_code, 403)

    @patch("recommendations.service.list_recommendations", return_value={"recommendations": [], "method": {}})
    def test_list_uses_session_student(self, list_recommendations):
        self.student()
        response = self.client.get("/api/recommendations")
        self.assertEqual(response.status_code, 200)
        list_recommendations.assert_called_once_with(13)

    @patch("recommendations.service.generate_recommendations")
    def test_generate_requires_csrf(self, generate):
        self.student()
        self.assertEqual(self.client.post("/api/recommendations/generate").status_code, 400)
        generate.assert_not_called()

    @patch("recommendations.service.generate_recommendations", return_value={"created": 1, "recommendations": []})
    def test_generate_runs_for_signed_in_student(self, generate):
        self.student()
        response = self.client.post("/api/recommendations/generate", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["created"], 1)
        generate.assert_called_once_with(13)

    @patch("recommendations.service.respond_to_recommendation")
    def test_respond_validates_body(self, respond):
        self.student()
        for body in ({}, {"accepted": "yes"}, {"accepted": 1}):
            response = self.client.post("/api/recommendations/5/respond", json=body, headers=self.headers())
            self.assertEqual(response.status_code, 400)
        respond.assert_not_called()

    @patch("recommendations.service.respond_to_recommendation", return_value={"id": 5, "status": "accepted"})
    def test_respond_accepts_boolean(self, respond):
        self.student()
        response = self.client.post("/api/recommendations/5/respond", json={"accepted": True}, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        respond.assert_called_once_with(13, 5, True)

    @patch("recommendations.service.respond_to_recommendation", side_effect=RecommendationNotFound())
    def test_respond_unknown_recommendation_is_404(self, _respond):
        self.student()
        response = self.client.post("/api/recommendations/5/respond", json={"accepted": False}, headers=self.headers())
        self.assertEqual(response.status_code, 404)

    @patch("recommendations.service.refresh_prediction", side_effect=StudentProfileNotFound())
    def test_refresh_without_profile_is_404(self, _refresh):
        self.student()
        response = self.client.post("/api/predictions/refresh", headers=self.headers())
        self.assertEqual(response.status_code, 404)

    @patch("recommendations.service.get_prediction_overview", side_effect=web_app.pyodbc.Error("down"))
    def test_database_error_is_503_without_leaking_details(self, _overview):
        self.student()
        response = self.client.get("/api/predictions/latest")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("down", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()

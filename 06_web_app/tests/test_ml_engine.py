import unittest

import app as web_app
from ml_engine import FEATURE_COLS, StudentPerformanceModel, model_instance


class MLEngineTests(unittest.TestCase):
    def test_train_test_split_and_evaluation_metrics(self):
        metrics = model_instance.evaluation_metrics
        self.assertGreater(metrics["train_size"], 0)
        self.assertGreater(metrics["test_size"], 0)
        self.assertAlmostEqual(
            metrics["test_size"] / (metrics["train_size"] + metrics["test_size"]),
            0.20,
            delta=0.03,
        )
        self.assertGreater(metrics["r2"], 0.70)
        self.assertGreater(metrics["rmse"], 0)
        self.assertGreater(metrics["mae"], 0)
        self.assertIn("baseline_comparison", metrics)
        self.assertIn("ridge_r2", metrics["baseline_comparison"])

    def test_missing_data_imputation_and_confidence_widening(self):
        complete_row = {
            "AvgMastery": 0.75,
            "MinMastery": 0.60,
            "AvgAccuracyPercent": 78.0,
            "LatestScoreNormalized": 880.0,
            "StudyRatio7d": 0.90,
            "ActiveDays14": 10,
            "ActivePathProgressPercent": 65.0,
            "AvgTimeSec": 45.0,
            "SubmittedAttempts": 4,
        }
        sparse_row = {
            "AvgMastery": 0.75,
            "MinMastery": None,
            "AvgAccuracyPercent": None,
            "LatestScoreNormalized": None,
            "StudyRatio7d": None,
            "ActiveDays14": None,
            "ActivePathProgressPercent": None,
            "AvgTimeSec": None,
            "SubmittedAttempts": None,
        }
        out_complete = model_instance.predict_from_feature_row(complete_row, target_score=900)
        out_sparse = model_instance.predict_from_feature_row(sparse_row, target_score=900)

        self.assertEqual(out_complete.data_completeness, 1.0)
        self.assertEqual(out_complete.missing_features, [])
        self.assertLess(out_sparse.data_completeness, 0.5)
        self.assertEqual(len(out_sparse.missing_features), len(FEATURE_COLS) - 1)
        self.assertTrue(150.0 <= out_sparse.predicted_score <= 1200.0)

        width_complete = out_complete.confidence_interval[1] - out_complete.confidence_interval[0]
        width_sparse = out_sparse.confidence_interval[1] - out_sparse.confidence_interval[0]
        self.assertGreater(width_sparse, width_complete)

    def test_model_report_endpoint_requires_student(self):
        client = web_app.app.test_client()
        res_unauth = client.get("/api/predictions/model-report")
        self.assertEqual(res_unauth.status_code, 401)

        with client.session_transaction() as sess:
            sess["user_id"] = 13
            sess["role"] = "Student"
        res = client.get("/api/predictions/model-report")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("evaluation_metrics", data)
        self.assertIn("mae", data["evaluation_metrics"])
        self.assertIn("rmse", data["evaluation_metrics"])
        self.assertIn("r2", data["evaluation_metrics"])


if __name__ == "__main__":
    unittest.main()

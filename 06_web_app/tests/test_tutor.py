
import os
import unittest
from unittest.mock import MagicMock, patch

import app as web_app
from tutor_api import bp as tutor_bp, _call_gemini_api


class TutorApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Đăng ký Blueprint tạm thời cho test nếu app.py chưa đăng ký
        if "tutor" not in web_app.app.blueprints:
            web_app.app.register_blueprint(tutor_bp)

    def setUp(self):
        web_app.app.config.update(TESTING=True, SECRET_KEY="test-secret-key-tutor")
        self.client = web_app.app.test_client()
        csrf_res = self.client.get("/api/csrf-token").get_json()
        self.csrf_token = csrf_res["csrf_token"]

    def auth_headers(self, token=None):
        return {"X-CSRF-Token": token or self.csrf_token}

    def login_as_student(self, user_id=3, fullname="Học Sinh Mẫu"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["email"] = "student@test.local"
            sess["fullname"] = fullname
            sess["role"] = "Student"

    def test_status_endpoint_returns_configuration(self):
        """Kiểm tra API kiểm tra trạng thái AI model."""
        res = self.client.get("/api/tutor/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("configured", data)
        self.assertIn("active_model", data)
        self.assertIn("instructions", data)

    def test_tutor_requires_authentication(self):
        """Chưa đăng nhập thì không thể vào lịch sử hoặc đặt câu hỏi."""
        res_history = self.client.get("/api/tutor/history")
        self.assertEqual(res_history.status_code, 401)

        res_ask = self.client.post(
            "/api/tutor/ask",
            json={"message": "Xin chào"},
            headers=self.auth_headers()
        )
        self.assertEqual(res_ask.status_code, 401)

    def test_tutor_rejects_non_student_role(self):
        """Giáo viên hoặc admin không dùng giao diện Tutor của học sinh."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["role"] = "Teacher"

        res = self.client.get("/api/tutor/history")
        self.assertEqual(res.status_code, 403)
        self.assertIn("chỉ hỗ trợ tài khoản học sinh", res.get_json()["error"])

    @patch("tutor_api.pyodbc.connect")
    def test_get_available_questions(self, mock_connect):
        """Học sinh lấy danh sách câu hỏi để chọn giải thích."""
        self.login_as_student()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("id",), ("content",), ("difficulty",), ("explanation",), ("competency",), ("subject",)
        ]
        mock_cursor.fetchall.return_value = [
            (1, "Câu hỏi logic 1", 3, "Lời giải mẫu", "Tư duy logic", "Toán học"),
            (2, "Câu hỏi đại số 2", 2, "Lời giải 2", "Đại số", "Toán học"),
        ]

        res = self.client.get("/api/tutor/questions")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("questions", data)
        self.assertEqual(len(data["questions"]), 2)
        self.assertEqual(data["questions"][0]["content"], "Câu hỏi logic 1")

    @patch("tutor_api.pyodbc.connect")
    def test_get_history_empty_and_with_messages(self, mock_connect):
        """Lấy lịch sử tin nhắn của học sinh."""
        self.login_as_student()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Trường hợp 1: Chưa có phiên hội thoại nào
        mock_cursor.fetchone.return_value = None
        res_empty = self.client.get("/api/tutor/history")
        self.assertEqual(res_empty.status_code, 200)
        self.assertIsNone(res_empty.get_json()["session_id"])
        self.assertEqual(res_empty.get_json()["messages"], [])

        # Trường hợp 2: Đã có phiên và có tin nhắn
        mock_cursor.description = [("SessionID",), ("StartedAt",)]
        mock_cursor.fetchone.return_value = (10, "2026-11-20 10:00:00")
        
        # Cursor tiếp theo cho SELECT messages
        mock_cursor.fetchall.return_value = [
            (1, "USER", "Em chưa hiểu câu này", 1, "2026-11-20 10:01:00", "Nội dung câu 1", "Logic"),
            (2, "AI", "Để giải câu này...", 1, "2026-11-20 10:01:02", "Nội dung câu 1", "Logic"),
        ]
        # Mô phỏng fetchall với mô tả cột
        def side_effect_desc():
            mock_cursor.description = [
                ("id",), ("sender",), ("content",), ("question_id",),
                ("sent_at",), ("question_content",), ("competency_name",)
            ]
        mock_cursor.execute.side_effect = lambda *args, **kwargs: side_effect_desc()

        res_with_msgs = self.client.get("/api/tutor/history")
        self.assertEqual(res_with_msgs.status_code, 200)
        data = res_with_msgs.get_json()
        self.assertEqual(data["session_id"], 10)
        self.assertTrue(len(data["messages"]) >= 1)

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    @patch("tutor_api.pyodbc.connect")
    def test_ask_tutor_internal_fallback(self, mock_connect):
        """Học sinh hỏi giải thích câu hỏi cụ thể khi không có key ngoài."""
        self.login_as_student()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock tìm session_id = 10
        mock_cursor.fetchone.side_effect = [
            (1, "Cho dãy số 2, 6, 12...", 3, "Quy luật n*(n+1)", "Tư duy logic"), # Question
            (1, "Cho dãy số 2, 6, 12...", 3, "Quy luật n*(n+1)", "Tư duy logic"), # Trong _generate_internal_explanation
            (10,), # Session có sẵn
        ]
        mock_cursor.fetchall.side_effect = [
            [("A", "40", 0), ("B", "42", 1)], # Options trong context
            [("A", "40", 0), ("B", "42", 1)], # Options trong internal explanation
        ]
        mock_cursor.description = [
            ("QuestionID",), ("Content",), ("Difficulty",), ("Explanation",), ("CompetencyName",)
        ]

        res = self.client.post(
            "/api/tutor/ask",
            json={"message": "Giải thích chi tiết giúp em câu này", "question_id": 1},
            headers=self.auth_headers()
        )

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("NovaPath Knowledge Base", data["model_used"])
        self.assertIn("Giải thích chi tiết cho câu hỏi", data["reply"])
        mock_conn.commit.assert_called()

    @patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test"})
    @patch("tutor_api._call_gemini_api")
    @patch("tutor_api.search")
    @patch("tutor_api.pyodbc.connect")
    def test_ask_persists_document_provenance(self, connect, search, call):
        self.login_as_student()
        cursor = connect.return_value.cursor.return_value
        cursor.fetchone.return_value = (10,)
        search.return_value = [{"source": "prob", "title": "Tài liệu", "ordinal": 1,
                                "text": "Tổng xác suất của toàn bộ không gian mẫu là 1."}]
        call.side_effect = [
            ('{"answer":"Tổng bằng 1 [1].","citations":[{"id":1,"quote":"Tổng xác suất của toàn bộ không gian mẫu là 1."}]}', "model"),
            ('{"valid":true}', "model"),
        ]
        response = self.client.post("/api/tutor/ask", json={"message": "Tổng xác suất?"},
                                    headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["origin"], "document")
        self.assertIn("Tài liệu (prob, đoạn 1)", result["reply"])
        inserts = [args for args, _ in cursor.execute.call_args_list if "VALUES (?, 'AI'" in args[0]]
        self.assertEqual(inserts[0][1], (10, result["reply"], None))

    @patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test"})
    @patch("tutor_api._call_gemini_api")
    def test_generate_rejects_question_with_wrong_answer(self, call):
        self.login_as_student()
        call.side_effect = [
            ('{"question":"Giải phương trình x + 1 = 2.", "options":["1","2","3","-1"],'
             '"answer":"B","explanation":"Trừ hai vế cho 1, ta được x = 1."}', "model"),
            ('{"answer":"A","valid":true}', "model"),
        ]
        response = self.client.post("/api/tutor/generate", json={"topic": "Toán", "difficulty": 1},
                                    headers=self.auth_headers())
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("question", response.get_json())

    @patch("tutor_rag.urllib.request.urlopen")
    def test_call_gemini_api_success(self, mock_urlopen):
        """Kiểm tra gọi mock Google Gemini API thành công."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'''
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Chao em! Day la huong dan giai tu AI Gemini."}
                        ]
                    }
                }
            ]
        }
        '''
        mock_urlopen.return_value.__enter__.return_value = mock_response

        reply, model_name = _call_gemini_api("dummy-test-key", "Giai giup em cau nay")
        self.assertEqual(reply, "Chao em! Day la huong dan giai tu AI Gemini.")
        self.assertIn("Google Gemini", model_name)

    @patch("tutor_api.pyodbc.connect")
    def test_clear_tutor_session(self, mock_connect):
        """Kiểm tra tạo phiên hội thoại mới."""
        self.login_as_student()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (99,) # New SCOPE_IDENTITY

        res = self.client.post("/api/tutor/clear", headers=self.auth_headers())
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["session_id"], 99)
        mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()

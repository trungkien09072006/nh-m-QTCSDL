import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from tutor_generation import generate_question, grounded_reply
from tutor_rag import DIMENSIONS, ingest, search


class TutorRagTests(unittest.TestCase):
    def test_persistent_vector_search_and_replace(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "index with spaces.sqlite3"
            with patch.dict(os.environ, {"TUTOR_INDEX_PATH": str(path), "TUTOR_MAX_COSINE_DISTANCE": "0.40"}):
                self.assertEqual(search("test", "xác suất"), [])
                relevant = [1.0, 0.0] + [0.0] * (DIMENSIONS - 2)
                irrelevant = [0.0, 1.0] + [0.0] * (DIMENSIONS - 2)
                with patch("tutor_rag.embed", side_effect=[relevant, irrelevant, relevant, irrelevant, relevant]) as embed:
                    ingest(path, "test", "prob", "Xác suất", "Quy tắc cộng trong xác suất.")
                    ingest(path, "test", "lang", "Ngữ văn", "Cấu trúc của bài nghị luận.")
                    ingest(path, "test", "prob", "Xác suất", "Quy tắc cộng trong xác suất.")
                    matches = search("test", "xác suất")
                    self.assertEqual([row["source"] for row in matches], ["prob"])
                    self.assertEqual(matches[0]["ordinal"], 1)
                    ingest(path, "test", "prob", "Xác suất", "Nội dung tài liệu đã đổi.")
                    self.assertEqual(search("test", "xác suất"), [])
                    self.assertEqual(embed.call_count, 5)

    def test_grounded_answer_requires_exact_quote_and_review(self):
        source = {"title": "Xác suất", "source": "prob", "ordinal": 2,
                  "text": "Tổng xác suất của toàn bộ không gian mẫu là 1."}
        response = {"answer": "Tổng bằng 1 [1].", "citations": [{"id": 1, "quote": source["text"]}]}
        call = Mock(side_effect=[(json.dumps(response), "model"), ('{"valid":true}', "model")])
        reply, _ = grounded_reply(call, "key", "Tổng bằng bao nhiêu?", None, [source])
        self.assertIn("Xác suất (prob, đoạn 2)", reply)
        self.assertIn(source["text"], reply)

        response["citations"][0]["quote"] = "Trích dẫn không xuất hiện trong tài liệu."
        call = Mock(return_value=(json.dumps(response), "model"))
        self.assertIsNone(grounded_reply(call, "key", "Tổng bằng bao nhiêu?", None, [source])[0])
        call.assert_called_once()

    def test_exercise_requires_independent_answer_and_valid_solution(self):
        draft = {"question": "Giải phương trình x + 1 = 2.", "options": ["1", "2", "3", "-1"],
                 "answer": "A", "explanation": "Trừ hai vế cho 1, ta được x = 1."}
        response = (json.dumps(draft), "model")
        call = Mock(side_effect=[response, ('{"answer":"B","valid":true}', "model")])
        self.assertIsNone(generate_question(call, "key", "Toán", 1, None))
        self.assertEqual(call.call_count, 2)

        call = Mock(side_effect=[response, ('{"answer":"A","valid":true}', "model"), ('{"valid":false}', "model")])
        self.assertIsNone(generate_question(call, "key", "Toán", 1, None))

        call = Mock(side_effect=[response, ('{"answer":"A","valid":true}', "model"), ('{"valid":true}', "model")])
        exercise = generate_question(call, "key", "Toán", 1, None)
        self.assertEqual(exercise["origin"], "ai_generated")
        self.assertEqual(exercise["answer"], "A")

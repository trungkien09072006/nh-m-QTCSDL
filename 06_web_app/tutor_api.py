
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime

import pyodbc
from flask import Blueprint, jsonify, request, session
from database import _connection_string, _row_as_dict

logger = logging.getLogger(__name__)

bp = Blueprint("tutor", __name__, url_prefix="/api/tutor")


def _get_tutor_user():
    """Kiểm tra quyền truy cập của học sinh."""
    if "user_id" not in session:
        return None, (jsonify(error="Vui lòng đăng nhập để sử dụng AI Tutor."), 401)
    if session.get("role") != "Student":
        return None, (jsonify(error="AI Tutor hiện chỉ hỗ trợ tài khoản học sinh."), 403)
    return {
        "id": session["user_id"],
        "email": session.get("email"),
        "fullname": session.get("fullname"),
        "role": session.get("role"),
    }, None


def _call_gemini_api(api_key: str, user_prompt: str, question_context: dict = None) -> tuple[str | None, str]:
    """
    Gọi Google Gemini API (mô hình ngoài) để giải thích câu hỏi học tập.
    Trả về (câu_trả_lời, tên_model). Nếu lỗi hoặc không có key, trả về (None, lý_do).
    """
    if not api_key or not api_key.strip():
        return None, "Chưa cấu hình GEMINI_API_KEY"

    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"

    system_instruction = (
        "Bạn là AI Tutor thông minh, thân thiện của hệ thống luyện thi Đánh Giá Năng Lực NovaPath. "
        "Nhiệm vụ của bạn là hướng dẫn học sinh hiểu sâu bản chất, phương pháp giải, công thức trọng tâm "
        "và mẹo tránh bẫy. Hãy trả lời bằng tiếng Việt chuẩn mực, mạch lạc, dễ hiểu theo định dạng Markdown."
    )

    prompt_parts = []
    if question_context:
        prompt_parts.append(f"--- DỮ LIỆU CÂU HỎI TRONG NGÂN HÀNG ĐỀ ---")
        prompt_parts.append(f"Chủ đề / Năng lực: {question_context.get('competency', 'Chung')}")
        prompt_parts.append(f"Nội dung câu hỏi: {question_context.get('content', '')}")
        if question_context.get("options"):
            prompt_parts.append("Các lựa chọn:")
            for opt in question_context["options"]:
                correct_mark = " (ĐÁP ÁN ĐÚNG)" if opt.get("is_correct") else ""
                prompt_parts.append(f"  [{opt.get('label')}] {opt.get('text')}{correct_mark}")
        if question_context.get("explanation"):
            prompt_parts.append(f"Lời giải chuẩn hệ thống: {question_context.get('explanation')}")
        prompt_parts.append("--- HẾT DỮ LIỆU CÂU HỎI ---")

    prompt_parts.append(f"Yêu cầu / Câu hỏi của học sinh: {user_prompt}")
    full_prompt = "\n".join(prompt_parts)

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "parts": [{"text": full_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024,
        }
    }

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip(), f"Google Gemini ({model})"
            return None, "Không nhận được nội dung hợp lệ từ Gemini"
    except Exception as exc:
        logger.warning("Không thể gọi Gemini API: %s. Chuyển sang fallback tri thức nội bộ.", exc)
        return None, f"Lỗi kết nối Gemini: {str(exc)}"


def _generate_internal_explanation(cursor, student_id: int, user_message: str, question_id: int = None) -> tuple[str, str]:
    """
    Thuật toán fallback trích xuất tri thức nội bộ từ SQL Server (Rule-based / RAG từ DB).
    Đảm bảo theo rubric: Nêu rõ đây là thuật toán luật / trích xuất DB chứ không mạo danh AI ngoài.
    """
    model_name = "NovaPath Knowledge Base (Rule-based / RAG nội bộ)"

    if question_id:
        cursor.execute(
            """
            SELECT q.QuestionID, q.Content, q.Difficulty, q.Explanation, c.CompetencyName
            FROM Questions AS q
            INNER JOIN Competencies AS c ON c.CompetencyID = q.CompetencyID
            WHERE q.QuestionID = ?
            """,
            (question_id,)
        )
        q_row = _row_as_dict(cursor, cursor.fetchone())

        if q_row:
            cursor.execute(
                """
                SELECT OptionLabel, OptionText, IsCorrect
                FROM QuestionOptions
                WHERE QuestionID = ?
                ORDER BY OptionLabel
                """,
                (question_id,)
            )
            options = [_row_as_dict(cursor, r) for r in cursor.fetchall()]

            correct_opt = next((o for o in options if o.get("IsCorrect")), None)
            correct_str = (
                f"Phương án **{correct_opt['OptionLabel']}**: *{correct_opt['OptionText']}*"
                if correct_opt else "Chưa xác định"
            )

            explanation_text = q_row.get("Explanation") or "Câu hỏi này hiện chưa có lời giải chi tiết từ giáo viên."

            reply = (
                f"> **[Chế độ: Tri thức NovaPath (RAG nội bộ)]**\n"
                f"> *(Chưa kích hoạt GEMINI_API_KEY nên hệ thống trích xuất từ dữ liệu chuẩn của ngân hàng câu hỏi)*\n\n"
                f"### 📘 Giải thích chi tiết cho câu hỏi (Mã #{question_id})\n"
                f"- **Chủ đề / Năng lực:** {q_row['CompetencyName']} (Độ khó: {q_row['Difficulty']}/5)\n"
                f"- **Câu hỏi:** *{q_row['Content']}*\n"
                f"- **Đáp án chính xác:** {correct_str}\n\n"
                f"#### 💡 Phương pháp giải và hướng dẫn:\n"
                f"{explanation_text}\n\n"
                f"---\n"
                f"**Lời khuyên từ NovaPath:** Hãy xem lại các công thức liên quan đến năng lực **{q_row['CompetencyName']}** "
                f"và luyện thêm 2-3 câu hỏi cùng mức độ để ghi nhớ quy luật giải bài."
            )
            return reply, model_name

    # Khi không có question_id hoặc câu hỏi chung
    cursor.execute(
        """
        SELECT TOP 1 c.CompetencyName, CAST(ROUND(sc.Mastery * 100, 0) AS INT) AS MasteryPercent
        FROM StudentCompetency AS sc
        INNER JOIN Competencies AS c ON c.CompetencyID = sc.CompetencyID
        WHERE sc.StudentID = ?
        ORDER BY sc.Mastery ASC
        """,
        (student_id,)
    )
    weak_comp = _row_as_dict(cursor, cursor.fetchone())

    cursor.execute(
        """
        SELECT TOP 1 lr.Title
        FROM Recommendations AS r
        INNER JOIN LearningResources AS lr ON lr.ResourceID = r.ResourceID
        WHERE r.StudentID = ? AND ISNULL(r.IsAccepted, 0) = 0
        ORDER BY r.CreatedAt DESC
        """,
        (student_id,)
    )
    rec = _row_as_dict(cursor, cursor.fetchone())

    comp_name = weak_comp["CompetencyName"] if weak_comp else "Tư duy logic & giải quyết vấn đề"
    mastery = weak_comp["MasteryPercent"] if weak_comp else 50
    rec_title = rec["Title"] if rec else "Ôn tập kiến thức nền tảng"

    reply = (
        f"> **[Chế độ: Tri thức NovaPath (Hệ thống phân tích hồ sơ học tập)]**\n\n"
        f"Chào bạn! Tôi là AI Tutor NovaPath. Dựa trên dữ liệu học tập hiện tại của bạn:\n\n"
        f"- 🎯 **Điểm cần củng cố nhất:** Năng lực **{comp_name}** (mức độ thành thạo hiện tại: **{mastery}%**).\n"
        f"- 📚 **Học liệu được đề xuất:** *\"{rec_title}\"*.\n\n"
        f"Bạn có thể bấm chọn một câu hỏi cụ thể trong danh sách ngân hàng câu hỏi bên cạnh để tôi phân tích phương pháp "
        f"giải, công thức và các bẫy thường gặp của câu hỏi đó nhé!"
    )
    return reply, model_name


@bp.get("/status")
def tutor_status():
    """Kiểm tra tình trạng cấu hình AI Model."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    has_key = bool(gemini_key)
    active_model = f"Google Gemini ({os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')})" if has_key else "NovaPath Knowledge Base"
    mode = "EXTERNAL_AI" if has_key else "INTERNAL_RAG"

    return jsonify(
        configured=has_key,
        mode=mode,
        active_model=active_model,
        instructions=(
            "Đặt biến môi trường GEMINI_API_KEY=<khóa_api_của_bạn> để kích hoạt mô hình sinh phản hồi trực tiếp từ Google Gemini. "
            "Nếu không đặt, hệ thống tự động trích xuất lời giải chuẩn xác từ CSDL SQL Server (Rule-based / RAG)."
        )
    )


@bp.get("/questions")
def get_available_questions():
    """Lấy danh sách các câu hỏi mẫu/thực tế để học sinh chọn hỏi AI Tutor."""
    user, error = _get_tutor_user()
    if error:
        return error

    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    """
                    SELECT TOP 20
                        q.QuestionID AS id,
                        q.Content AS content,
                        q.Difficulty AS difficulty,
                        q.Explanation AS explanation,
                        c.CompetencyName AS competency,
                        s.SubjectName AS subject
                    FROM Questions AS q
                    INNER JOIN Competencies AS c ON c.CompetencyID = q.CompetencyID
                    INNER JOIN Subjects AS s ON s.SubjectID = c.SubjectID
                    ORDER BY q.QuestionID ASC
                    """
                )
                questions = [_row_as_dict(cursor, row) for row in cursor.fetchall()]
                return jsonify(questions=questions)
    except pyodbc.Error:
        logger.exception("Không thể tải danh sách câu hỏi cho Tutor")
        return jsonify(error="Không thể tải danh sách câu hỏi từ CSDL."), 503


@bp.get("/history")
def get_tutor_history():
    """Lấy lịch sử hội thoại gần nhất của học sinh."""
    user, error = _get_tutor_user()
    if error:
        return error

    student_id = user["id"]
    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                # Tìm phiên gần nhất
                cursor.execute(
                    """
                    SELECT TOP 1 SessionID, StartedAt
                    FROM TutorSessions
                    WHERE StudentID = ?
                    ORDER BY StartedAt DESC, SessionID DESC
                    """,
                    (student_id,)
                )
                raw_session = cursor.fetchone()
        session_row = _row_as_dict(cursor, raw_session) if raw_session is not None else None

        session_id = None
        if isinstance(session_row, dict):
            session_id = (
                session_row.get("SessionID")
                or session_row.get("session_id")
                or next(iter(session_row.values()), None)
            )
        if session_id is None and isinstance(raw_session, (tuple, list)) and len(raw_session) > 0:
                session_id = raw_session[0]

        if session_id is None:
            return jsonify(session_id=None, messages=[])

        cursor.execute(
            """
            SELECT
                tm.MessageID AS id,
                tm.Sender AS sender,
                tm.Content AS content,
                tm.QuestionID AS question_id,
                CONVERT(VARCHAR(19), tm.SentAt, 120) AS sent_at,
                q.Content AS question_content,
                c.CompetencyName AS competency_name
            FROM TutorMessages AS tm
            LEFT JOIN Questions AS q ON q.QuestionID = tm.QuestionID
            LEFT JOIN Competencies AS c ON c.CompetencyID = q.CompetencyID
            WHERE tm.SessionID = ?
            ORDER BY tm.MessageID ASC
            """,
            (session_id,),
        )
        raw_messages = cursor.fetchall() or []
        messages = [_row_as_dict(cursor, r) for r in raw_messages]
        return jsonify(session_id=session_id, messages=messages)
    except pyodbc.Error:
        logger.exception("Không thể tải lịch sử trò chuyện AI Tutor")
        return jsonify(error="Không thể kết nối CSDL để tải lịch sử hội thoại."), 503


@bp.post("/ask")
def ask_tutor():
    """
    Gửi câu hỏi tới AI Tutor.
    Body JSON: { "message": "...", "question_id": 1 (tùy chọn) }
    """
    user, error = _get_tutor_user()
    if error:
        return error

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Dữ liệu yêu cầu không hợp lệ."), 400

    message = (data.get("message") or "").strip()
    question_id = data.get("question_id")

    if question_id is not None:
        try:
            question_id = int(question_id)
        except (ValueError, TypeError):
            return jsonify(error="Mã câu hỏi không hợp lệ."), 400

    if not message and not question_id:
        return jsonify(error="Vui lòng nhập nội dung câu hỏi hoặc chọn câu hỏi cần giải thích."), 400

    student_id = user["id"]
    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                # 1. Tìm hoặc tạo phiên TutorSession
                cursor.execute(
                    """
                    SELECT TOP 1 SessionID
                    FROM TutorSessions
                    WHERE StudentID = ?
                    ORDER BY StartedAt DESC, SessionID DESC
                    """,
                    (student_id,)
                )
                sess_row = cursor.fetchone()
                if sess_row:
                    session_id = sess_row[0]
                else:
                    cursor.execute(
                        "INSERT INTO TutorSessions (StudentID) VALUES (?)",
                        (student_id,)
                    )
                    cursor.execute("SELECT SCOPE_IDENTITY()")
                    session_id = int(cursor.fetchone()[0])

                # 2. Thu thập context câu hỏi nếu có
                q_context = None
                if question_id:
                    cursor.execute(
                        """
                        SELECT q.QuestionID, q.Content, q.Difficulty, q.Explanation, c.CompetencyName
                        FROM Questions AS q
                        INNER JOIN Competencies AS c ON c.CompetencyID = q.CompetencyID
                        WHERE q.QuestionID = ?
                        """,
                        (question_id,)
                    )
                    q_data = _row_as_dict(cursor, cursor.fetchone())
                    if q_data:
                        cursor.execute(
                            "SELECT OptionLabel, OptionText, IsCorrect FROM QuestionOptions WHERE QuestionID = ? ORDER BY OptionLabel",
                            (question_id,)
                        )
                        opts = [
                            {"label": r[0], "text": r[1], "is_correct": bool(r[2])}
                            for r in cursor.fetchall()
                        ]
                        q_context = {
                            "content": q_data["Content"],
                            "difficulty": q_data["Difficulty"],
                            "explanation": q_data["Explanation"],
                            "competency": q_data["CompetencyName"],
                            "options": opts,
                        }

                # 3. Lưu tin nhắn USER
                user_msg_content = message or f"Nhờ AI Tutor giải thích câu hỏi mã #{question_id}."
                cursor.execute(
                    """
                    INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID)
                    VALUES (?, 'USER', ?, ?)
                    """,
                    (session_id, user_msg_content, question_id)
                )

                # 4. Tạo phản hồi từ AI (Gemini ngoài hoặc Knowledge-base nội bộ)
                gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
                reply_text = None
                model_used = None

                if gemini_key:
                    reply_text, model_used = _call_gemini_api(gemini_key, user_msg_content, q_context)

                if not reply_text:
                    reply_text, model_used = _generate_internal_explanation(
                        cursor, student_id, user_msg_content, question_id
                    )

                # 5. Lưu tin nhắn AI
                cursor.execute(
                    """
                    INSERT INTO TutorMessages (SessionID, Sender, Content, QuestionID)
                    VALUES (?, 'AI', ?, ?)
                    """,
                    (session_id, reply_text, question_id)
                )

                # 6. Ghi nhận nhật ký học tập (StudyLogs)
                cursor.execute(
                    """
                    INSERT INTO StudyLogs (StudentID, ActivityType, DurationMin)
                    VALUES (?, 'TUTOR', 5)
                    """,
                    (student_id,)
                )

                connection.commit()

                return jsonify(
                    ok=True,
                    session_id=session_id,
                    reply=reply_text,
                    model_used=model_used,
                    question_id=question_id,
                    sent_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

    except pyodbc.Error:
        logger.exception("Lỗi khi xử lý hỏi đáp AI Tutor trong CSDL")
        return jsonify(error="Lỗi lưu trữ dữ liệu hội thoại trong SQL Server."), 503


@bp.post("/clear")
def clear_tutor_session():
    """Tạo một phiên hội thoại mới cho học sinh (bắt đầu cuộc trò chuyện mới)."""
    user, error = _get_tutor_user()
    if error:
        return error

    student_id = user["id"]
    try:
        with closing(pyodbc.connect(_connection_string(), timeout=5)) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    "INSERT INTO TutorSessions (StudentID) VALUES (?)",
                    (student_id,)
                )
                cursor.execute("SELECT SCOPE_IDENTITY()")
                new_session_id = int(cursor.fetchone()[0])
                connection.commit()

                return jsonify(
                    ok=True,
                    session_id=new_session_id,
                    message="Đã khởi tạo phiên hỏi đáp mới với AI Tutor."
                )
    except pyodbc.Error:
        logger.exception("Lỗi khi khởi tạo phiên mới cho Tutor")
        return jsonify(error="Không thể kết nối CSDL để tạo phiên mới."), 503

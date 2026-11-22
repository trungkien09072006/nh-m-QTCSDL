"""Gợi ý học và dự đoán điểm (phần 2).

Module này KHÔNG tự tính mô hình AI. Nó nối các thủ tục SQL đã có
(``sp_GenerateRecommendations``, ``sp_CalculateScorePrediction``) vào API và
bổ sung phần giải thích cho học sinh: vì sao được gợi ý, cách cải thiện, độ tin cậy.

Cả hai kết quả đều là THUẬT TOÁN LUẬT / CÔNG THỨC TRỌNG SỐ (heuristic), không phải
mô hình học máy và xác suất chưa được hiệu chuẩn hay kiểm chứng. Giao diện phải nói rõ
điều đó (xem ``RECOMMENDATION_METHOD`` và ``PREDICTION_METHOD``).
"""

from contextlib import closing
from datetime import date, datetime
from decimal import Decimal

import pyodbc

from database import _connection_string, _fetch_all

# Ngưỡng "cần ôn" trùng với sp_GenerateRecommendations và vw_StudentCompetencyProfile.
MASTERY_THRESHOLD = 0.65
# Trọng số trùng với sp_CalculateScorePrediction.
W_MASTERY, W_EXAM, W_STUDY = 0.55, 0.30, 0.15
MAX_SCORE = 1200.0
# Không ghi thêm dòng dự đoán nếu dữ liệu chưa đổi và dự đoán gần nhất còn rất mới.
PREDICTION_REUSE_SECONDS = 60
# Sai lệch cho phép khi so bản tính lại bằng Python với điểm đã lưu trong SQL.
STALE_TOLERANCE = 1.0

RECOMMENDATION_METHOD = {
    "type": "rule_based",
    "label": "Thuật toán luật (rule-based)",
    "description": (
        "Gợi ý học liệu cho chủ đề có mức thành thạo dưới 65% và gợi ý ôn lại các câu "
        "đã làm sai trong bài đã nộp. Đây là quy tắc cố định, không dùng mô hình học "
        "máy và chưa được kiểm chứng về hiệu quả học tập."
    ),
}

PREDICTION_METHOD = {
    "type": "heuristic_formula",
    "label": "Công thức trọng số (heuristic)",
    "description": (
        "Điểm dự đoán = 55% mức thành thạo trung bình + 30% điểm bài thi gần nhất "
        "+ 15% mức đáp ứng thời lượng học 7 ngày. Không phải mô hình học máy. "
        "Khả năng đạt mục tiêu chỉ là ước lượng theo công thức, chưa được hiệu chuẩn "
        "hay kiểm chứng bằng dữ liệu thi thật; hãy xem như tham khảo."
    ),
}


class RecommendationNotFound(Exception):
    pass


class StudentProfileNotFound(Exception):
    pass


def _iso(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _num(value, digits=None):
    if value is None:
        return None
    number = float(value) if isinstance(value, Decimal) else value
    return round(number, digits) if digits is not None else number


def _safe_url(url):
    """Chỉ cho phép liên kết http/https để tránh javascript: hoặc scheme lạ."""
    if isinstance(url, str) and url.lower().startswith(("http://", "https://")):
        return url
    return None


def _connect():
    return closing(pyodbc.connect(_connection_string(), timeout=5))


def _priority(mastery):
    if mastery is None:
        return None
    if mastery < 0.40:
        return "Ưu tiên cao"
    if mastery < MASTERY_THRESHOLD:
        return "Ưu tiên vừa"
    return None


# ---------------------------------------------------------------------------
# Phần tính toán thuần Python (không cần CSDL, dễ kiểm thử)
# ---------------------------------------------------------------------------

def compute_prediction(inputs):
    """Tính lại đúng công thức của sp_CalculateScorePrediction để giải thích từng thành phần."""
    mastery_defaulted = inputs["avg_mastery"] is None
    avg_mastery = 0.5 if mastery_defaulted else float(inputs["avg_mastery"])
    latest = inputs["latest_score"]

    if latest is None:
        exam_points, exam_source = avg_mastery * MAX_SCORE, "mastery"
    elif latest <= 100:
        exam_points, exam_source = latest * 12.0, "exam"
    else:
        exam_points, exam_source = float(latest), "exam"

    weekly_goal = (inputs["daily_study_min"] or 60) * 7
    if weekly_goal <= 0:
        study_ratio = 0.5
    else:
        study_ratio = min(1.0, inputs["minutes_7d"] / weekly_goal)

    mastery_part = avg_mastery * MAX_SCORE * W_MASTERY
    exam_part = exam_points * W_EXAM
    study_part = study_ratio * MAX_SCORE * W_STUDY
    score = min(MAX_SCORE, max(0.0, round(mastery_part + exam_part + study_part, 2)))

    target = inputs["target_score"] or 0
    if target <= 0:
        probability = None
    elif score >= target:
        probability = 0.9
    else:
        probability = round(score / target * 0.85, 4)

    return {
        "score": score,
        "probability": probability,
        "avg_mastery": avg_mastery,
        "mastery_defaulted": mastery_defaulted,
        "exam_points": exam_points,
        "exam_source": exam_source,
        "study_ratio": study_ratio,
        "weekly_goal_min": weekly_goal,
        "minutes_7d": inputs["minutes_7d"],
        "parts": {
            "mastery": round(mastery_part, 1),
            "exam": round(exam_part, 1),
            "study": round(study_part, 1),
        },
    }


def risk_level(probability):
    """Cùng ngưỡng với vw_LatestPrediction."""
    if probability is None:
        return None
    if probability >= 0.80:
        return "An toàn"
    if probability >= 0.60:
        return "Cần theo dõi"
    return "Nguy cơ cao"


def data_quality(inputs):
    answered = inputs["answered_count"]
    attempts = inputs["submitted_attempts"]
    if answered < 10 or inputs["competency_count"] == 0:
        level, note = "low", "Dữ liệu còn ít nên dự đoán chỉ mang tính tham khảo thấp."
    elif answered < 30:
        level, note = "medium", "Dữ liệu ở mức vừa phải; dự đoán sẽ ổn định hơn khi làm thêm bài."
    else:
        level, note = "good", "Đã có khá nhiều dữ liệu, nhưng công thức vẫn chưa được kiểm chứng."
    return {
        "level": level,
        "answered_count": answered,
        "submitted_attempts": attempts,
        "competency_count": inputs["competency_count"],
        "note": note,
    }


def _tip(kind, title, detail):
    return {"kind": kind, "title": title, "detail": detail}


def build_improvements(inputs, current, weak):
    """Các bước cải thiện dựa trên luật, mỗi bước đều nêu căn cứ từ dữ liệu."""
    tips = []
    target = inputs["target_score"] or 0

    if inputs["competency_count"] == 0 and inputs["submitted_attempts"] == 0:
        tips.append(_tip(
            "data",
            "Chưa có dữ liệu học tập",
            "Hãy làm bài chẩn đoán hoặc một bài luyện tập. Hiện hệ thống tạm dùng mức "
            "thành thạo mặc định 50% nên kết quả chưa phản ánh năng lực thật.",
        ))

    if target <= 0:
        tips.append(_tip(
            "profile",
            "Chưa đặt điểm mục tiêu",
            "Cập nhật điểm mục tiêu trong Hồ sơ để tính khoảng cách và khả năng đạt mục tiêu.",
        ))
    else:
        gap = target - current["score"]
        if gap > 0:
            detail = f"Điểm dự đoán {current['score']:.0f}/{MAX_SCORE:.0f}, mục tiêu {target}."
            if current["exam_source"] == "exam":
                needed = (target - current["exam_points"] * W_EXAM
                          - current["study_ratio"] * MAX_SCORE * W_STUDY) / (MAX_SCORE * W_MASTERY)
            else:
                needed = (target - current["study_ratio"] * MAX_SCORE * W_STUDY) / (
                    MAX_SCORE * (W_MASTERY + W_EXAM))
            if needed > 1:
                detail += (" Theo công thức hiện tại, chỉ nâng mức thành thạo là chưa đủ; "
                           "cần cải thiện thêm điểm bài thi và thời lượng học.")
            elif needed > current["avg_mastery"]:
                detail += (f" Nếu điểm bài thi và thời lượng học giữ nguyên, mức thành thạo "
                           f"trung bình cần đạt khoảng {needed * 100:.0f}% "
                           f"(hiện {current['avg_mastery'] * 100:.0f}%).")
            tips.append(_tip("gap", f"Còn thiếu khoảng {gap:.0f} điểm so với mục tiêu", detail))

    for item in weak:
        pct = round(item["mastery"] * 100)
        if item["resource_title"]:
            detail = (f"Mức thành thạo {pct}% (ngưỡng đạt {round(MASTERY_THRESHOLD * 100)}%). "
                      f"Bắt đầu với “{item['resource_title']}” (~{item['resource_min']} phút), "
                      "sau đó làm lại vài câu cùng chủ đề để kiểm tra.")
        else:
            detail = (f"Mức thành thạo {pct}% (ngưỡng đạt {round(MASTERY_THRESHOLD * 100)}%). "
                      "Chưa có học liệu cho chủ đề này; hãy làm thêm câu hỏi cùng chủ đề.")
        tips.append(_tip("competency", f"Ưu tiên chủ đề “{item['name']}”", detail))

    daily = inputs["daily_study_min"] or 0
    weekly_goal = current["weekly_goal_min"]
    if daily > 0 and current["minutes_7d"] < weekly_goal:
        missing = weekly_goal - current["minutes_7d"]
        tips.append(_tip(
            "study",
            "Tăng thời lượng học",
            f"7 ngày qua bạn học {current['minutes_7d']}/{weekly_goal} phút theo mục tiêu "
            f"{daily} phút/ngày. Còn thiếu khoảng {missing} phút để đạt mục tiêu tuần.",
        ))

    days = inputs["days_to_exam"]
    if days is None:
        tips.append(_tip("profile", "Chưa có ngày thi dự kiến",
                         "Cập nhật ngày thi trong Hồ sơ để theo dõi thời gian còn lại."))
    elif days < 0:
        tips.append(_tip("profile", "Ngày thi dự kiến đã qua",
                         "Hãy cập nhật ngày thi mới trong Hồ sơ nếu bạn vẫn đang ôn luyện."))
    elif days <= 30:
        tips.append(_tip("schedule", f"Còn {days} ngày đến kỳ thi",
                         "Thời gian còn ngắn: ưu tiên các chủ đề yếu nhất và làm đề thử định kỳ."))
    else:
        tips.append(_tip("schedule", f"Còn {days} ngày đến kỳ thi",
                         f"Duy trì tối thiểu {daily} phút/ngày để đủ thời gian củng cố các chủ đề yếu."))

    if not tips:
        tips.append(_tip("keep", "Tiếp tục duy trì", "Chưa phát hiện điểm cần cải thiện gấp."))
    return tips


def _how_to_improve(row):
    mastery = row["mastery"]
    pct = f" (hiện {round(mastery * 100)}%)" if mastery is not None else ""
    topic = row["competency_name"] or "này"
    if row["resource_id"] is not None:
        minutes = row["estimated_min"] or 15
        return (f"Dành khoảng {minutes} phút học “{row['resource_title']}”, rồi làm lại vài câu "
                f"thuộc chủ đề {topic}{pct} để kiểm tra. Mục tiêu: đạt từ "
                f"{round(MASTERY_THRESHOLD * 100)}% trở lên.")
    return (f"Đọc lại lời giải câu hỏi này, sau đó làm thêm 2–3 câu cùng chủ đề {topic}{pct} "
            "ở độ khó bằng hoặc thấp hơn để chắc kiến thức nền.")


# ---------------------------------------------------------------------------
# Truy vấn CSDL
# ---------------------------------------------------------------------------

def _ensure_mastery_profile(cursor, student_id):
    """Dựng hồ sơ năng lực từ lịch sử bài làm nếu chưa có (không ghi đè dữ liệu có sẵn)."""
    cursor.execute(
        """
        IF OBJECT_ID(N'dbo.sp_SyncMasteryFromAnswers', N'P') IS NOT NULL
            EXEC dbo.sp_SyncMasteryFromAnswers @StudentID = ?
        """,
        (student_id,),
    )


def _load_inputs(cursor, student_id):
    rows = _fetch_all(
        cursor,
        """
        SELECT sp.TargetScore, sp.ExamDate, sp.DailyStudyMin,
               DATEDIFF(DAY, CAST(SYSDATETIME() AS DATE), sp.ExamDate) AS DaysToExam,
               (SELECT AVG(sc.Mastery) FROM dbo.StudentCompetency AS sc
                 WHERE sc.StudentID = sp.StudentID) AS AvgMastery,
               (SELECT COUNT(*) FROM dbo.StudentCompetency AS sc
                 WHERE sc.StudentID = sp.StudentID) AS CompetencyCount,
               (SELECT TOP 1 ea.Score FROM dbo.ExamAttempts AS ea
                 WHERE ea.StudentID = sp.StudentID AND ea.SubmittedAt IS NOT NULL
                   AND ea.Score IS NOT NULL
                 ORDER BY ea.SubmittedAt DESC, ea.AttemptID DESC) AS LatestScore,
               (SELECT COUNT(*) FROM dbo.ExamAttempts AS ea
                 WHERE ea.StudentID = sp.StudentID AND ea.SubmittedAt IS NOT NULL) AS SubmittedAttempts,
               (SELECT COUNT(*) FROM dbo.ExamAttempts AS ea
                 INNER JOIN dbo.AttemptAnswers AS aa
                    ON aa.AttemptID = ea.AttemptID AND aa.ExamID = ea.ExamID
                 WHERE ea.StudentID = sp.StudentID AND ea.SubmittedAt IS NOT NULL) AS AnsweredCount,
               (SELECT ISNULL(SUM(sl.DurationMin), 0) FROM dbo.StudyLogs AS sl
                 WHERE sl.StudentID = sp.StudentID
                   AND sl.LoggedAt >= DATEADD(DAY, -7, SYSDATETIME())) AS Minutes7d
        FROM dbo.StudentProfiles AS sp
        WHERE sp.StudentID = ?
        """,
        (student_id,),
    )
    if not rows:
        raise StudentProfileNotFound()
    row = rows[0]
    return {
        "target_score": row["TargetScore"],
        "exam_date": _iso(row["ExamDate"]),
        "days_to_exam": row["DaysToExam"],
        "daily_study_min": row["DailyStudyMin"],
        "avg_mastery": _num(row["AvgMastery"]),
        "competency_count": row["CompetencyCount"],
        "latest_score": _num(row["LatestScore"]),
        "submitted_attempts": row["SubmittedAttempts"],
        "answered_count": row["AnsweredCount"],
        "minutes_7d": row["Minutes7d"],
    }


def _weak_competencies(cursor, student_id, limit=3):
    rows = _fetch_all(
        cursor,
        f"""
        SELECT TOP ({int(limit)})
               c.CompetencyName, sc.Mastery, r.Title AS ResourceTitle, r.EstimatedMin
        FROM dbo.StudentCompetency AS sc
        INNER JOIN dbo.Competencies AS c ON c.CompetencyID = sc.CompetencyID
        OUTER APPLY (
            SELECT TOP 1 lr.Title, lr.EstimatedMin
            FROM dbo.LearningResources AS lr
            WHERE lr.CompetencyID = sc.CompetencyID
            ORDER BY lr.EstimatedMin ASC, lr.ResourceID ASC
        ) AS r
        WHERE sc.StudentID = ? AND sc.Mastery < ?
        ORDER BY sc.Mastery ASC, c.CompetencyID ASC
        """,
        (student_id, MASTERY_THRESHOLD),
    )
    return [
        {
            "name": row["CompetencyName"],
            "mastery": float(row["Mastery"]),
            "resource_title": row["ResourceTitle"],
            "resource_min": row["EstimatedMin"],
        }
        for row in rows
    ]


def _latest_prediction(cursor, student_id):
    rows = _fetch_all(
        cursor,
        """
        SELECT TOP 1 PredictionID, PredictedScore, ProbReachTarget, RiskNote, PredictedAt,
               DATEDIFF(SECOND, PredictedAt, SYSDATETIME()) AS AgeSeconds
        FROM dbo.ScorePredictions
        WHERE StudentID = ?
        ORDER BY PredictedAt DESC, PredictionID DESC
        """,
        (student_id,),
    )
    return rows[0] if rows else None


def _prediction_history(cursor, student_id, limit=8):
    rows = _fetch_all(
        cursor,
        f"""
        SELECT TOP ({int(limit)}) PredictedScore, ProbReachTarget, PredictedAt
        FROM dbo.ScorePredictions
        WHERE StudentID = ?
        ORDER BY PredictedAt DESC, PredictionID DESC
        """,
        (student_id,),
    )
    return [
        {
            "score": _num(row["PredictedScore"], 2),
            "probability": _num(row["ProbReachTarget"], 4),
            "predicted_at": _iso(row["PredictedAt"]),
        }
        for row in reversed(rows)
    ]


def _build_overview(cursor, student_id, inputs=None, reused=False):
    inputs = inputs or _load_inputs(cursor, student_id)
    current = compute_prediction(inputs)
    stored = _latest_prediction(cursor, student_id)
    weak = _weak_competencies(cursor, student_id)

    prediction = None
    if stored is not None:
        score = _num(stored["PredictedScore"], 2)
        probability = _num(stored["ProbReachTarget"], 4)
        target = inputs["target_score"] or 0
        target_set = target > 0
        prediction = {
            "id": stored["PredictionID"],
            "score": score,
            "target_score": target,
            "target_set": target_set,
            "gap": round(target - score, 2) if target_set else None,
            "probability": probability if target_set else None,
            "probability_percent": round(probability * 100) if target_set else None,
            "risk_level": risk_level(probability) if target_set else None,
            "risk_note": stored["RiskNote"],
            "predicted_at": _iso(stored["PredictedAt"]),
            "is_stale": abs(current["score"] - score) > STALE_TOLERANCE,
        }

    return {
        "prediction": prediction,
        "reused": reused,
        "factors": {
            "parts": current["parts"],
            "avg_mastery_percent": round(current["avg_mastery"] * 100),
            "mastery_defaulted": current["mastery_defaulted"],
            "exam_source": current["exam_source"],
            "latest_exam_score": inputs["latest_score"],
            "minutes_7d": current["minutes_7d"],
            "weekly_goal_min": current["weekly_goal_min"],
            "study_ratio_percent": round(current["study_ratio"] * 100),
            "weights": {"mastery": W_MASTERY, "exam": W_EXAM, "study": W_STUDY},
        },
        "profile": {
            "target_score": inputs["target_score"],
            "exam_date": inputs["exam_date"],
            "days_to_exam": inputs["days_to_exam"],
            "daily_study_min": inputs["daily_study_min"],
        },
        "improvements": build_improvements(inputs, current, weak),
        "data_quality": data_quality(inputs),
        "history": _prediction_history(cursor, student_id),
        "method": PREDICTION_METHOD,
    }


def get_prediction_overview(student_id):
    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            return _build_overview(cursor, student_id)


def refresh_prediction(student_id):
    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            _ensure_mastery_profile(cursor, student_id)
            inputs = _load_inputs(cursor, student_id)
            current = compute_prediction(inputs)
            latest = _latest_prediction(cursor, student_id)

            reuse = (
                latest is not None
                and (latest["AgeSeconds"] or 0) < PREDICTION_REUSE_SECONDS
                and abs(current["score"] - float(latest["PredictedScore"])) <= STALE_TOLERANCE
            )
            if not reuse:
                cursor.execute(
                    "EXEC dbo.sp_CalculateScorePrediction @StudentID = ?", (student_id,)
                )
            connection.commit()
            return _build_overview(cursor, student_id, inputs=inputs, reused=reuse)


def _recommendation_rows(cursor, student_id, limit=50):
    rows = _fetch_all(
        cursor,
        f"""
        SELECT TOP ({int(limit)})
               rec.RecID, rec.ResourceID, rec.QuestionID, rec.Reason, rec.CreatedAt,
               rec.IsAccepted,
               r.Title AS ResourceTitle, r.ResourceType, r.Url, r.EstimatedMin,
               q.Content AS QuestionContent, q.Difficulty,
               c.CompetencyName, s.SubjectName, sc.Mastery
        FROM dbo.Recommendations AS rec
        LEFT JOIN dbo.LearningResources AS r ON r.ResourceID = rec.ResourceID
        LEFT JOIN dbo.Questions AS q ON q.QuestionID = rec.QuestionID
        LEFT JOIN dbo.Competencies AS c ON c.CompetencyID = COALESCE(q.CompetencyID, r.CompetencyID)
        LEFT JOIN dbo.Subjects AS s ON s.SubjectID = c.SubjectID
        LEFT JOIN dbo.StudentCompetency AS sc
            ON sc.StudentID = rec.StudentID AND sc.CompetencyID = c.CompetencyID
        WHERE rec.StudentID = ?
        ORDER BY CASE WHEN rec.IsAccepted = 1 THEN 1 ELSE 0 END,
                 rec.CreatedAt DESC, rec.RecID DESC
        """,
        (student_id,),
    )
    items = []
    for row in rows:
        accepted = row["IsAccepted"]
        item = {
            "id": row["RecID"],
            "type": "resource" if row["ResourceID"] is not None else "question",
            "resource_id": row["ResourceID"],
            "resource_title": row["ResourceTitle"],
            "resource_type": row["ResourceType"],
            "resource_url": _safe_url(row["Url"]),
            "estimated_min": row["EstimatedMin"],
            "question_id": row["QuestionID"],
            "question_content": row["QuestionContent"],
            "difficulty": row["Difficulty"],
            "competency_name": row["CompetencyName"],
            "subject_name": row["SubjectName"],
            "mastery": _num(row["Mastery"], 4),
            "mastery_percent": round(float(row["Mastery"]) * 100) if row["Mastery"] is not None else None,
            "reason": row["Reason"],
            "created_at": _iso(row["CreatedAt"]),
            "status": "accepted" if accepted else ("dismissed" if accepted is not None else "pending"),
        }
        item["priority"] = _priority(item["mastery"])
        item["how_to_improve"] = _how_to_improve(item)
        items.append(item)
    return items


def list_recommendations(student_id):
    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            return {
                "recommendations": _recommendation_rows(cursor, student_id),
                "method": RECOMMENDATION_METHOD,
            }


def generate_recommendations(student_id):
    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.StudentProfiles WHERE StudentID = ?", (student_id,)
            )
            if cursor.fetchone()[0] == 0:
                raise StudentProfileNotFound()

            _ensure_mastery_profile(cursor, student_id)
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.Recommendations WHERE StudentID = ?", (student_id,)
            )
            before = cursor.fetchone()[0]
            cursor.execute("EXEC dbo.sp_GenerateRecommendations @StudentID = ?", (student_id,))
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.Recommendations WHERE StudentID = ?", (student_id,)
            )
            after = cursor.fetchone()[0]
            connection.commit()
            return {
                "created": max(0, after - before),
                "recommendations": _recommendation_rows(cursor, student_id),
                "method": RECOMMENDATION_METHOD,
            }


def respond_to_recommendation(student_id, rec_id, accepted):
    with _connect() as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT 1 FROM dbo.Recommendations WHERE RecID = ? AND StudentID = ?",
                (rec_id, student_id),
            )
            if cursor.fetchone() is None:
                raise RecommendationNotFound()
            cursor.execute(
                "UPDATE dbo.Recommendations SET IsAccepted = ? WHERE RecID = ? AND StudentID = ?",
                (1 if accepted else 0, rec_id, student_id),
            )
            connection.commit()
            return {"id": rec_id, "status": "accepted" if accepted else "dismissed"}

import { useEffect, useRef, useState } from "react";

const ACTIVE_ATTEMPT_KEY = "novapath-active-exam-attempt";

function formatTime(seconds) {
  const safeSeconds = Math.max(0, seconds || 0);
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remaining = safeSeconds % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
}

function answersForAttempt(questions) {
  return Object.fromEntries(
    questions
      .filter((question) => question.selected_option_id != null)
      .map((question) => [question.id, question.selected_option_id]),
  );
}

export default function ExamPage({ api }) {
  const [exams, setExams] = useState([]);
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [remainingSeconds, setRemainingSeconds] = useState(null);
  const [deadline, setDeadline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pendingSaves, setPendingSaves] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const submitting = useRef(false);
  const timeoutHandled = useRef(null);

  useEffect(() => {
    let active = true;
    async function initialize() {
      setLoading(true);
      setError("");
      try {
        const result = await api.exams();
        if (!active) return;
        setExams(result.exams);

        const storedAttemptId = window.sessionStorage.getItem(ACTIVE_ATTEMPT_KEY);
        if (!storedAttemptId) return;
        try {
          const response = await api.getExamAttempt(Number(storedAttemptId));
          if (!active) return;
          if (response.attempt.submitted_at) {
            window.sessionStorage.removeItem(ACTIVE_ATTEMPT_KEY);
            return;
          }
          setAttempt(response.attempt);
          setAnswers(answersForAttempt(response.attempt.questions));
          setRemainingSeconds(response.attempt.remaining_seconds);
          setDeadline(Date.now() + response.attempt.remaining_seconds * 1000);
        } catch (requestError) {
          if (requestError.status !== 404) throw requestError;
          window.sessionStorage.removeItem(ACTIVE_ATTEMPT_KEY);
        }
      } catch (requestError) {
        if (active) setError(requestError.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    initialize();
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    if (!attempt || attempt.submitted_at || deadline === null) return undefined;
    function updateCountdown() {
      setRemainingSeconds(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
    }
    updateCountdown();
    const timer = window.setInterval(updateCountdown, 250);
    return () => window.clearInterval(timer);
  }, [attempt?.id, attempt?.submitted_at, deadline]);

  async function loadExams() {
    setError("");
    setLoading(true);
    try {
      const result = await api.exams();
      setExams(result.exams);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function startExam(examId) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.startExam(examId);
      setAttempt({ ...result.attempt, questions: result.questions });
      setAnswers({});
      setRemainingSeconds(result.attempt.remaining_seconds);
      setDeadline(Date.now() + result.attempt.remaining_seconds * 1000);
      timeoutHandled.current = null;
      window.sessionStorage.setItem(ACTIVE_ATTEMPT_KEY, String(result.attempt.id));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function chooseAnswer(questionId, optionId) {
    setAnswers((current) => ({ ...current, [questionId]: optionId }));
    setPendingSaves((current) => current + 1);
    try {
      await api.saveExamAnswers(attempt.id, [{ question_id: questionId, option_id: optionId }]);
    } catch (requestError) {
      if (requestError.status === 409) {
        setRemainingSeconds(0);
      } else {
        setError(requestError.message);
      }
    } finally {
      setPendingSaves((current) => Math.max(0, current - 1));
    }
  }

  async function submitExam() {
    if (submitting.current || !attempt || attempt.submitted_at) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api.submitExam(
        attempt.id,
        Object.entries(answers).map(([question_id, option_id]) => ({
          question_id: Number(question_id),
          option_id,
        })),
      );
      setAttempt(result.attempt);
      setRemainingSeconds(null);
      setDeadline(null);
      window.sessionStorage.removeItem(ACTIVE_ATTEMPT_KEY);
      if (result.attempt.timed_out) {
        setNotice("Đã hết giờ. Bài làm được tự động nộp với các đáp án đã lưu.");
      }
    } catch (requestError) {
      setError(requestError.message);
      timeoutHandled.current = null;
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  useEffect(() => {
    if (
      !attempt
      || attempt.submitted_at
      || remainingSeconds !== 0
      || timeoutHandled.current === attempt.id
    ) return;
    timeoutHandled.current = attempt.id;
    setNotice("Hết giờ, hệ thống đang tự động nộp bài...");
    submitExam();
  }, [attempt, remainingSeconds]);

  if (loading) {
    return <div className="alert warning">Đang tải danh sách đề thi...</div>;
  }

  if (attempt) {
    const submitted = Boolean(attempt.submitted_at);
    return (
      <section className="exam-page">
        <div className="panel exam-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{submitted ? "KẾT QUẢ BÀI LÀM" : "ĐANG LÀM BÀI"}</p>
              <h1>{attempt.exam_title || "Bài thi"}</h1>
              <p className="welcome-copy">
                {submitted
                  ? `Kết quả: ${attempt.correct_count}/${attempt.question_count} câu đúng · ${Number(attempt.score).toFixed(2)} điểm`
                  : `Thời lượng: ${attempt.duration_min} phút · Đáp án được lưu ngay khi chọn.`}
              </p>
            </div>
            {!submitted && (
              <div
                className={`exam-timer ${remainingSeconds <= 60 ? "urgent" : ""}`}
                role="timer"
                aria-live="off"
              >
                <span>THỜI GIAN CÒN LẠI</span>
                <strong>{formatTime(remainingSeconds)}</strong>
              </div>
            )}
          </div>
          {notice && <div className="alert warning" role="status">{notice}</div>}
          {error && <div className="alert error" role="alert">{error}</div>}
          <div className="exam-question-list">
            {attempt.questions.map((question, index) => (
              <article className="exam-question" key={question.id}>
                <div className="exam-question-title">
                  <strong>Câu {index + 1}</strong>
                  <span>Độ khó {question.difficulty}/5</span>
                  {submitted && (
                    <span className={question.is_correct ? "answer-correct" : "answer-wrong"}>
                      {question.is_correct ? "Đúng" : "Chưa đúng"}
                    </span>
                  )}
                </div>
                <p>{question.content}</p>
                <div className="exam-options">
                  {question.options.map((option) => (
                    <label
                      className={`exam-option ${submitted && option.is_correct ? "correct-option" : ""}`}
                      key={option.id}
                    >
                      <input
                        type="radio"
                        name={`question-${question.id}`}
                        checked={question.selected_option_id === option.id || answers[question.id] === option.id}
                        disabled={submitted || busy || remainingSeconds === 0}
                        onChange={() => chooseAnswer(question.id, option.id)}
                      />
                      <span><strong>{option.label}.</strong> {option.text}</span>
                    </label>
                  ))}
                </div>
                {submitted && question.explanation && (
                  <p className="exam-explanation"><strong>Giải thích:</strong> {question.explanation}</p>
                )}
              </article>
            ))}
          </div>
          <div className="exam-actions">
            {!submitted && (
              <button
                className="primary-button"
                disabled={busy || pendingSaves > 0}
                onClick={submitExam}
              >
                {busy ? "Đang nộp..." : pendingSaves ? "Đang lưu đáp án..." : "Nộp bài"}
              </button>
            )}
            <button className="refresh-button" disabled={busy} onClick={() => setAttempt(null)}>
              {submitted ? "Quay lại danh sách đề" : "Thoát bài thi"}
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="exam-page">
      <div className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">LUYỆN TẬP & ĐÁNH GIÁ</p><h1>Đề thi</h1></div>
          <button className="refresh-button" onClick={loadExams}>Làm mới</button>
        </div>
        {error && <div className="alert error" role="alert">{error}</div>}
        {exams.length ? (
          <div className="exam-list">
            {exams.map((exam) => (
              <article className="exam-card" key={exam.id}>
                <div>
                  <span className="exam-type">{exam.exam_type === "DIAGNOSTIC" ? "Chẩn đoán" : exam.exam_type === "MOCK" ? "Thi thử" : "Luyện tập"}</span>
                  <h2>{exam.title}</h2>
                  <p>{exam.question_count} câu · {exam.duration_min} phút</p>
                </div>
                <button className="primary-button" disabled={busy} onClick={() => startExam(exam.id)}>
                  {busy ? "Đang mở..." : "Bắt đầu"}
                </button>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <span>✎</span><strong>Chưa có đề thi sẵn sàng</strong>
            <p>Đề thi đã được giáo viên duyệt sẽ xuất hiện tại đây.</p>
          </div>
        )}
      </div>
    </section>
  );
}

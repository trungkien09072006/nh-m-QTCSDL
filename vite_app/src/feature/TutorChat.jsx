import { useEffect, useRef, useState } from "react";
import { tutorApi } from "./tutorApi.js";
import "./tutor.css";

// Hàm render văn bản đơn giản hỗ trợ Markdown cơ bản (in đậm, danh sách, trích dẫn)
function SimpleMarkdown({ content }) {
  if (!content) return null;

  const lines = content.split("\n");
  const elements = [];
  let inList = false;
  let listItems = [];

  function flushList() {
    if (inList && listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`}>
          {listItems.map((item, idx) => (
            <li key={idx} dangerouslySetInnerHTML={{ __html: parseInline(item) }} />
          ))}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  }

  function parseInline(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      inList = true;
      listItems.push(trimmed.substring(2));
      return;
    }

    flushList();

    if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote
          key={`quote-${index}`}
          dangerouslySetInnerHTML={{ __html: parseInline(trimmed.substring(2)) }}
        />
      );
    } else if (trimmed.startsWith("### ")) {
      elements.push(
        <h3
          key={`h3-${index}`}
          dangerouslySetInnerHTML={{ __html: parseInline(trimmed.substring(4)) }}
        />
      );
    } else if (trimmed.startsWith("#### ")) {
      elements.push(
        <h4
          key={`h4-${index}`}
          dangerouslySetInnerHTML={{ __html: parseInline(trimmed.substring(5)) }}
        />
      );
    } else if (trimmed === "---") {
      elements.push(<hr key={`hr-${index}`} style={{ border: 0, borderTop: "1px solid #e9edf4", margin: "10px 0" }} />);
    } else if (trimmed.length > 0) {
      elements.push(
        <p
          key={`p-${index}`}
          dangerouslySetInnerHTML={{ __html: parseInline(trimmed) }}
        />
      );
    }
  });

  flushList();
  return <div className="tutor-rendered-content">{elements}</div>;
}

export function TutorChat({ studentName = "Học sinh" }) {
  const [questions, setQuestions] = useState([]);
  const [selectedQuestion, setSelectedQuestion] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(true);
  const [aiStatus, setAiStatus] = useState(null);
  const [errorNotice, setErrorNotice] = useState("");

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Tải trạng thái, ngân hàng câu hỏi và lịch sử tin nhắn ban đầu
  useEffect(() => {
    async function initData() {
      setFetchingHistory(true);
      try {
        const [statusData, qData, historyData] = await Promise.all([
          tutorApi.getStatus().catch(() => null),
          tutorApi.getQuestions().catch(() => ({ questions: [] })),
          tutorApi.getHistory().catch(() => ({ messages: [] })),
        ]);

        if (statusData) setAiStatus(statusData);
        if (qData?.questions) setQuestions(qData.questions);
        if (historyData?.messages) setMessages(historyData.messages);
      } catch (err) {
        setErrorNotice("Không thể tải thông tin AI Tutor: " + (err.message || "Lỗi mạng"));
      } finally {
        setFetchingHistory(false);
      }
    }
    initData();
  }, []);

  async function handleSend(customText = null) {
    const textToSend = (customText !== null ? customText : inputMessage).trim();
    if (!textToSend && !selectedQuestion) return;

    const payload = {
      message: textToSend,
      question_id: selectedQuestion ? selectedQuestion.id : null,
    };

    // Thêm tin nhắn tạm vào giao diện
    const tempUserMsg = {
      id: Date.now(),
      sender: "USER",
      content: textToSend || `Yêu cầu AI Tutor hướng dẫn giải câu hỏi #${selectedQuestion.id}`,
      question_id: selectedQuestion?.id,
      question_content: selectedQuestion?.content,
      competency_name: selectedQuestion?.competency,
      sent_at: "Vừa xong",
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setInputMessage("");
    setLoading(true);
    setErrorNotice("");

    try {
      const res = await tutorApi.ask(payload);
      if (res && res.reply) {
        const aiMsg = {
          id: Date.now() + 1,
          sender: "AI",
          content: res.reply,
          question_id: res.question_id,
          sent_at: res.sent_at || "Vừa xong",
          model_used: res.model_used,
        };
        setMessages((prev) => [...prev, aiMsg]);
      }
    } catch (err) {
      setErrorNotice("Không thể gửi tin nhắn: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResetSession() {
    if (!window.confirm("Bạn có chắc chắn muốn khởi tạo cuộc trò chuyện mới với AI Tutor không?")) {
      return;
    }
    try {
      setLoading(true);
      await tutorApi.clearSession();
      setMessages([]);
      setSelectedQuestion(null);
      setErrorNotice("");
    } catch (err) {
      setErrorNotice("Không thể làm mới phiên: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSelectQuestion(q) {
    if (selectedQuestion?.id === q.id) {
      setSelectedQuestion(null);
    } else {
      setSelectedQuestion(q);
    }
  }

  return (
    <div className="tutor-container">
      {/* Cột 1: Danh sách câu hỏi cần giải thích */}
      <aside className="tutor-sidebar-questions">
        <div className="tutor-sidebar-header">
          <p className="eyebrow" style={{ margin: "0 0 2px" }}>NGÂN HÀNG BÀI TẬP</p>
          <h3>Chọn câu hỏi cần giải thích</h3>
          <p>Bấm chọn một câu để AI Tutor giải thích phương pháp giải & tránh bẫy</p>
        </div>

        <div className="tutor-question-list">
          {questions.length === 0 ? (
            <p style={{ fontSize: "12px", color: "#8a96a9", padding: "10px" }}>
              Chưa có danh sách câu hỏi.
            </p>
          ) : (
            questions.map((q) => {
              const isSelected = selectedQuestion?.id === q.id;
              return (
                <div
                  key={q.id}
                  className={`tutor-q-card ${isSelected ? "selected" : ""}`}
                  onClick={() => handleSelectQuestion(q)}
                >
                  <div className="tutor-q-meta">
                    <span className="tutor-comp-badge">{q.competency || "Tổng hợp"}</span>
                    <span className="tutor-diff-badge">Độ khó: {q.difficulty}/5 ★</span>
                  </div>
                  <div className="tutor-q-text">
                    <strong>#{q.id}.</strong> {q.content}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* Cột 2: Khung trò chuyện AI Tutor */}
      <section className="tutor-chat-main">
        {/* Header khung chat */}
        <div className="tutor-chat-header">
          <div className="tutor-header-title">
            <span className="tutor-bot-icon">✦</span>
            <div>
              <h2 style={{ fontSize: "16px", margin: 0 }}>AI Tutor NovaPath</h2>
              <small style={{ color: "#8793a6", fontSize: "11px" }}>
                Đồng hành phân tích tư duy & phương pháp làm bài ĐGNL
              </small>
            </div>
          </div>

          <div className="tutor-header-actions">
            {aiStatus && (
              <span
                className={`tutor-mode-tag ${
                  aiStatus.mode === "EXTERNAL_AI" ? "gemini" : "local"
                }`}
                title={aiStatus.instructions}
              >
                {aiStatus.mode === "EXTERNAL_AI" ? "✨ Gemini AI" : "📚 Tri thức NovaPath (RAG)"}
              </span>
            )}

            <button
              className="tutor-reset-btn"
              onClick={handleResetSession}
              disabled={loading}
              title="Khởi tạo cuộc hội thoại mới"
            >
              ↺ Làm mới hội thoại
            </button>
          </div>
        </div>

        {errorNotice && (
          <div
            style={{
              padding: "8px 16px",
              background: "#ffefef",
              color: "#c5221f",
              fontSize: "12px",
              borderBottom: "1px solid #ffd3d3",
            }}
          >
            {errorNotice}
          </div>
        )}

        {/* Khung cuộn tin nhắn */}
        <div className="tutor-messages-wrap">
          {fetchingHistory ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "#8a96a9" }}>
              Đang tải lịch sử trò chuyện...
            </div>
          ) : messages.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 20px", color: "#8a96a9" }}>
              <span style={{ fontSize: "32px", display: "block", marginBottom: "10px" }}>💡</span>
              <strong style={{ color: "#252e40", fontSize: "14px" }}>
                Chào bạn, mình là AI Tutor NovaPath!
              </strong>
              <p style={{ fontSize: "12px", maxWidth: "420px", margin: "8px auto 0", lineHeight: 1.5 }}>
                Hãy chọn một câu hỏi bên danh sách hoặc đặt câu hỏi trực tiếp để nhận hướng dẫn giải thích
                chi tiết từng bước và mẹo tránh bẫy câu hỏi.
              </p>
            </div>
          ) : (
            messages.map((m) => {
              const isUser = m.sender === "USER";
              return (
                <div key={m.id} className={`tutor-msg-item ${isUser ? "user" : "ai"}`}>
                  <div className="tutor-msg-avatar">
                    {isUser ? studentName?.slice(0, 1) || "U" : "✦"}
                  </div>
                  <div className="tutor-bubble">
                    {m.question_id && (
                      <div className="tutor-bubble-question-ref">
                        📌 Hỏi về câu hỏi #{m.question_id}
                        {m.competency_name ? ` (${m.competency_name})` : ""}
                      </div>
                    )}
                    <SimpleMarkdown content={m.content} />
                    <span className="tutor-msg-time">{m.sent_at}</span>
                  </div>
                </div>
              );
            })
          )}

          {loading && (
            <div className="tutor-msg-item ai">
              <div className="tutor-msg-avatar">✦</div>
              <div className="tutor-bubble">
                <span className="tutor-typing-indicator">
                  <span>AI Tutor đang suy nghĩ và phân tích dữ liệu...</span>
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick prompt chips khi học sinh chọn câu hỏi */}
        <div className="tutor-quick-prompts">
          {selectedQuestion ? (
            <>
              <button
                className="tutor-chip"
                onClick={() =>
                  handleSend(`Hãy giải thích chi tiết phương pháp làm bài cho câu hỏi #${selectedQuestion.id}`)
                }
                disabled={loading}
              >
                💡 Giải thích chi tiết câu #{selectedQuestion.id}
              </button>
              <button
                className="tutor-chip"
                onClick={() =>
                  handleSend(`Chỉ ra công thức và các bẫy thường gặp ở câu #${selectedQuestion.id}`)
                }
                disabled={loading}
              >
                ⚠️ Bẫy thường gặp & Công thức
              </button>
              <button
                className="tutor-chip"
                onClick={() =>
                  handleSend(`Cho em một câu hỏi tương tự câu #${selectedQuestion.id} để tự luyện tập`)
                }
                disabled={loading}
              >
                🎯 Câu hỏi tương tự để luyện
              </button>
            </>
          ) : (
            <>
              <button
                className="tutor-chip"
                onClick={() =>
                  handleSend("Dựa trên hồ sơ học tập của em, em nên ưu tiên củng cố dạng bài nào trước?")
                }
                disabled={loading}
              >
                📊 Phân tích năng lực còn yếu của em
              </button>
              <button
                className="tutor-chip"
                onClick={() =>
                  handleSend("Hãy chia sẻ cho em chiến thuật phân bổ thời gian khi làm đề thi ĐGNL")
                }
                disabled={loading}
              >
                ⏱ Chiến thuật phân bổ thời gian thi
              </button>
            </>
          )}
        </div>

        {/* Khung gửi câu hỏi */}
        <form
          className="tutor-input-bar"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <input
            className="tutor-input"
            placeholder={
              selectedQuestion
                ? `Hỏi AI Tutor về câu #${selectedQuestion.id} (hoặc bấm gửi để yêu cầu giải thích)...`
                : "Hỏi AI Tutor về bài học, công thức, cách giải..."
            }
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            className="tutor-send-btn"
            disabled={loading || (!inputMessage.trim() && !selectedQuestion)}
          >
            Gửi ➔
          </button>
        </form>
      </section>
    </div>
  );
}

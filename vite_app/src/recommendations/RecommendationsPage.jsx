import { useCallback, useEffect, useState } from "react";
import { recommendationsApi as defaultApi } from "./recommendationsApi.js";
import "./recommendations.css";

const RESOURCE_TYPES = { VIDEO: "Video", ARTICLE: "Bài đọc", SLIDE: "Slide", EXERCISE: "Bài tập" };
const STATUS_LABELS = { pending: "Chưa phản hồi", accepted: "Đã chấp nhận", dismissed: "Chưa chấp nhận" };
const RISK_CLASS = { "An toàn": "safe", "Cần theo dõi": "watch", "Nguy cơ cao": "risk" };
const QUALITY_LABELS = { low: "Thấp", medium: "Trung bình", good: "Khá" };
const FACTOR_ROWS = [
  { key: "mastery", label: "Mức thành thạo trung bình", weightKey: "mastery" },
  { key: "exam", label: "Điểm bài thi gần nhất", weightKey: "exam" },
  { key: "study", label: "Thời lượng học 7 ngày", weightKey: "study" },
];

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function MethodNote({ method }) {
  if (!method) return null;
  return (
    <div className="rec-method" role="note">
      <span className="rec-method-badge">{method.label}</span>
      <p>{method.description}</p>
    </div>
  );
}

function Sparkline({ history }) {
  if (!history || history.length < 2) return null;
  const scores = history.map((item) => item.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const span = max - min || 1;
  const points = scores
    .map((score, index) => {
      const x = (index / (scores.length - 1)) * 200 + 4;
      const y = 36 - ((score - min) / span) * 30;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <figure className="rec-spark">
      <svg viewBox="0 0 208 42" role="img" aria-label={`Điểm dự đoán qua ${scores.length} lần cập nhật gần nhất`}>
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <figcaption>
        {scores.length} lần cập nhật gần nhất: {Math.round(scores[0])} → {Math.round(scores[scores.length - 1])}
      </figcaption>
    </figure>
  );
}

function PredictionPanel({ overview, busy, onRefresh }) {
  const prediction = overview.prediction;
  const factors = overview.factors;
  const quality = overview.data_quality;
  const maxPoints = 1200;

  return (
    <section className="panel rec-panel" aria-labelledby="prediction-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">DỰ ĐOÁN ĐIỂM ĐGNL</p>
          <h2 id="prediction-title">Khả năng đạt mục tiêu</h2>
        </div>
        <button className="rec-button" onClick={onRefresh} disabled={busy}>
          {busy ? "Đang tính..." : "Cập nhật dự đoán"}
        </button>
      </div>

      <MethodNote method={overview.method} />

      {!prediction ? (
        <div className="empty-state">
          <span>◎</span>
          <strong>Chưa có dự đoán</strong>
          <p>Nhấn “Cập nhật dự đoán” để tính điểm dự kiến từ dữ liệu học tập hiện có.</p>
        </div>
      ) : (
        <>
          {prediction.is_stale && (
            <div className="alert warning" role="status">
              Dữ liệu học tập đã thay đổi kể từ lần dự đoán cuối. Hãy cập nhật dự đoán để có kết quả mới.
            </div>
          )}
          <div className="rec-score-row">
            <div className="rec-score">
              <small>ĐIỂM DỰ KIẾN</small>
              <strong>{Math.round(prediction.score)}<span> / 1200</span></strong>
              <em>
                {prediction.target_set
                  ? `Mục tiêu ${prediction.target_score} điểm${prediction.gap > 0 ? ` · còn thiếu ${Math.round(prediction.gap)}` : " · đã đạt theo dự đoán"}`
                  : "Chưa đặt điểm mục tiêu"}
              </em>
            </div>
            <div className="rec-prob">
              <small>KHẢ NĂNG ĐẠT MỤC TIÊU (ƯỚC LƯỢNG)</small>
              {prediction.target_set ? (
                <>
                  <strong>{prediction.probability_percent}%</strong>
                  <span className={`rec-risk ${RISK_CLASS[prediction.risk_level] || ""}`}>{prediction.risk_level}</span>
                  <div className="progress-track"><span style={{ width: `${prediction.probability_percent}%` }} /></div>
                </>
              ) : (
                <strong>—</strong>
              )}
            </div>
            <Sparkline history={overview.history} />
          </div>
          {prediction.risk_note && <p className="rec-risk-note">{prediction.risk_note}</p>}
          <p className="rec-meta">Cập nhật lúc {formatDateTime(prediction.predicted_at)}{overview.reused ? " (dữ liệu chưa đổi nên giữ kết quả gần nhất)" : ""}</p>
        </>
      )}

      <div className="rec-quality">
        <span className={`rec-quality-dot ${quality.level}`} aria-hidden="true" />
        <p>
          <strong>Độ đầy đủ dữ liệu: {QUALITY_LABELS[quality.level]}.</strong>{" "}
          {quality.answered_count} câu trả lời từ {quality.submitted_attempts} bài đã nộp, {quality.competency_count} năng lực có dữ liệu. {quality.note}
        </p>
      </div>

      <h3 className="rec-subtitle">Điểm dự kiến được tính từ đâu?</h3>
      <div className="rec-factors">
        {FACTOR_ROWS.map((row) => {
          const points = factors.parts[row.key];
          return (
            <div className="rec-factor" key={row.key}>
              <div>
                <span>{row.label} <small>(trọng số {Math.round(factors.weights[row.weightKey] * 100)}%)</small></span>
                <strong>{Math.round(points)} điểm</strong>
              </div>
              <div className="progress-track"><span style={{ width: `${Math.min(100, (points / (maxPoints * factors.weights[row.weightKey])) * 100)}%` }} /></div>
            </div>
          );
        })}
      </div>
      <ul className="rec-factor-notes">
        <li>
          Mức thành thạo trung bình: {factors.avg_mastery_percent}%
          {factors.mastery_defaulted ? " (chưa có dữ liệu nên dùng mặc định 50%)" : ""}.
        </li>
        <li>
          {factors.exam_source === "exam"
            ? `Điểm bài thi gần nhất: ${factors.latest_exam_score}.`
            : "Chưa có bài thi đã nộp nên phần này lấy theo mức thành thạo."}
        </li>
        <li>Đã học {factors.minutes_7d}/{factors.weekly_goal_min} phút trong 7 ngày ({factors.study_ratio_percent}%).</li>
      </ul>
    </section>
  );
}

function ImprovementPanel({ items }) {
  return (
    <section className="panel rec-panel" aria-labelledby="improve-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">CÁCH CẢI THIỆN</p>
          <h2 id="improve-title">Nên làm gì tiếp theo?</h2>
        </div>
      </div>
      <ol className="rec-tips">
        {items.map((tip, index) => (
          <li className={`rec-tip ${tip.kind}`} key={`${tip.kind}-${index}`}>
            <strong>{tip.title}</strong>
            <p>{tip.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function RecommendationCard({ item, busy, onRespond }) {
  const isResource = item.type === "resource";
  return (
    <article className={`rec-card ${item.status}`}>
      <div className="rec-card-head">
        <span className="rec-type">{isResource ? "Học liệu" : "Ôn câu hỏi"}</span>
        {item.priority && <span className={`rec-priority ${item.priority === "Ưu tiên cao" ? "high" : ""}`}>{item.priority}</span>}
        <span className="rec-status">{STATUS_LABELS[item.status]}</span>
      </div>
      <h3>
        {isResource
          ? item.resource_title
          : item.question_content || "Câu hỏi đã làm sai"}
      </h3>
      <p className="rec-topic">
        {[item.subject_name, item.competency_name].filter(Boolean).join(" · ")}
        {item.mastery_percent != null && ` · thành thạo ${item.mastery_percent}%`}
        {isResource && ` · ${RESOURCE_TYPES[item.resource_type] || item.resource_type}, khoảng ${item.estimated_min} phút`}
        {!isResource && item.difficulty != null && ` · độ khó ${item.difficulty}/5`}
      </p>
      <div className="rec-why"><strong>Vì sao được gợi ý</strong><p>{item.reason}</p></div>
      <div className="rec-how"><strong>Cách cải thiện</strong><p>{item.how_to_improve}</p></div>
      <div className="rec-actions">
        {item.resource_url && (
          <a className="rec-link" href={item.resource_url} target="_blank" rel="noopener noreferrer">Mở học liệu ↗</a>
        )}
        {item.status !== "accepted" && (
          <button className="rec-button" disabled={busy} onClick={() => onRespond(item.id, true)}>Chấp nhận</button>
        )}
        {item.status === "pending" && (
          <button className="rec-button ghost" disabled={busy} onClick={() => onRespond(item.id, false)}>Bỏ qua</button>
        )}
      </div>
    </article>
  );
}

export default function RecommendationsPage({ api = defaultApi }) {
  const [overview, setOverview] = useState(null);
  const [recs, setRecs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const fail = useCallback((requestError) => {
    setError(requestError.status === 401 ? "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại." : requestError.message);
  }, []);

  const load = useCallback(async () => {
    setError("");
    try {
      const [prediction, list] = await Promise.all([api.latestPrediction(), api.list()]);
      setOverview(prediction);
      setRecs(list);
    } catch (requestError) {
      fail(requestError);
    } finally {
      setLoading(false);
    }
  }, [api, fail]);

  useEffect(() => { load(); }, [load]);

  async function run(name, action) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (requestError) {
      fail(requestError);
    } finally {
      setBusy("");
    }
  }

  const refreshPrediction = () => run("prediction", async () => {
    setOverview(await api.refreshPrediction());
  });

  const generate = () => run("generate", async () => {
    const result = await api.generate();
    setRecs(result);
    setNotice(
      result.created > 0
        ? `Đã tạo ${result.created} gợi ý mới.`
        : "Chưa có gợi ý mới: các chủ đề hiện đã có gợi ý đang chờ hoặc chưa có chủ đề cần ôn.",
    );
  });

  const respond = (id, accepted) => run("respond", async () => {
    const result = await api.respond(id, accepted);
    setRecs((current) => ({
      ...current,
      recommendations: current.recommendations.map((item) => (item.id === id ? { ...item, status: result.status } : item)),
    }));
  });

  if (loading) {
    return <div className="alert warning" role="status">Đang tải gợi ý và dự đoán...</div>;
  }

  return (
    <div className="rec-page">
      <section className="rec-header">
        <p className="eyebrow">AI HỖ TRỢ HỌC TẬP</p>
        <h1>Gợi ý học & dự đoán điểm</h1>
        <p className="welcome-copy">Xem điểm dự kiến, lý do được gợi ý và các bước nên làm để tiến gần mục tiêu.</p>
      </section>

      {error && <div className="alert error" role="alert">{error}</div>}
      {notice && <div className="alert success" role="status">{notice}</div>}

      {overview && <PredictionPanel overview={overview} busy={busy === "prediction"} onRefresh={refreshPrediction} />}
      {overview && <ImprovementPanel items={overview.improvements} />}

      <section className="panel rec-panel" aria-labelledby="recs-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">GỢI Ý CÁ NHÂN HÓA</p>
            <h2 id="recs-title">Học liệu và câu hỏi nên ôn</h2>
          </div>
          <button className="rec-button" onClick={generate} disabled={busy === "generate"}>
            {busy === "generate" ? "Đang tạo..." : "Tạo gợi ý mới"}
          </button>
        </div>
        <MethodNote method={recs?.method} />
        {recs?.recommendations?.length ? (
          <div className="rec-list">
            {recs.recommendations.map((item) => (
              <RecommendationCard key={item.id} item={item} busy={busy === "respond"} onRespond={respond} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <span>✧</span>
            <strong>Chưa có gợi ý</strong>
            <p>Nhấn “Tạo gợi ý mới” để hệ thống tìm chủ đề cần ôn từ kết quả làm bài của bạn.</p>
          </div>
        )}
      </section>
    </div>
  );
}

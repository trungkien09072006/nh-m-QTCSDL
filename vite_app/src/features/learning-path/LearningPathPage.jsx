import { useCallback, useEffect, useState } from "react";
import { learningPathApi as defaultApi } from "./learningPathApi.js";
import "./learningPath.css";

const STATUS_LABELS = {
  TODO: "Chưa học",
  DOING: "Đang học",
  DONE: "Hoàn thành",
  SKIPPED: "Bỏ qua",
};

const RESOURCE_TYPES = {
  VIDEO: "Video",
  ARTICLE: "Bài đọc",
  SLIDE: "Slide",
  EXERCISE: "Bài tập",
};

const FILTERS = [
  { key: "ALL", label: "Tất cả" },
  { key: "TODO", label: "Chưa học" },
  { key: "DOING", label: "Đang học" },
  { key: "DONE", label: "Hoàn thành" },
  { key: "SKIPPED", label: "Bỏ qua" },
];

export default function LearningPathPage({ api = defaultApi }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [busyItemId, setBusyItemId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api.get());
    } catch (err) {
      setError(err.status === 401 ? "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại." : err.message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleStatusChange(itemId, nextStatus) {
    setBusyItemId(itemId);
    setError("");
    setNotice("");
    try {
      const updated = await api.updateStatus(itemId, nextStatus);
      setData(updated);
      setNotice(`Đã cập nhật trạng thái nhiệm vụ sang "${STATUS_LABELS[nextStatus]}".`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyItemId(null);
    }
  }

  if (loading) {
    return <div className="alert warning" role="status">Đang tải lộ trình học tập...</div>;
  }

  const path = data?.path;
  const summary = data?.summary || {
    total_items: 0,
    done_items: 0,
    doing_items: 0,
    todo_items: 0,
    skipped_items: 0,
    overdue_items: 0,
    progress_percent: 0,
  };
  const items = (data?.items || []).filter(
    (item) => filter === "ALL" || item.status === filter,
  );

  return (
    <div className="lp-page">
      <section>
        <p className="eyebrow">CÁ NHÂN HÓA LỘ TRÌNH</p>
        <h1>Lộ trình học & tiến độ</h1>
        <p className="welcome-copy">
          Theo dõi các nhiệm vụ ôn luyện theo ngày và cập nhật tiến độ trực tiếp lên bảng điều khiển.
        </p>
      </section>

      {error && <div className="alert error" role="alert">{error}</div>}
      {notice && <div className="alert success" role="status">{notice}</div>}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">TỔNG QUAN TIẾN ĐỘ</p>
            <h2>{path ? `Lộ trình đang hoạt động (#${path.id})` : "Chưa có lộ trình hoạt động"}</h2>
          </div>
          <button className="refresh-button" onClick={load} disabled={busyItemId !== null}>
            Làm mới
          </button>
        </div>

        <div className="lp-summary-grid">
          <div className="lp-stat">
            <small>HOÀN THÀNH</small>
            <strong>{summary.done_items}/{summary.total_items}</strong>
          </div>
          <div className="lp-stat">
            <small>ĐANG HỌC</small>
            <strong>{summary.doing_items}</strong>
          </div>
          <div className="lp-stat">
            <small>CHƯA HỌC</small>
            <strong>{summary.todo_items}</strong>
          </div>
          <div className={`lp-stat ${summary.overdue_items > 0 ? "overdue" : ""}`}>
            <small>TRỄ HẠN</small>
            <strong>{summary.overdue_items}</strong>
          </div>
        </div>

        <div className="lp-progress-head">
          <span>Tiến độ hoàn thành lộ trình</span>
          <strong>{summary.progress_percent}%</strong>
        </div>
        <div className="progress-track">
          <span style={{ width: `${summary.progress_percent}%` }} />
        </div>

        {path && (
          <p className="lp-dates">
            Thời gian: {path.start_date_display} – {path.end_date_display}
            {path.days_left != null && (
              path.days_left >= 0
                ? ` · Còn ${path.days_left} ngày`
                : ` · Đã quá hạn ${Math.abs(path.days_left)} ngày`
            )}
          </p>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">NHIỆM VỤ & HỌC LIỆU</p>
            <h2>Danh sách bài học</h2>
          </div>
        </div>

        <div className="lp-filters" role="tablist" aria-label="Lọc theo trạng thái">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`lp-filter-btn ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {items.length ? (
          <div className="lp-list">
            {items.map((item) => {
              const isBusy = busyItemId === item.id;
              return (
                <article key={item.id} className={`lp-card ${item.status.toLowerCase()}`}>
                  <div className="lp-card-top">
                    <span className={`lp-badge ${item.status.toLowerCase()}`}>
                      {STATUS_LABELS[item.status]}
                    </span>
                    <span className="lp-priority">Ưu tiên {item.priority}/5</span>
                    {item.is_overdue && <span className="lp-badge overdue">Trễ hạn</span>}
                    <span className="lp-date">Lịch học: {item.scheduled_date_display}</span>
                  </div>

                  <h3>{item.resource_title || `Ôn tập chủ đề: ${item.competency_name}`}</h3>
                  <p className="lp-meta">
                    {item.subject_name} · {item.competency_name}
                    {item.resource_type && ` · ${RESOURCE_TYPES[item.resource_type] || item.resource_type}`}
                    {` · ~${item.estimated_min} phút`}
                  </p>

                  <div className="lp-actions">
                    {item.resource_url && (
                      <a
                        className="lp-link"
                        href={item.resource_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Mở học liệu ↗
                      </a>
                    )}
                    {item.status !== "DOING" && item.status !== "DONE" && (
                      <button
                        className="lp-btn"
                        disabled={isBusy}
                        onClick={() => handleStatusChange(item.id, "DOING")}
                      >
                        Bắt đầu học
                      </button>
                    )}
                    {item.status !== "DONE" && (
                      <button
                        className="lp-btn primary"
                        disabled={isBusy}
                        onClick={() => handleStatusChange(item.id, "DONE")}
                      >
                        Hoàn thành
                      </button>
                    )}
                    {item.status !== "SKIPPED" && item.status !== "DONE" && (
                      <button
                        className="lp-btn ghost"
                        disabled={isBusy}
                        onClick={() => handleStatusChange(item.id, "SKIPPED")}
                      >
                        Bỏ qua
                      </button>
                    )}
                    {(item.status === "DONE" || item.status === "SKIPPED") && (
                      <button
                        className="lp-btn ghost"
                        disabled={isBusy}
                        onClick={() => handleStatusChange(item.id, "TODO")}
                      >
                        Đặt lại chưa học
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <span>◷</span>
            <strong>Không có nhiệm vụ phù hợp</strong>
            <p>Thử chuyển bộ lọc khác hoặc nạp dữ liệu mẫu lộ trình học.</p>
          </div>
        )}
      </section>
    </div>
  );
}
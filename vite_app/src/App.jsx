import { useCallback, useEffect, useState } from "react";
import { api, refreshCsrfToken } from "./api.js";
import ExamPage from "./features/exams/ExamPage.jsx";
import RecommendationsPage from "./recommendations/RecommendationsPage.jsx";
import { TutorChat } from "./features/tutor";
import { LearningPathPage } from "./features/learning-path";

function Brand() {
  return (
    <a className="brand" href="#" aria-label="NovaPath">
      <span className="brand-mark">N</span>
      <span className="brand-name">
        nova<span>path</span>
        <small>HỌC THÔNG MINH, THI TỰ TIN</small>
      </span>
    </a>
  );
}

function AuthPage({ onLogin, onRegister, busy, error, notice }) {
  const [mode, setMode] = useState("login");
  const [loginRole, setLoginRole] = useState("Student");
  const [fullname, setFullname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const roleOptions = [
    { value: "Student", label: "Học sinh" },
    { value: "Parent", label: "Phụ huynh" },
    { value: "Teacher", label: "Giáo viên" },
  ];

  async function submit(event) {
    event.preventDefault();
    if (mode === "login") {
      await onLogin(email, password, loginRole);
    } else {
      const registered = await onRegister(fullname, email, password);
      if (registered) {
        setMode("login");
        setPassword("");
      }
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <Brand />
        <p className="eyebrow">KHÔNG GIAN HỌC TẬP CỦA BẠN</p>
        <h1>{mode === "login" ? "Chào mừng trở lại" : "Tạo tài khoản học viên"}</h1>
        <p className="auth-description">
          {mode === "login"
            ? `Đăng nhập với tư cách ${roleOptions.find((role) => role.value === loginRole).label} để vào đúng cổng.`
            : "Bắt đầu xây dựng lộ trình ôn luyện phù hợp."}
        </p>
        {notice && <div className="alert success" role="status">{notice}</div>}
        {error && <div className="alert error" role="alert">{error}</div>}
        <form onSubmit={submit}>
          {mode === "login" && (
            <fieldset className="role-picker">
              <legend>Đăng nhập với tư cách</legend>
              {roleOptions.map((role) => (
                <label className="role-option" key={role.value}>
                  <input
                    type="radio"
                    name="login-role"
                    value={role.value}
                    checked={loginRole === role.value}
                    onChange={() => setLoginRole(role.value)}
                  />
                  <span>{role.label}</span>
                </label>
              ))}
            </fieldset>
          )}
          {mode === "register" && (
            <label>
              Họ và tên
              <input
                autoComplete="name"
                maxLength="100"
                required
                value={fullname}
                onChange={(event) => setFullname(event.target.value)}
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              maxLength="150"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Mật khẩu
            <input
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              maxLength="128"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button className="primary-button full-width" disabled={busy}>
            {busy ? "Đang xử lý..." : mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
        </form>
        <p className="auth-switch">
          {mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
          <button
            className="text-button"
            onClick={() => {
              const nextMode = mode === "login" ? "register" : "login";
              setMode(nextMode);
              if (nextMode === "register") setLoginRole("Student");
            }}
            type="button"
          >
            {mode === "login" ? "Đăng ký ngay" : "Đăng nhập"}
          </button>
        </p>
        {mode === "login" && loginRole === "Parent" && (
          <p className="auth-switch"><a href="/parent/register">Tạo tài khoản phụ huynh</a></p>
        )}
        {mode === "login" && loginRole === "Teacher" && (
          <p className="auth-switch">Tài khoản giáo viên được cấp bởi quản trị viên.</p>
        )}
      </section>
    </main>
  );
}

function EmptyState({ icon, title, description }) {
  return (
    <div className="empty-state">
      <span>{icon}</span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function Dashboard({ user, data, onNavigate }) {
  const student = data?.student;
  return (
    <>
      {data && !student && (
        <div className="alert warning" role="status">
          Chưa tìm thấy hồ sơ học tập. Hãy cập nhật hồ sơ của bạn.
        </div>
      )}
      <section className="welcome-row">
        <div>
          <p className="eyebrow">THỨC DẬY TIỀM NĂNG CỦA BẠN</p>
          <h1>Chào {user.fullname?.trim().split(/\s+/).at(-1)} <span className="wave">✦</span></h1>
          <p className="welcome-copy">Mỗi ngày một bước nhỏ, gần hơn với mục tiêu ĐGNL của bạn.</p>
        </div>
        <div className="target-card">
          <span className="target-icon">◎</span>
          <div>
            <small>MỤC TIÊU ĐGNL</small>
            <strong>{student?.TargetScore ?? "—"}<span> / 1200</span></strong>
          </div>
          {student?.ExamDate && <span className="target-date">Ngày thi {student.ExamDate}</span>}
        </div>
      </section>

      <section className="stats-grid" aria-label="Tổng quan tiến độ">
        <article className="stat-card">
          <div className="stat-top"><span className="stat-icon mint">◷</span><span className="stat-label">Thời gian học tuần này</span></div>
          <strong className="stat-value">{Math.floor((data?.weekly_minutes || 0) / 60)}<small> giờ</small> {(data?.weekly_minutes || 0) % 60}<small> phút</small></strong>
          <span className="stat-foot">Mục tiêu tuần: {(student?.DailyStudyMin || 0) * 7} phút</span>
        </article>
        <article className="stat-card">
          <div className="stat-top"><span className="stat-icon lilac">✎</span><span className="stat-label">Điểm đề gần nhất</span></div>
          <strong className="stat-value">{data?.latest_exam?.score ?? "—"}<small> điểm</small></strong>
          <span className="stat-foot stat-truncate">{data?.latest_exam?.title || "Chưa có lượt thi hoàn thành"}</span>
        </article>
        <article className="stat-card">
          <div className="stat-top"><span className="stat-icon peach">✦</span><span className="stat-label">Dự đoán từ AI</span></div>
          <strong className="stat-value">{data?.prediction?.score != null ? Math.round(data.prediction.score) : "—"}<small> điểm</small></strong>
          <span className="stat-foot">
            {data?.prediction
              ? `Khả năng đạt mục tiêu ${Math.round(data.prediction.probability * 100)}%`
              : "Chưa có dữ liệu dự đoán"}
          </span>
        </article>
      </section>

      <div className="content-grid">
        <section className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">HỌC ĐÚNG TRỌNG TÂM</p><h2>Lộ trình sắp tới</h2></div>
            <button className="text-button" onClick={() => onNavigate("learning-path")}>Xem lộ trình →</button>
          </div>
          {data?.tasks?.length ? (
            <div className="task-list">
              {data.tasks.map((task, index) => (
                <article className="task-row" key={`${task.CompetencyName}-${index}`}>
                  <span className={`task-marker ${task.Status === "DOING" ? "in-progress" : ""}`} />
                  <div className="task-copy">
                    <strong>{task.CompetencyName}</strong>
                    <span>{task.ResourceTitle || "Ôn tập kiến thức trọng tâm"}</span>
                  </div>
                  <span className="task-date">{task.ScheduledDate}</span>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState icon="◷" title="Chưa có nhiệm vụ học tập" description="Lộ trình cá nhân sẽ xuất hiện khi được tạo trong hệ thống." />
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div><p className="eyebrow">GỢI Ý CÁ NHÂN HÓA</p><h2>Tiếp theo nên học gì?</h2></div>
            <span className="sparkle">✦</span>
          </div>
          {data?.recommendations?.length ? (
            <div className="recommendation-list">
              {data.recommendations.map((item, index) => (
                <article className="recommendation-card" key={`${item.ResourceTitle}-${index}`}>
                  <span className="recommendation-icon">✧</span>
                  <div><strong>{item.ResourceTitle || "Bài luyện tập gợi ý"}</strong><p>{item.Reason || item.QuestionContent || "Ôn tập thêm để củng cố kiến thức."}</p></div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState icon="✧" title="Chưa có gợi ý mới" description="Gợi ý học tập sẽ hiển thị tại đây." />
          )}
        </section>
      </div>

      <section className="panel competency-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">BẢN ĐỒ NĂNG LỰC</p><h2>Năng lực học tập</h2></div>
          <button className="text-button" onClick={() => onNavigate("competencies")}>Xem tất cả →</button>
        </div>
        {data?.competencies?.length ? (
          <div className="competency-grid">
            {data.competencies.slice(0, 6).map((item, index) => (
              <article className="competency-item" key={`${item.SubjectName}-${item.CompetencyName}-${index}`}>
                <div><span>{item.CompetencyName}</span><strong>{item.MasteryPercent}%</strong></div>
                <div className="progress-track"><span style={{ width: `${item.MasteryPercent}%` }} /></div>
                <small>{item.SubjectName}</small>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState icon="▤" title="Chưa có dữ liệu năng lực" description="Kết quả học tập sẽ giúp hoàn thiện bản đồ năng lực." />
        )}
      </section>
    </>
  );
}

function ProfileForm({ profile, onSave, busy, error, notice }) {
  const [form, setForm] = useState(() => ({
    fullname: profile?.FullName || "",
    phone: profile?.Phone || "",
    school: profile?.SchoolName || "",
    target_score: profile?.TargetScore ?? 0,
    exam_date: profile?.ExamDate || "",
    daily_study_min: profile?.DailyStudyMin ?? 60,
  }));
  useEffect(() => {
    setForm({
      fullname: profile?.FullName || "",
      phone: profile?.Phone || "",
      school: profile?.SchoolName || "",
      target_score: profile?.TargetScore ?? 0,
      exam_date: profile?.ExamDate || "",
      daily_study_min: profile?.DailyStudyMin ?? 60,
    });
  }, [profile]);
  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  return (
    <section className="profile-wrap">
      <p className="eyebrow">KHÔNG GIAN HỌC TẬP</p>
      <h1>Cập nhật hồ sơ</h1>
      <p className="welcome-copy">Thông tin này giúp NovaPath cá nhân hóa lộ trình học.</p>
      {notice && <div className="alert success" role="status">{notice}</div>}
      {error && <div className="alert error" role="alert">{error}</div>}
      <form className="panel profile-form" onSubmit={(event) => { event.preventDefault(); onSave(form); }}>
        <label>Họ và tên<input maxLength="100" required value={form.fullname} onChange={(event) => update("fullname", event.target.value)} /></label>
        <label>Số điện thoại<input maxLength="15" value={form.phone} onChange={(event) => update("phone", event.target.value)} /></label>
        <label>Trường đang học<input maxLength="150" value={form.school} onChange={(event) => update("school", event.target.value)} /></label>
        <label>Điểm mục tiêu (0 - 1200)<input type="number" min="0" max="1200" required value={form.target_score} onChange={(event) => update("target_score", event.target.value)} /></label>
        <label>Ngày thi dự kiến<input type="date" value={form.exam_date} onChange={(event) => update("exam_date", event.target.value)} /></label>
        <label>Thời lượng học mục tiêu (phút/ngày)<input type="number" min="1" required value={form.daily_study_min} onChange={(event) => update("daily_study_min", event.target.value)} /></label>
        <button className="primary-button" disabled={busy}>{busy ? "Đang lưu..." : "Lưu thay đổi"}</button>
      </form>
    </section>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [profile, setProfile] = useState(null);
  const [page, setPage] = useState("dashboard");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const roleLandingPaths = {
    Parent: "/parent",
    Teacher: "/teacher/students",
    Admin: "/teacher/questions",
  };

  const loadPageData = useCallback(async (currentPage) => {
    setError("");
    try {
      if (currentPage === "profile") {
        setProfile(await api.profile());
      } else if (!["exams", "recommendations", "tutor", "learning-path"].includes(currentPage)) {
        setDashboard(await api.dashboard());
      }
    } catch (requestError) {
      if (requestError.status === 401) {
        setUser(null);
      } else {
        setError(requestError.message);
      }
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        await refreshCsrfToken();
        const result = await api.session();
        if (active && result.user) {
          if (result.user.role === "Student") {
            setUser(result.user);
            await loadPageData("dashboard");
          } else if (roleLandingPaths[result.user.role]) {
            window.location.assign(roleLandingPaths[result.user.role]);
          } else {
            setError("Vai trò tài khoản không được ứng dụng này hỗ trợ.");
          }
        }
      } catch (requestError) {
        if (active) setError(requestError.message);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [loadPageData]);

  useEffect(() => {
    if (!user) return undefined;
    function refreshWhenVisible() {
      if (document.visibilityState === "visible") {
        loadPageData(page);
      }
    }
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => document.removeEventListener("visibilitychange", refreshWhenVisible);
  }, [loadPageData, page, user]);

  async function login(email, password, role) {
    setBusy(true);
    setError("");
    try {
      const result = await api.login(email, password, role);
      setNotice("");
      if (result.user.role === "Student") {
        setUser(result.user);
        setPage("dashboard");
        await loadPageData("dashboard");
      } else if (roleLandingPaths[result.user.role]) {
        window.location.assign(roleLandingPaths[result.user.role]);
      } else {
        setError("Vai trò tài khoản không được ứng dụng này hỗ trợ.");
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function register(fullname, email, password) {
    setBusy(true);
    setError("");
    try {
      const result = await api.register(fullname, email, password);
      setNotice(result.message);
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError("");
    try {
      await api.logout();
      setUser(null);
      setDashboard(null);
      setProfile(null);
      setPage("dashboard");
      setNotice("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function navigate(nextPage) {
    setPage(nextPage);
    setNotice("");
    await loadPageData(nextPage);
  }

  async function saveProfile(values) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.updateProfile(values);
      setUser((current) => ({ ...current, fullname: result.fullname }));
      setProfile((current) => ({ ...current, ...values }));
      setNotice(result.message);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="loading-screen"><Brand /><p>Đang kết nối NovaPath...</p></main>;
  }

  if (!user || user.role !== "Student") {
    return <AuthPage onLogin={login} onRegister={register} busy={busy} error={error} notice={notice} />;
  }

  const pageTitles = {
    dashboard: "Tổng quan",
    "learning-path": "Lộ trình học",
    exams: "Làm bài thi",
    recommendations: "Gợi ý & dự đoán",
    tutor: "AI Tutor",
    competencies: "Năng lực",
    profile: "Hồ sơ",
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <p className="nav-caption">KHÔNG GIAN HỌC TẬP</p>
        <nav className="main-nav" aria-label="Điều hướng chính">
          <button className={`nav-link ${page === "dashboard" ? "active" : ""}`} onClick={() => navigate("dashboard")}><span className="nav-icon">⌂</span>Tổng quan</button>
          <button className={`nav-link ${page === "learning-path" ? "active" : ""}`} onClick={() => navigate("learning-path")}><span className="nav-icon">◷</span>Lộ trình học</button>
          <button className={`nav-link ${page === "exams" ? "active" : ""}`} onClick={() => navigate("exams")}><span className="nav-icon">✎</span>Làm bài thi</button>
          <button className={`nav-link ${page === "recommendations" ? "active" : ""}`} onClick={() => navigate("recommendations")}><span className="nav-icon">✧</span>Gợi ý &amp; dự đoán</button>
          <button className={`nav-link ${page === "tutor" ? "active" : ""}`} onClick={() => navigate("tutor")}><span className="nav-icon">✦</span>AI Tutor</button>
          <button className={`nav-link ${page === "competencies" ? "active" : ""}`} onClick={() => navigate("competencies")}><span className="nav-icon">▤</span>Năng lực</button>
          <button className={`nav-link ${page === "profile" ? "active" : ""}`} onClick={() => navigate("profile")}><span className="nav-icon">♙</span>Hồ sơ của tôi</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="ai-note"><span className="ai-spark">✦</span><p><strong>Học theo cách của bạn</strong><br />NovaPath từng bước cá nhân hóa hành trình ĐGNL.</p></div>
          <div className="sidebar-user">
            <span className="avatar">{user.fullname?.slice(0, 1) || "N"}</span>
            <span><strong>{user.fullname}</strong><small>{user.email}</small></span>
            <button className="user-menu" onClick={logout} disabled={busy} aria-label="Đăng xuất" title="Đăng xuất">↪</button>
          </div>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Không gian học tập <span>/</span> <strong>{pageTitles[page] || "Tổng quan"}</strong></div>
          <div className="topbar-right"><span>{new Intl.DateTimeFormat("vi-VN", { dateStyle: "long" }).format(new Date())}</span><button className="refresh-button" onClick={() => loadPageData(page)}>Làm mới</button></div>
        </header>
        <div className="page-content">
          {error && !page.includes("profile") && <div className="alert error" role="alert">{error}</div>}
          {page === "learning-path" ? (
            <LearningPathPage />
          ) : page === "exams" ? (
            <ExamPage api={api} />
          ) : page === "recommendations" ? (
            <RecommendationsPage />
          ) : page === "tutor" ? (
            <TutorChat studentName={user.fullname} />
          ) : page === "profile" ? (
            profile ? <ProfileForm profile={profile} onSave={saveProfile} busy={busy} error={error} notice={notice} /> : <div className="alert warning">Đang tải hồ sơ...</div>
          ) : page === "competencies" ? (
            <section className="panel"><div className="panel-heading"><div><p className="eyebrow">BẢN ĐỒ NĂNG LỰC</p><h2>Năng lực học tập</h2></div></div>{dashboard ? <div className="competency-grid">{dashboard.competencies?.map((item, index) => <article className="competency-item" key={`${item.SubjectName}-${item.CompetencyName}-${index}`}><div><span>{item.CompetencyName}</span><strong>{item.MasteryPercent}%</strong></div><div className="progress-track"><span style={{ width: `${item.MasteryPercent}%` }} /></div><small>{item.SubjectName}</small></article>)}</div> : <EmptyState icon="▤" title="Đang tải năng lực" description="Vui lòng đợi trong giây lát." />}</section>
          ) : dashboard ? (
            <Dashboard user={user} data={dashboard} onNavigate={navigate} />
          ) : (
            <div className="alert warning">Đang tải dashboard...</div>
          )}
        </div>
      </main>
    </div>
  );
}
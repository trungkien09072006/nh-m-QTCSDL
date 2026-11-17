USE AILearningDB;
GO

/*
===============================================================================
PHÂN HỆ 02 - DATA VIEWS: PHẦN 9
CẤP QUYỀN TRÊN VIEW / HÀM BẢNG THEO VAI TRÒ (LEAST PRIVILEGE)
-------------------------------------------------------------------------------
- Role_Admin và Role_App đã có SELECT trên toàn schema dbo -> tự động dùng được mọi view mới
  (Role_App là backend / AI Engine: dùng vw_AIStudentFeatures, vw_AnswerHistory...).
- Chạy được trước hoặc sau 04_security\01_logins_users_roles.sql: role nào chưa có thì bỏ qua
  và in cảnh báo; chạy lại file này sau khi tạo role là đủ.
- Ownership chaining: người dùng chỉ cần quyền trên view/hàm, không cần quyền trên bảng gốc.
  Row-Level Security vẫn áp dụng trên bảng gốc nên mỗi người chỉ thấy dữ liệu của mình.
- Học sinh / Phụ huynh KHÔNG được cấp các view lộ đáp án hoặc dữ liệu của người khác:
  vw_QuestionBank, vw_QuestionStatistics, vw_QuestionQuality, vw_OptionDistribution,
  vw_ExamSummary, vw_ExamRanking, vw_RecommendationQuality, vw_AnswerHistory, vw_AIStudentFeatures.
- Chỉ Admin/Backend được xem vw_UserDirectory, vw_SystemSettings, vw_AuditTrail,
  vw_PlatformActivityDaily, vw_SystemOverview.
===============================================================================
*/
PRINT '>>> [09_view_permissions.sql] Đang cấp quyền trên view / hàm...';
GO

DECLARE @grants TABLE (RoleName SYSNAME, ObjName SYSNAME, Perm VARCHAR(20));

INSERT INTO @grants (RoleName, ObjName, Perm) VALUES
-- ===== GIÁO VIÊN: nội dung, chất lượng câu hỏi, chất lượng gợi ý AI, tiến độ học sinh =====
('Role_Teacher', 'vw_StudentOverview', 'SELECT'),
('Role_Teacher', 'vw_ParentChildren', 'SELECT'),
('Role_Teacher', 'vw_CompetencyTree', 'SELECT'),
('Role_Teacher', 'vw_LearningResourceCatalog', 'SELECT'),
('Role_Teacher', 'vw_QuestionBank', 'SELECT'),
('Role_Teacher', 'vw_ExamSummary', 'SELECT'),
('Role_Teacher', 'vw_AvailableExams', 'SELECT'),
('Role_Teacher', 'vw_AttemptResults', 'SELECT'),
('Role_Teacher', 'vw_AnswerReview', 'SELECT'),
('Role_Teacher', 'vw_QuestionStatistics', 'SELECT'),
('Role_Teacher', 'vw_QuestionQuality', 'SELECT'),
('Role_Teacher', 'vw_OptionDistribution', 'SELECT'),
('Role_Teacher', 'vw_ExamRanking', 'SELECT'),
('Role_Teacher', 'vw_StudentCompetencyProfile', 'SELECT'),
('Role_Teacher', 'vw_SubjectMastery', 'SELECT'),
('Role_Teacher', 'vw_DiagnosticResults', 'SELECT'),
('Role_Teacher', 'vw_CompetencyAccuracy', 'SELECT'),
('Role_Teacher', 'vw_AnswerHistory', 'SELECT'),
('Role_Teacher', 'vw_LearningPathProgress', 'SELECT'),
('Role_Teacher', 'vw_LearningPathItems', 'SELECT'),
('Role_Teacher', 'vw_ActiveLearningPaths', 'SELECT'),
('Role_Teacher', 'vw_Recommendations', 'SELECT'),
('Role_Teacher', 'vw_RecommendationQuality', 'SELECT'),
('Role_Teacher', 'vw_LatestPrediction', 'SELECT'),
('Role_Teacher', 'vw_StudyActivitySummary', 'SELECT'),
('Role_Teacher', 'vw_DailyStudyTime', 'SELECT'),
('Role_Teacher', 'vw_WeeklyStudyTime', 'SELECT'),
('Role_Teacher', 'vw_StudyConsistency', 'SELECT'),
('Role_Teacher', 'vw_TutorUsage', 'SELECT'),
('Role_Teacher', 'vw_StudentAlerts', 'SELECT'),
('Role_Teacher', 'vw_ExamReadiness', 'SELECT'),
('Role_Teacher', 'vw_QuestionCountByCompetency', 'SELECT'),
('Role_Teacher', 'fn_WeakCompetencies', 'SELECT'),
('Role_Teacher', 'fn_PracticeCandidates', 'SELECT'),
('Role_Teacher', 'fn_StudyTimeBetween', 'SELECT'),
('Role_Teacher', 'fn_ScoreTrend', 'SELECT'),
('Role_Teacher', 'fn_ExamResults', 'SELECT'),
-- ===== HỌC SINH: chỉ dữ liệu của chính mình (RLS), nội dung không lộ đáp án =====
('Role_Student', 'vw_StudentOverview', 'SELECT'),
('Role_Student', 'vw_CompetencyTree', 'SELECT'),
('Role_Student', 'vw_LearningResourceCatalog', 'SELECT'),
('Role_Student', 'vw_AvailableExams', 'SELECT'),
('Role_Student', 'vw_AttemptResults', 'SELECT'),
('Role_Student', 'vw_AnswerReview', 'SELECT'),
('Role_Student', 'vw_StudentCompetencyProfile', 'SELECT'),
('Role_Student', 'vw_SubjectMastery', 'SELECT'),
('Role_Student', 'vw_DiagnosticResults', 'SELECT'),
('Role_Student', 'vw_CompetencyAccuracy', 'SELECT'),
('Role_Student', 'vw_LearningPathProgress', 'SELECT'),
('Role_Student', 'vw_LearningPathItems', 'SELECT'),
('Role_Student', 'vw_Recommendations', 'SELECT'),
('Role_Student', 'vw_LatestPrediction', 'SELECT'),
('Role_Student', 'vw_StudyActivitySummary', 'SELECT'),
('Role_Student', 'vw_DailyStudyTime', 'SELECT'),
('Role_Student', 'vw_WeeklyStudyTime', 'SELECT'),
('Role_Student', 'vw_StudyConsistency', 'SELECT'),
('Role_Student', 'vw_TutorUsage', 'SELECT'),
('Role_Student', 'vw_NotificationInbox', 'SELECT'),
('Role_Student', 'vw_NotificationInbox', 'UPDATE'),
('Role_Student', 'vw_TutorConversation', 'SELECT'),
('Role_Student', 'vw_StudentAlerts', 'SELECT'),
('Role_Student', 'vw_ExamReadiness', 'SELECT'),
('Role_Student', 'vw_StudentEditableProfile', 'SELECT'),
('Role_Student', 'vw_StudentEditableProfile', 'UPDATE'),
('Role_Student', 'fn_WeakCompetencies', 'SELECT'),
('Role_Student', 'fn_PracticeCandidates', 'SELECT'),
('Role_Student', 'fn_StudyTimeBetween', 'SELECT'),
('Role_Student', 'fn_ScoreTrend', 'SELECT'),
-- ===== PHỤ HUYNH: chỉ theo dõi con em (RLS qua ParentStudent), không xem câu hỏi/đáp án =====
('Role_Parent', 'vw_ParentChildren', 'SELECT'),
('Role_Parent', 'vw_ParentDashboard', 'SELECT'),
('Role_Parent', 'vw_StudentOverview', 'SELECT'),
('Role_Parent', 'vw_AttemptResults', 'SELECT'),
('Role_Parent', 'vw_StudentCompetencyProfile', 'SELECT'),
('Role_Parent', 'vw_SubjectMastery', 'SELECT'),
('Role_Parent', 'vw_DiagnosticResults', 'SELECT'),
('Role_Parent', 'vw_CompetencyAccuracy', 'SELECT'),
('Role_Parent', 'vw_LearningPathProgress', 'SELECT'),
('Role_Parent', 'vw_LatestPrediction', 'SELECT'),
('Role_Parent', 'vw_StudyActivitySummary', 'SELECT'),
('Role_Parent', 'vw_DailyStudyTime', 'SELECT'),
('Role_Parent', 'vw_WeeklyStudyTime', 'SELECT'),
('Role_Parent', 'vw_StudyConsistency', 'SELECT'),
('Role_Parent', 'vw_StudentAlerts', 'SELECT'),
('Role_Parent', 'vw_ExamReadiness', 'SELECT'),
('Role_Parent', 'vw_NotificationInbox', 'SELECT'),
('Role_Parent', 'vw_NotificationInbox', 'UPDATE'),
('Role_Parent', 'vw_CompetencyTree', 'SELECT'),
('Role_Parent', 'fn_WeakCompetencies', 'SELECT'),
('Role_Parent', 'fn_StudyTimeBetween', 'SELECT'),
('Role_Parent', 'fn_ScoreTrend', 'SELECT');

DECLARE @role SYSNAME, @obj SYSNAME, @perm VARCHAR(20), @sql NVARCHAR(600);
DECLARE cur CURSOR LOCAL FAST_FORWARD FOR SELECT RoleName, ObjName, Perm FROM @grants;
OPEN cur;
FETCH NEXT FROM cur INTO @role, @obj, @perm;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF DATABASE_PRINCIPAL_ID(@role) IS NULL
        PRINT N'    ! Bỏ qua ' + @obj + N': chưa có role ' + @role + N' (chạy lại file này sau 04_security\01_logins_users_roles.sql).';
    ELSE IF OBJECT_ID(N'dbo.' + @obj) IS NULL
        PRINT N'    ! Bỏ qua: chưa có đối tượng dbo.' + @obj;
    ELSE
    BEGIN
        SET @sql = N'GRANT ' + @perm + N' ON dbo.' + QUOTENAME(@obj) + N' TO ' + QUOTENAME(@role) + N';';
        EXEC (@sql);
    END;
    FETCH NEXT FROM cur INTO @role, @obj, @perm;
END;
CLOSE cur;
DEALLOCATE cur;
GO

-- vw_StudentExamView đã được cấp cho Role_Student trong 04_security\04_row_level_security.sql

PRINT '    + Đã cấp quyền view / hàm theo vai trò.';
GO

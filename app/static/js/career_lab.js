(function () {
  const state = {
    resumes: [],
    roles: [],
    latestAnalysis: null,
    latestRoute: null,
    analyticsStatus: null,
    catalogQuality: null,
    routeRuns: [],
    skillReview: null,
    latestBaselineEvaluation: null,
    selectedUploadFile: null,
  };

  const els = {};
  const fallbackRoles = [
    {
      target_role: 'Data Analyst',
      requirement_source: 'role_seed',
      required_skills_count: 0,
      synced_job_postings_count: 0,
      is_market_backed: false,
    },
    {
      target_role: 'Business Analyst',
      requirement_source: 'role_seed',
      required_skills_count: 0,
      synced_job_postings_count: 0,
      is_market_backed: false,
    },
    {
      target_role: 'Junior Data Scientist',
      requirement_source: 'role_seed',
      required_skills_count: 0,
      synced_job_postings_count: 0,
      is_market_backed: false,
    },
  ];

  function bindElements() {
    els.form = document.getElementById('careerLabForm');
    els.resumeSelect = document.getElementById('resumeSelect');
    els.targetRoleSelect = document.getElementById('targetRoleSelect');
    els.runButton = document.getElementById('runAnalysisBtn');
    els.empty = document.getElementById('careerLabEmpty');
    els.status = document.getElementById('careerLabStatus');
    els.uploadForm = document.getElementById('careerLabUploadForm');
    els.uploadArea = document.getElementById('careerLabUploadArea');
    els.uploadFileInput = document.getElementById('careerLabCvFile');
    els.uploadButton = document.getElementById('careerLabUploadBtn');
    els.uploadFileName = document.getElementById('careerLabUploadFileName');
    els.uploadStatus = document.getElementById('careerLabUploadStatus');
    els.analyticsReadiness = document.querySelector('.analytics-readiness');
    els.analyticsReadinessBadge = document.getElementById('analyticsReadinessBadge');
    els.analyticsReadinessTitle = document.getElementById('analyticsReadinessTitle');
    els.analyticsReadinessCopy = document.getElementById('analyticsReadinessCopy');
    els.analyticsReadinessStats = document.getElementById('analyticsReadinessStats');
    els.skillReviewCounts = document.getElementById('skillReviewCounts');
    els.skillReviewList = document.getElementById('skillReviewList');
    els.manualSkillForm = document.getElementById('manualSkillForm');
    els.manualSkillInput = document.getElementById('manualSkillInput');
    els.manualSkillButton = document.getElementById('manualSkillButton');
    els.overallReadinessScore = document.getElementById('overallReadinessScore');
    els.matchScore = document.getElementById('matchScore');
    els.contextSimilarityScore = document.getElementById('contextSimilarityScore');
    els.contextMatchLevel = document.getElementById('contextMatchLevel');
    els.missingSkillsCount = document.getElementById('missingSkillsCount');
    els.recommendedCourseCount = document.getElementById('recommendedCourseCount');
    els.requirementsSource = document.getElementById('requirementsSource');
    els.semanticStatus = document.getElementById('semanticStatus');
    els.semanticMatchCount = document.getElementById('semanticMatchCount');
    els.skillComparisonList = document.getElementById('skillComparisonList');
    els.improvementList = document.getElementById('improvementList');
    els.insightsList = document.getElementById('insightsList');
    els.courseRouteList = document.getElementById('courseRouteList');
    els.routeForm = document.getElementById('routeOptimizationForm');
    els.routeBudget = document.getElementById('routeBudget');
    els.routeHours = document.getElementById('routeHours');
    els.routeMaxCourses = document.getElementById('routeMaxCourses');
    els.generateRouteButton = document.getElementById('generateRouteBtn');
    els.routeSummaryStrip = document.getElementById('routeSummaryStrip');
    els.routeSummaryCopy = document.getElementById('routeSummaryCopy');
    els.routeScoreBefore = document.getElementById('routeScoreBefore');
    els.routeScoreAfter = document.getElementById('routeScoreAfter');
    els.routeTotalCost = document.getElementById('routeTotalCost');
    els.routeTotalHours = document.getElementById('routeTotalHours');
    els.routeHistoryList = document.getElementById('routeHistoryList');
    els.dashboardSummary = document.getElementById('dashboardSummary');
    els.dashboardSummaryTitle = document.getElementById('dashboardSummaryTitle');
    els.dashboardSummaryCopy = document.getElementById('dashboardSummaryCopy');
    els.summaryProjectedScore = document.getElementById('summaryProjectedScore');
    els.summaryTotalCost = document.getElementById('summaryTotalCost');
    els.summaryTotalHours = document.getElementById('summaryTotalHours');
    els.summaryBestBaseline = document.getElementById('summaryBestBaseline');
    els.baselineSummary = document.getElementById('baselineSummary');
    els.baselineMethodList = document.getElementById('baselineMethodList');
    els.catalogQualityPanel = document.getElementById('catalogQualityPanel');
    els.embeddingStatusList = document.getElementById('embeddingStatusList');
    els.marketSignalsList = document.getElementById('marketSignalsList');
    els.radar = document.getElementById('skillRadar');
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDate(value) {
    if (!value) return 'Recently uploaded';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Recently uploaded';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function clampPercent(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
  }

  function scorePercent(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '--';
    return `${Math.round(clampPercent(numeric <= 1 ? numeric * 100 : numeric))}%`;
  }

  function scoreDecimal(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '--';
    return numeric.toFixed(2);
  }

  function formatMoney(value, currency) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return 'Free';
    return `${currency || 'CAD'} ${numeric.toFixed(0)}`;
  }

  function formatHours(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return 'Self-paced';
    return `${numeric.toFixed(numeric % 1 ? 1 : 0)}h`;
  }

  function formatDateTime(value) {
    if (!value) return 'Recent';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Recent';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function safeExternalUrl(value) {
    try {
      const url = new URL(String(value || ''), window.location.origin);
      if (url.protocol === 'http:' || url.protocol === 'https:') return url.href;
    } catch (error) {
      return '';
    }
    return '';
  }

  function setStatus(message, type) {
    els.status.textContent = message;
    els.status.classList.toggle('error', type === 'error');
  }

  function sourceLabel(source) {
    if (source === 'job_postings') return 'Job postings';
    if (source === 'role_seed') return 'Starter profile';
    if (source === 'none') return 'Not ready';
    return 'Role profile';
  }

  function roleOptionLabel(role) {
    const source = role.is_market_backed ? 'Market-backed' : sourceLabel(role.requirement_source);
    const skillCount = Number(role.required_skills_count || 0);
    const suffix = skillCount ? `${source}, ${skillCount} skills` : source;
    return `${role.target_role} - ${suffix}`;
  }

  function sourceExplanation(source) {
    if (source === 'job_postings') {
      return 'This analysis is using skills extracted from synced employer job postings, so the requirements reflect live market signals.';
    }
    if (source === 'role_seed') {
      return 'This analysis is using starter role profiles. Sync job postings later to make requirements more market-driven.';
    }
    return 'No role requirements were found yet. Seed the analytical catalog or sync job postings to activate market matching.';
  }

  function setUploadStatus(message, type) {
    if (!els.uploadStatus) return;
    els.uploadStatus.textContent = message || '';
    els.uploadStatus.classList.toggle('error', type === 'error');
    els.uploadStatus.classList.toggle('success', type === 'success');
  }

  function validateUploadFile(file) {
    if (!file) return 'Choose a CV file first.';
    const allowedTypes = new Set([
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]);
    const allowedExtensions = /\.(pdf|doc|docx)$/i;
    if (!allowedTypes.has(file.type) && !allowedExtensions.test(file.name || '')) {
      return 'Only PDF, DOC, or DOCX files are allowed.';
    }
    if (file.size > 5 * 1024 * 1024) {
      return 'File size must be less than 5MB.';
    }
    return '';
  }

  function setSelectedUploadFile(file) {
    const validationError = validateUploadFile(file);
    if (validationError) {
      state.selectedUploadFile = null;
      if (els.uploadFileInput) els.uploadFileInput.value = '';
      if (els.uploadFileName) els.uploadFileName.textContent = 'Choose or drop a CV';
      setUploadStatus(validationError, 'error');
      updateRunButtonState();
      return;
    }

    state.selectedUploadFile = file;
    if (els.uploadFileName) els.uploadFileName.textContent = file.name;
    setUploadStatus('Ready to upload.', 'success');
    updateRunButtonState();
  }

  async function uploadResumeFromLab(event) {
    event.preventDefault();
    const file = state.selectedUploadFile;
    const validationError = validateUploadFile(file);
    if (validationError) {
      setUploadStatus(validationError, 'error');
      return;
    }

    const formData = new FormData();
    formData.append('cv', file);
    if (els.uploadButton) els.uploadButton.disabled = true;
    setUploadStatus('Uploading CV...', '');

    try {
      const payload = await apiFetch('/api/v1/profile/cv/upload', {
        method: 'POST',
        body: formData,
      });
      state.selectedUploadFile = null;
      if (els.uploadFileInput) els.uploadFileInput.value = '';
      if (els.uploadFileName) els.uploadFileName.textContent = 'Choose or drop a CV';
      setUploadStatus('CV uploaded. Resume selector refreshed.', 'success');
      await loadResumes(payload?.resume_id);
      setStatus('CV uploaded. Choose a target role and run your gap analysis.');
    } catch (error) {
      setUploadStatus(`${error.message || 'Upload failed.'} You can also upload from your profile.`, 'error');
    } finally {
      updateRunButtonState();
    }
  }

  async function apiFetch(url, options) {
    const requestOptions = options || {};
    const isFormData = requestOptions.body instanceof FormData;
    let response;
    try {
      response = await fetch(url, {
        credentials: 'include',
        cache: 'no-store',
        ...requestOptions,
        headers: {
          ...(requestOptions.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
          ...(requestOptions.headers || {}),
        },
      });
    } catch (error) {
      throw new Error('StudentsCompass API is unreachable. Make sure the local server is running, then reload this page.');
    }
    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return null;
    }
    if (!response.ok) {
      let detail = 'Request failed';
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (error) {
        detail = response.statusText || detail;
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function updateRunButtonState() {
    els.runButton.disabled = !state.resumes.length || !els.resumeSelect.value || !els.targetRoleSelect.value;
    if (els.generateRouteButton) {
      els.generateRouteButton.disabled = !state.resumes.length || !els.resumeSelect.value || !els.targetRoleSelect.value;
    }
    if (els.manualSkillButton) {
      els.manualSkillButton.disabled = !state.resumes.length || !els.resumeSelect.value;
    }
    if (els.uploadButton) {
      els.uploadButton.disabled = !state.selectedUploadFile;
    }
  }

  async function loadResumes(preferredResumeId) {
    updateRunButtonState();
    const resumes = await apiFetch('/api/v1/profile/cv');
    if (!resumes) return;

    state.resumes = Array.isArray(resumes) ? resumes : [];
    if (!state.resumes.length) {
      els.resumeSelect.innerHTML = '<option value="">No resume uploaded</option>';
      els.empty.hidden = false;
      setStatus('Upload a CV first so the Career Optimization Lab can analyze your current skill profile.');
      drawRadar(null);
      renderSkillReview(null);
      updateRunButtonState();
      return;
    }

    const preferredIndex = preferredResumeId
      ? state.resumes.findIndex((resume) => String(resume.id) === String(preferredResumeId))
      : 0;
    const selectedIndex = preferredIndex >= 0 ? preferredIndex : 0;
    els.empty.hidden = true;
    els.resumeSelect.innerHTML = state.resumes.map((resume, index) => {
      const label = `${resume.original_filename || 'Resume'} - ${formatDate(resume.created_at)}`;
      return `<option value="${escapeHtml(resume.id)}" ${index === selectedIndex ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    updateRunButtonState();
    setStatus('Ready. Pick a target role and run your gap analysis.');
    await loadResumeSkillReview();
  }

  async function loadResumeSkillReview() {
    if (!els.skillReviewList || !els.resumeSelect.value) {
      renderSkillReview(null);
      return;
    }

    try {
      const payload = await apiFetch(`/api/v1/capstone/resumes/${encodeURIComponent(els.resumeSelect.value)}/skills`);
      if (!payload) return;
      state.skillReview = payload;
      renderSkillReview(payload);
    } catch (error) {
      els.skillReviewList.innerHTML = `<p class="panel-placeholder">Skill review is unavailable: ${escapeHtml(error.message || 'Request failed')}.</p>`;
    }
  }

  async function loadTargetRoles() {
    els.targetRoleSelect.innerHTML = '<option value="">Loading target roles...</option>';
    updateRunButtonState();

    try {
      const payload = await apiFetch('/api/v1/capstone/analytics/roles');
      if (!payload) return;
      state.roles = Array.isArray(payload.roles) && payload.roles.length ? payload.roles : fallbackRoles;
    } catch (error) {
      state.roles = fallbackRoles;
    }

    renderTargetRoles();
  }

  function renderTargetRoles() {
    if (!state.roles.length) {
      els.targetRoleSelect.innerHTML = '<option value="">No target roles available</option>';
      updateRunButtonState();
      return;
    }

    els.targetRoleSelect.innerHTML = state.roles.map((role, index) => `
      <option value="${escapeHtml(role.target_role)}" ${index === 0 ? 'selected' : ''}>
        ${escapeHtml(roleOptionLabel(role))}
      </option>
    `).join('');
    updateRunButtonState();
  }

  async function loadAnalyticsStatus() {
    if (!els.analyticsReadiness) return;

    try {
      const status = await apiFetch('/api/v1/capstone/analytics/status');
      if (!status) return;
      state.analyticsStatus = status;
      renderAnalyticsStatus(status);
    } catch (error) {
      renderAnalyticsStatusError(error.message || 'Unable to load analytics status.');
    }
  }

  async function loadCatalogQuality() {
    if (!els.catalogQualityPanel) return;
    try {
      const quality = await apiFetch('/api/v1/capstone/catalog/quality');
      if (!quality) return;
      state.catalogQuality = quality;
      renderCatalogQuality(quality);
    } catch (error) {
      els.catalogQualityPanel.innerHTML = `<p class="panel-placeholder">Catalog quality is unavailable: ${escapeHtml(error.message || 'Request failed')}.</p>`;
    }
  }

  async function loadRouteRuns() {
    if (!els.routeHistoryList) return;
    try {
      const payload = await apiFetch('/api/v1/capstone/learning-route/runs?limit=5');
      if (!payload) return;
      state.routeRuns = Array.isArray(payload.runs) ? payload.runs : [];
      renderRouteHistory(state.routeRuns);
    } catch (error) {
      els.routeHistoryList.innerHTML = `<p class="panel-placeholder">Route history is unavailable: ${escapeHtml(error.message || 'Request failed')}.</p>`;
    }
  }

  function renderAnalyticsStatus(status) {
    const hasMarketSignals = Number(status.real_job_skill_links_count || 0) > 0;
    const catalogReady = Boolean(status.catalog_ready);
    const className = hasMarketSignals ? 'ready' : catalogReady ? 'warning' : 'error';

    els.analyticsReadiness.classList.remove('ready', 'warning', 'error');
    els.analyticsReadiness.classList.add(className);

    els.analyticsReadinessBadge.textContent = hasMarketSignals
      ? 'Market-backed'
      : catalogReady
        ? 'Starter catalog'
        : 'Needs setup';

    els.analyticsReadinessTitle.textContent = hasMarketSignals
      ? 'Using synced job posting signals when roles match'
      : catalogReady
        ? 'Using the Phase 1 starter role catalog'
        : 'Career analytics catalog is not ready';

    els.analyticsReadinessCopy.textContent = status.next_action || (
      hasMarketSignals
        ? 'The system has extracted skills from employer postings and can prefer market-backed requirements over starter profiles.'
        : 'The starter catalog is enough for clear P1 gap analysis while job posting skill extraction grows.'
    );

    els.analyticsReadinessStats.innerHTML = `
      <span><strong>${escapeHtml(status.skills_count)}</strong> skills</span>
      <span><strong>${escapeHtml(status.courses_count)}</strong> courses</span>
      <span><strong>${escapeHtml(status.synced_job_postings_count)}</strong> synced jobs</span>
      <span><strong>${escapeHtml(status.resume_embeddings_count)}</strong> embeddings</span>
    `;

    renderEmbeddingStatus(status);
  }

  function renderAnalyticsStatusError(message) {
    if (!els.analyticsReadiness) return;
    els.analyticsReadiness.classList.remove('ready', 'warning');
    els.analyticsReadiness.classList.add('error');
    els.analyticsReadinessBadge.textContent = 'Status unavailable';
    els.analyticsReadinessTitle.textContent = 'Career analytics status could not be loaded';
    els.analyticsReadinessCopy.textContent = message;
    els.analyticsReadinessStats.innerHTML = `
      <span><strong>--</strong> skills</span>
      <span><strong>--</strong> courses</span>
      <span><strong>--</strong> synced jobs</span>
      <span><strong>--</strong> embeddings</span>
    `;
    if (els.embeddingStatusList) {
      els.embeddingStatusList.innerHTML = `<p class="panel-placeholder">${escapeHtml(message)}</p>`;
    }
  }

  function renderEmbeddingStatus(status) {
    if (!els.embeddingStatusList) return;
    const ready = Boolean(status.semantic_matching_ready);
    const rows = [
      ['Provider', status.embedding_provider || 'Unknown'],
      ['Semantic matching ready', ready ? 'Yes' : 'Fallback mode'],
      ['Local package available', status.local_embedding_package_available ? 'Yes' : 'No'],
      ['Hash fallback count', String(status.embedding_fallback_to_hash_count ?? 0)],
    ];
    els.embeddingStatusList.innerHTML = `
      <div class="diagnostic-badge ${ready ? 'ready' : 'warning'}">${ready ? 'Semantic ready' : 'Fallback active'}</div>
      <div class="diagnostic-list">
        ${rows.map(([label, value]) => `
          <div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
        `).join('')}
      </div>
      <p class="diagnostic-note">${escapeHtml(status.embedding_production_recommendation || 'Use a production semantic provider before relying on context scoring at scale.')}</p>
    `;
  }

  function renderCatalogQuality(quality) {
    if (!els.catalogQualityPanel) return;
    const metadata = quality.metadata_completeness || {};
    const actions = Array.isArray(quality.next_actions) ? quality.next_actions : [];
    els.catalogQualityPanel.innerHTML = `
      <div class="quality-score">
        <span>Quality score</span>
        <strong>${scorePercent(quality.quality_score)}</strong>
      </div>
      <div class="diagnostic-list">
        <div><span>Skills</span><strong>${escapeHtml(quality.skills_count ?? '--')}</strong></div>
        <div><span>Courses</span><strong>${escapeHtml(quality.courses_count ?? '--')}</strong></div>
        <div><span>Mapped courses</span><strong>${scorePercent(quality.mapped_course_ratio)}</strong></div>
        <div><span>Metadata</span><strong>${scorePercent(metadata.overall)}</strong></div>
      </div>
      <div class="next-action-list">
        ${(actions.length ? actions : ['Catalog diagnostics are ready.']).slice(0, 3).map((action) => `
          <p>${escapeHtml(action)}</p>
        `).join('')}
      </div>
    `;
  }

  async function runAnalysis(event) {
    event.preventDefault();
    await runAnalysisForCurrentSelection({ syncSkills: true });
  }

  async function runAnalysisForCurrentSelection({ syncSkills } = { syncSkills: true }) {
    const resumeId = els.resumeSelect.value;
    const targetRole = els.targetRoleSelect.value;
    if (!resumeId || !targetRole) return;

    els.runButton.disabled = true;
    setStatus('Analyzing your resume skills and comparing them with role requirements...');

    try {
      if (syncSkills) {
        await apiFetch(`/api/v1/capstone/resumes/${encodeURIComponent(resumeId)}/skills/sync`, {
          method: 'POST',
        });
      }
      await loadResumeSkillReview();
      const params = new URLSearchParams({ resume_id: resumeId, target_role: targetRole });
      const analysis = await apiFetch(`/api/v1/capstone/gap-analysis?${params.toString()}`);
      if (!analysis) return;
      state.latestAnalysis = analysis;
      renderAnalysis(analysis);
    } catch (error) {
      setStatus(error.message || 'Unable to run career analysis right now.', 'error');
    } finally {
      updateRunButtonState();
    }
  }

  function renderSkillReview(payload) {
    if (!els.skillReviewList || !els.skillReviewCounts) return;
    const skills = Array.isArray(payload?.skills) ? payload.skills : [];
    const counts = skills.reduce((acc, skill) => {
      const status = skill.status || 'detected';
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});

    els.skillReviewCounts.innerHTML = `
      <span><strong>${escapeHtml(counts.detected || 0)}</strong> detected</span>
      <span><strong>${escapeHtml(counts.confirmed || 0)}</strong> confirmed</span>
      <span><strong>${escapeHtml(counts.manual || 0)}</strong> manual</span>
      <span><strong>${escapeHtml(counts.rejected || 0)}</strong> rejected</span>
    `;

    if (!els.resumeSelect.value) {
      els.skillReviewList.innerHTML = '<p class="panel-placeholder">Select a resume to review detected skills.</p>';
      return;
    }

    if (!skills.length) {
      els.skillReviewList.innerHTML = '<p class="panel-placeholder">No skills detected yet. Run an analysis to sync this resume with the skill catalog.</p>';
      return;
    }

    const ordered = skills.slice().sort((a, b) => {
      const rank = { manual: 0, confirmed: 1, detected: 2, rejected: 3 };
      return (rank[a.status] ?? 2) - (rank[b.status] ?? 2)
        || String(a.display_name || '').localeCompare(String(b.display_name || ''));
    });

    els.skillReviewList.innerHTML = ordered.map((skill) => {
      const status = skill.status || 'detected';
      const isConfirmed = status === 'confirmed';
      const isRejected = status === 'rejected';
      const isManual = status === 'manual';
      return `
        <div class="skill-review-item ${escapeHtml(status)}" data-resume-skill-id="${escapeHtml(skill.resume_skill_id || '')}">
          <div class="skill-review-main">
            <span>${escapeHtml(status)}</span>
            <strong>${escapeHtml(skill.display_name)}</strong>
            <small>${escapeHtml(skill.evidence_text || skill.normalized_name || 'Catalog skill')}</small>
          </div>
          <div class="skill-review-actions">
            <button type="button" data-skill-action="confirmed" ${isConfirmed || isManual ? 'disabled' : ''}>Confirm</button>
            <button type="button" data-skill-action="rejected" ${isRejected || isManual ? 'disabled' : ''}>Reject</button>
            <button type="button" data-skill-action="delete">Remove</button>
          </div>
        </div>
      `;
    }).join('');
  }

  async function handleSkillReviewAction(event) {
    const button = event.target.closest('[data-skill-action]');
    if (!button || !els.resumeSelect.value) return;
    const item = button.closest('[data-resume-skill-id]');
    const resumeSkillId = item?.dataset.resumeSkillId;
    if (!resumeSkillId) return;

    const action = button.dataset.skillAction;
    button.disabled = true;

    try {
      if (action === 'delete') {
        const payload = await apiFetch(
          `/api/v1/capstone/resumes/${encodeURIComponent(els.resumeSelect.value)}/skills/${encodeURIComponent(resumeSkillId)}`,
          { method: 'DELETE' },
        );
        state.skillReview = payload;
        renderSkillReview(payload);
      } else {
        const payload = await apiFetch(
          `/api/v1/capstone/resumes/${encodeURIComponent(els.resumeSelect.value)}/skills/${encodeURIComponent(resumeSkillId)}`,
          {
            method: 'PATCH',
            body: JSON.stringify({ status: action }),
          },
        );
        state.skillReview = payload;
        renderSkillReview(payload);
      }

      if (state.latestAnalysis?.resume_id === els.resumeSelect.value) {
        await runAnalysisForCurrentSelection({ syncSkills: false });
      } else {
        setStatus('Resume skills updated.');
      }
    } catch (error) {
      setStatus(error.message || 'Unable to update resume skill.', 'error');
      await loadResumeSkillReview();
    }
  }

  async function addManualSkill(event) {
    event.preventDefault();
    if (!els.resumeSelect.value || !els.manualSkillInput.value.trim()) return;
    els.manualSkillButton.disabled = true;

    try {
      const payload = await apiFetch(`/api/v1/capstone/resumes/${encodeURIComponent(els.resumeSelect.value)}/skills/manual`, {
        method: 'POST',
        body: JSON.stringify({
          normalized_name: els.manualSkillInput.value.trim(),
          source_section: 'student_review',
          evidence_text: 'Added from Career Lab review.',
        }),
      });
      state.skillReview = payload;
      els.manualSkillInput.value = '';
      renderSkillReview(payload);
      if (state.latestAnalysis?.resume_id === els.resumeSelect.value) {
        await runAnalysisForCurrentSelection({ syncSkills: false });
      } else {
        setStatus('Manual skill added to this resume.');
      }
    } catch (error) {
      setStatus(error.message || 'Unable to add manual skill.', 'error');
    } finally {
      updateRunButtonState();
    }
  }

  function renderAnalysis(analysis) {
    if (analysis.status !== 'ok') {
      setStatus('This resume could not be analyzed yet.', 'error');
      return;
    }

    const missing = analysis.priority_missing_skills || analysis.missing_skills || [];
    const recommendations = analysis.recommended_courses || [];

    resetRouteDashboard();
    els.overallReadinessScore.textContent = scorePercent(analysis.overall_readiness_score);
    els.matchScore.textContent = scorePercent(analysis.match_score ?? analysis.coverage_ratio);
    els.contextSimilarityScore.textContent = scorePercent(analysis.context_similarity_score);
    els.contextMatchLevel.textContent = analysis.semantic_context_ready
      ? `${analysis.context_match_level || 'Context'} semantic match`
      : 'Semantic context in fallback';
    els.missingSkillsCount.textContent = String(missing.length);
    els.recommendedCourseCount.textContent = String(recommendations.length);
    els.requirementsSource.textContent = sourceLabel(analysis.requirements_source);
    els.semanticStatus.textContent = analysis.semantic_context_ready
      ? 'Semantic context active'
      : 'Hash/fallback mode';
    els.semanticMatchCount.textContent = String(analysis.semantic_match_count || 0);
    if (!analysis.required_skills?.length) {
      setStatus('The analytical catalog is not seeded yet for this role. Add starter skills or sync job postings to activate the lab.', 'error');
    } else {
      setStatus(`Analysis ready for ${analysis.target_role}. Review the gaps and turn them into a learning route.`);
    }

    renderSkillComparison(analysis);
    renderImprovements(analysis);
    renderInsights(analysis);
    renderMarketSignals(analysis);
    renderCourseRecommendations(analysis);
    drawRadar(analysis);
  }

  function renderSkillComparison(analysis) {
    const required = analysis.required_skills || [];
    const matchedIds = new Set((analysis.matched_required_skills || []).map((skill) => skill.skill_id));

    if (!required.length) {
      els.skillComparisonList.innerHTML = '<p class="panel-placeholder">No role requirements available yet.</p>';
      return;
    }

    els.skillComparisonList.innerHTML = required
      .slice()
      .sort((a, b) => Number(b.importance_score || 0) - Number(a.importance_score || 0))
      .slice(0, 10)
      .map((skill) => {
        const matched = matchedIds.has(skill.skill_id);
        const width = matched ? 100 : Math.max(12, clampPercent(Math.round(Number(skill.importance_score || 0.5) * 100)));
        const label = matched ? 'Matched' : 'Gap';
        return `
          <div class="skill-row ${matched ? 'matched' : 'missing'}">
            <div class="skill-row-top">
              <span>${escapeHtml(skill.display_name)}</span>
              <small>${label}</small>
            </div>
            <div class="skill-track"><span style="width:${width}%"></span></div>
          </div>
        `;
      }).join('');
  }

  function renderImprovements(analysis) {
    const missing = analysis.priority_missing_skills || analysis.missing_skills || [];
    if (!missing.length) {
      els.improvementList.innerHTML = '<p class="panel-placeholder">No major gaps found for this role. Keep strengthening your proof through projects and applications.</p>';
      return;
    }

    const sortedGaps = missing
      .slice()
      .sort((a, b) => Number(b.skill_gap_score || b.priority_score || b.importance_score || 0) - Number(a.skill_gap_score || a.priority_score || a.importance_score || 0));
    const maxGapScore = Math.max(...sortedGaps.map((skill) => Number(skill.skill_gap_score || skill.priority_score || 0)), 1);
    const courseBySkill = buildCourseLookupBySkill(analysis.recommended_courses || []);

    els.improvementList.innerHTML = sortedGaps.slice(0, 6).map((skill) => {
      const gapScore = Number(skill.skill_gap_score || skill.priority_score || skill.importance_score || 0);
      const gapWidth = clampPercent(Math.round((gapScore / maxGapScore) * 100));
      const course = courseBySkill.get(skill.skill_id);
      return `
        <div class="improvement-item">
          <div class="gap-score-top">
            <span>${escapeHtml(skill.priority_rank ? `Rank ${skill.priority_rank}` : skill.category || 'Skill gap')}</span>
            <strong>${escapeHtml(skill.display_name)}</strong>
            <b>${escapeHtml(scoreDecimal(gapScore))}</b>
          </div>
          <div class="gap-score-track" aria-hidden="true"><span style="width:${gapWidth}%"></span></div>
          <div class="gap-score-metrics">
            <small>Weight ${escapeHtml(scoreDecimal(skill.required_skill_weight ?? skill.importance_score))}</small>
            <small>Evidence ${escapeHtml(scorePercent(skill.student_skill_evidence || 0))}</small>
            <small>${escapeHtml(skill.market_demand_count ? `${skill.market_demand_count} postings` : sourceLabel(analysis.requirements_source))}</small>
          </div>
          <p>${escapeHtml(skill.reason || skill.evidence_text || 'Required by the selected role profile.')}</p>
          ${course ? `<p class="gap-course-link">Course match: ${escapeHtml(course.title)}</p>` : ''}
        </div>
      `;
    }).join('');
  }

  function buildCourseLookupBySkill(courses) {
    const lookup = new Map();
    courses.forEach((course) => {
      (course.skills_covered || []).forEach((skill) => {
        if (!lookup.has(skill.skill_id)) {
          lookup.set(skill.skill_id, course);
        }
      });
    });
    return lookup;
  }

  function renderInsights(analysis) {
    const insights = analysis.gap_insights || [];
    if (!els.insightsList) return;
    if (!insights.length) {
      els.insightsList.innerHTML = '<p class="panel-placeholder">No insights available yet. Run an analysis after the catalog has role requirements.</p>';
      return;
    }

    els.insightsList.innerHTML = insights.slice(0, 6).map((insight) => `
      <div class="insight-item ${escapeHtml(insight.severity || 'info')}">
        <span>${escapeHtml(insight.insight_type || 'Insight')}</span>
        <strong>${escapeHtml(insight.skill_name || severityLabel(insight.severity))}</strong>
        <p>${escapeHtml(insight.message)}</p>
      </div>
    `).join('');
  }

  function severityLabel(severity) {
    if (severity === 'positive') return 'Good signal';
    if (severity === 'high') return 'High priority';
    if (severity === 'medium') return 'Watch this';
    return 'Context';
  }

  function renderMarketSignals(analysis) {
    if (!els.marketSignalsList) return;
    const signals = analysis.market_signals || {};
    const skills = Array.isArray(signals.skills) ? signals.skills : [];
    const sourceCopy = sourceExplanation(signals.source || analysis.requirements_source);
    const syncedCount = Number(signals.synced_job_postings_count || 0);

    if (!skills.length) {
      els.marketSignalsList.innerHTML = `
        <div class="market-signal">
          <span>${escapeHtml(sourceLabel(signals.source || analysis.requirements_source))}</span>
          <strong>${syncedCount ? `${syncedCount} synced postings` : 'No market skills yet'}</strong>
          <p>${escapeHtml(sourceCopy)}</p>
        </div>
      `;
      return;
    }

    els.marketSignalsList.innerHTML = `
      <div class="market-signal">
        <span>${escapeHtml(sourceLabel(signals.source || analysis.requirements_source))}</span>
        <strong>${syncedCount ? `${syncedCount} synced postings` : 'Starter role profile'}</strong>
        <p>${escapeHtml(sourceCopy)}</p>
      </div>
      ${skills.slice(0, 5).map((skill) => `
        <div class="market-signal compact">
          <span>${scorePercent(skill.demand_score)} demand</span>
          <strong>${escapeHtml(skill.display_name)}</strong>
          <p>${escapeHtml(skill.job_posting_count || 0)} synced posting(s) mention this skill.</p>
        </div>
      `).join('')}
    `;
  }

  function renderCourseRecommendations(analysis) {
    const courses = analysis.recommended_courses || [];
    if (!courses.length) {
      els.courseRouteList.innerHTML = '<p class="panel-placeholder">No course recommendations yet. This usually means there are no mapped resources for the current gaps.</p>';
      return;
    }

    if (els.routeSummaryStrip) els.routeSummaryStrip.hidden = true;
    if (els.routeSummaryCopy) els.routeSummaryCopy.hidden = true;
    els.courseRouteList.innerHTML = courses.slice(0, 5).map((course, index) => {
      const covered = (course.skills_covered || []).map((skill) => skill.display_name).slice(0, 3).join(', ');
      const cost = formatMoney(course.cost, course.currency);
      const duration = formatHours(course.duration_hours);
      const resourceUrl = safeExternalUrl(course.url);
      const link = resourceUrl ? `<a href="${escapeHtml(resourceUrl)}" target="_blank" rel="noopener">Open resource</a>` : '';
      return `
        <div class="course-route-item">
          <span>Recommendation ${index + 1}</span>
          <strong>${escapeHtml(course.title)}</strong>
          <p>${escapeHtml(course.provider || 'Students Compass')} ${covered ? `covers ${escapeHtml(covered)}` : 'supports this learning route'}.</p>
          <div class="course-route-meta">
            <small>${escapeHtml(cost)}</small>
            <small>${escapeHtml(duration)}</small>
            <small>${escapeHtml(course.difficulty || 'Recommended')}</small>
          </div>
          ${link}
        </div>
      `;
    }).join('');
  }

  async function generateLearningRoute(event) {
    event.preventDefault();
    const resumeId = els.resumeSelect.value;
    const targetRole = els.targetRoleSelect.value;
    if (!resumeId || !targetRole) return;

    els.generateRouteButton.disabled = true;
    els.courseRouteList.innerHTML = '<p class="panel-placeholder">Optimizing a route across your budget, hours, and priority gaps...</p>';
    renderBaselineLoading();
    setStatus('Generating an optimized learning route...');

    const payload = {
      resume_id: resumeId,
      target_role: targetRole,
      budget: Number(els.routeBudget.value || 150),
      available_hours: Number(els.routeHours.value || 40),
      max_courses: Number(els.routeMaxCourses.value || 4),
    };

    try {
      const route = await apiFetch('/api/v1/capstone/learning-route/optimize', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!route) return;
      state.latestRoute = route;
      renderOptimizedRoute(route);
      renderDashboardSummary(route, null);
      await loadRouteRuns();
      await evaluateBaselines(payload, route);
      setStatus(`Learning route ready for ${route.target_role}.`);
    } catch (error) {
      els.courseRouteList.innerHTML = `<p class="panel-placeholder">Route optimization failed: ${escapeHtml(error.message || 'Request failed')}.</p>`;
      renderBaselineComparison(null);
      renderDashboardSummary(null, null);
      setStatus(error.message || 'Unable to generate learning route right now.', 'error');
    } finally {
      updateRunButtonState();
    }
  }

  function renderOptimizedRoute(route) {
    const courses = route.selected_courses || [];
    const remaining = route.remaining_gaps || [];

    if (els.routeSummaryStrip) {
      els.routeSummaryStrip.hidden = false;
      els.routeScoreBefore.textContent = scorePercent(route.match_score_before);
      els.routeScoreAfter.textContent = scorePercent(route.projected_match_score_after);
      els.routeTotalCost.textContent = formatMoney(route.total_cost);
      els.routeTotalHours.textContent = formatHours(route.total_hours);
    }

    if (els.routeSummaryCopy) {
      els.routeSummaryCopy.hidden = false;
      els.routeSummaryCopy.textContent = route.route_summary || 'Optimized route generated.';
    }

    if (!courses.length) {
      els.courseRouteList.innerHTML = `
        <div class="route-empty-state">
          <strong>No mapped courses found for these gaps yet.</strong>
          <p>The current catalog does not cover ${remaining.length ? 'these remaining gaps' : 'the missing gaps'} under your constraints.</p>
          ${remaining.length ? `
            <div class="chip-list">
              ${remaining.slice(0, 8).map((gap) => `<span>${escapeHtml(gap.display_name)}</span>`).join('')}
            </div>
          ` : ''}
        </div>
      `;
      return;
    }

    els.courseRouteList.innerHTML = courses
      .slice()
      .sort((a, b) => Number(a.sequence_order || 0) - Number(b.sequence_order || 0))
      .map((course, index) => {
        const order = course.sequence_order || index + 1;
        const covered = course.covered_priority_skills || [];
        const resourceUrl = safeExternalUrl(course.url);
        const link = resourceUrl ? `<a href="${escapeHtml(resourceUrl)}" target="_blank" rel="noopener">Open resource</a>` : '';
        return `
          <div class="course-route-item timeline-item">
            <span>Step ${escapeHtml(order)}</span>
            <strong>${escapeHtml(course.title)}</strong>
            <p>${escapeHtml(course.selection_reason || 'Selected because it covers priority gaps within your constraints.')}</p>
            <div class="course-route-meta">
              <small>${escapeHtml(course.provider || 'Students Compass')}</small>
              <small>${escapeHtml(formatMoney(course.cost, course.currency))}</small>
              <small>${escapeHtml(formatHours(course.duration_hours))}</small>
              <small>${escapeHtml(course.difficulty || 'Recommended')}</small>
            </div>
            ${covered.length ? `
              <div class="chip-list">
                ${covered.slice(0, 5).map((skill) => `<span>${escapeHtml(skill)}</span>`).join('')}
              </div>
            ` : ''}
            ${link}
          </div>
        `;
      }).join('');
  }

  async function evaluateBaselines(payload, route) {
    try {
      const evaluation = await apiFetch('/api/v1/capstone/learning-route/evaluate-baselines', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!evaluation) return;
      state.latestBaselineEvaluation = evaluation;
      renderBaselineComparison(evaluation);
      renderDashboardSummary(route, evaluation);
    } catch (error) {
      state.latestBaselineEvaluation = null;
      if (els.baselineSummary) {
        els.baselineSummary.innerHTML = `
          <p class="panel-placeholder error">Baseline comparison is unavailable: ${escapeHtml(error.message || 'Request failed')}.</p>
        `;
      }
      if (els.baselineMethodList) els.baselineMethodList.innerHTML = '';
      renderDashboardSummary(route, null);
    }
  }

  function renderBaselineLoading() {
    if (els.baselineSummary) {
      els.baselineSummary.innerHTML = '<p class="panel-placeholder">Comparing route methods under the same budget, hours, and course limits...</p>';
    }
    if (els.baselineMethodList) els.baselineMethodList.innerHTML = '';
  }

  function renderBaselineComparison(evaluation) {
    if (!els.baselineSummary || !els.baselineMethodList) return;
    if (!evaluation) {
      els.baselineSummary.innerHTML = '<p class="panel-placeholder">Generate a learning route to compare CP-SAT, heuristic, similarity, cost, rating, and random baselines.</p>';
      els.baselineMethodList.innerHTML = '';
      return;
    }

    const winner = evaluation.winner_summary || {};
    const methods = Array.isArray(evaluation.methods) ? evaluation.methods : [];
    const order = [
      'cp_sat_route_v1',
      'heuristic_route_v1',
      'similarity_only',
      'cheapest_feasible',
      'highest_rated_feasible',
      'random_feasible_seeded',
    ];
    const orderedMethods = methods.slice().sort((a, b) => {
      const aRank = order.indexOf(a.method);
      const bRank = order.indexOf(b.method);
      return (aRank === -1 ? 99 : aRank) - (bRank === -1 ? 99 : bRank);
    });

    els.baselineSummary.innerHTML = `
      <div class="baseline-winner">
        <span>Winner</span>
        <strong>${escapeHtml(methodLabel(winner.best_method))}</strong>
        <p>${escapeHtml(winner.summary || 'Baseline comparison completed.')}</p>
      </div>
    `;

    els.baselineMethodList.innerHTML = orderedMethods.map((method) => {
      const metrics = method.metrics || {};
      const isWinner = method.method === winner.best_method;
      return `
        <div class="baseline-method ${isWinner ? 'winner' : ''}">
          <div class="baseline-method-top">
            <span>${escapeHtml(isWinner ? 'Best method' : 'Method')}</span>
            <strong>${escapeHtml(methodLabel(method.method))}</strong>
            <small>${escapeHtml(method.solver_status || method.objective_version || 'Evaluated')}</small>
          </div>
          <div class="baseline-metrics">
            <div><span>Coverage</span><strong>${scorePercent(metrics.weighted_skill_coverage)}</strong></div>
            <div><span>Critical</span><strong>${scorePercent(metrics.critical_skill_coverage)}</strong></div>
            <div><span>Cost</span><strong>${escapeHtml(formatMoney(metrics.total_cost))}</strong></div>
            <div><span>Hours</span><strong>${escapeHtml(formatHours(metrics.total_hours))}</strong></div>
            <div><span>Courses</span><strong>${escapeHtml(metrics.selected_courses_count ?? 0)}</strong></div>
            <div><span>Redundancy</span><strong>${scorePercent(metrics.redundancy_rate)}</strong></div>
            <div><span>Gain</span><strong>${scorePercent(metrics.projected_readiness_gain)}</strong></div>
            <div><span>Runtime</span><strong>${escapeHtml(scoreDecimal(metrics.runtime_ms))}ms</strong></div>
          </div>
          <p>${escapeHtml(method.explanation || 'Comparison method evaluated under the same constraints.')}</p>
        </div>
      `;
    }).join('');
  }

  function methodLabel(method) {
    const labels = {
      cp_sat_route_v1: 'OR-Tools CP-SAT',
      heuristic_route_v1: 'MVP heuristic',
      similarity_only: 'Similarity only',
      cheapest_feasible: 'Cheapest feasible',
      highest_rated_feasible: 'Highest rated',
      random_feasible_seeded: 'Seeded random',
    };
    return labels[method] || method || '--';
  }

  function renderDashboardSummary(route, evaluation) {
    if (!els.dashboardSummary) return;
    const winner = evaluation?.winner_summary?.best_method;
    if (!route) {
      els.dashboardSummaryTitle.textContent = 'Optimize a route to complete your dashboard.';
      els.dashboardSummaryCopy.textContent = 'Your projected score, cost, hours, and baseline winner will appear here after route optimization.';
      els.summaryProjectedScore.textContent = '--';
      els.summaryTotalCost.textContent = '--';
      els.summaryTotalHours.textContent = '--';
      els.summaryBestBaseline.textContent = '--';
      return;
    }

    els.dashboardSummaryTitle.textContent = `Optimized route ready for ${route.target_role}.`;
    els.dashboardSummaryCopy.textContent = evaluation
      ? 'Dashboard complete: route optimization and baseline comparison are both available.'
      : 'Route optimization is available. Baseline comparison will appear when the evaluation finishes.';
    els.summaryProjectedScore.textContent = scorePercent(route.projected_match_score_after);
    els.summaryTotalCost.textContent = formatMoney(route.total_cost);
    els.summaryTotalHours.textContent = formatHours(route.total_hours);
    els.summaryBestBaseline.textContent = methodLabel(winner);
  }

  function resetRouteDashboard() {
    state.latestRoute = null;
    state.latestBaselineEvaluation = null;
    if (els.routeSummaryStrip) els.routeSummaryStrip.hidden = true;
    if (els.routeSummaryCopy) els.routeSummaryCopy.hidden = true;
    if (els.courseRouteList) {
      els.courseRouteList.innerHTML = '<p class="panel-placeholder">Generate a route to turn priority gaps into a timeline.</p>';
    }
    renderBaselineComparison(null);
    renderDashboardSummary(null, null);
  }

  function renderRouteHistory(runs) {
    if (!els.routeHistoryList) return;
    if (!runs.length) {
      els.routeHistoryList.innerHTML = '<p class="panel-placeholder">No route history yet. Generate a learning route to save your first run.</p>';
      return;
    }

    els.routeHistoryList.innerHTML = runs.map((run) => `
      <div class="route-history-item">
        <div class="route-history-top">
          <strong>${escapeHtml(run.target_role)}</strong>
          <span>${escapeHtml(formatDateTime(run.created_at))}</span>
        </div>
        <div class="route-history-metrics">
          <small>${scorePercent(run.match_score_before)} to ${scorePercent(run.projected_match_score_after)}</small>
          <small>${escapeHtml(formatMoney(run.total_cost))}</small>
          <small>${escapeHtml(formatHours(run.total_hours))}</small>
          <small>${escapeHtml(run.selected_courses_count || 0)} courses</small>
        </div>
        <p>${escapeHtml(run.route_summary || 'Route generated for this target role.')}</p>
      </div>
    `).join('');
  }

  function drawRadar(analysis) {
    const canvas = els.radar;
    if (!canvas || !canvas.getContext) return;

    const context = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2 + 8;
    const radius = Math.min(width, height) * 0.34;
    context.clearRect(0, 0, width, height);

    const required = (analysis?.required_skills || [])
      .slice()
      .sort((a, b) => Number(b.importance_score || 0) - Number(a.importance_score || 0))
      .slice(0, 8);
    const matchedIds = new Set((analysis?.matched_required_skills || []).map((skill) => skill.skill_id));

    const labels = required.length
      ? required.map((skill) => skill.display_name)
      : ['Python', 'SQL', 'Analytics', 'Communication', 'Projects', 'Excel'];
    const requiredValues = required.length
      ? required.map((skill) => Math.max(0.35, Number(skill.importance_score || 0.65)))
      : [0.86, 0.82, 0.72, 0.65, 0.58, 0.7];
    const currentValues = required.length
      ? required.map((skill) => matchedIds.has(skill.skill_id) ? 0.92 : 0.22)
      : [0.55, 0.4, 0.46, 0.72, 0.28, 0.62];

    const sides = labels.length;

    context.lineWidth = 1;
    context.strokeStyle = 'rgba(148, 163, 184, 0.38)';
    context.fillStyle = 'rgba(15, 23, 42, 0.68)';
    context.font = '600 12px Inter, system-ui, sans-serif';

    for (let ring = 1; ring <= 4; ring += 1) {
      drawPolygon(context, centerX, centerY, radius * (ring / 4), sides, null, 'rgba(148, 163, 184, 0.32)');
    }

    for (let i = 0; i < sides; i += 1) {
      const angle = angleForIndex(i, sides);
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius;
      context.beginPath();
      context.moveTo(centerX, centerY);
      context.lineTo(x, y);
      context.stroke();

      const labelX = centerX + Math.cos(angle) * (radius + 36);
      const labelY = centerY + Math.sin(angle) * (radius + 26);
      context.textAlign = labelX < centerX - 8 ? 'right' : labelX > centerX + 8 ? 'left' : 'center';
      context.textBaseline = labelY < centerY ? 'bottom' : 'top';
      context.fillText(shortLabel(labels[i]), labelX, labelY);
    }

    drawValuePolygon(context, centerX, centerY, radius, requiredValues, 'rgba(251, 113, 133, 0.18)', '#fb7185');
    drawValuePolygon(context, centerX, centerY, radius, currentValues, 'rgba(37, 99, 235, 0.18)', '#2563eb');
  }

  function angleForIndex(index, sides) {
    return (Math.PI * 2 * index / sides) - Math.PI / 2;
  }

  function drawPolygon(context, centerX, centerY, radius, sides, fillStyle, strokeStyle) {
    context.beginPath();
    for (let i = 0; i < sides; i += 1) {
      const angle = angleForIndex(i, sides);
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius;
      if (i === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
    context.closePath();
    if (fillStyle) {
      context.fillStyle = fillStyle;
      context.fill();
    }
    if (strokeStyle) {
      context.strokeStyle = strokeStyle;
      context.stroke();
    }
  }

  function drawValuePolygon(context, centerX, centerY, radius, values, fillStyle, strokeStyle) {
    context.beginPath();
    values.forEach((value, index) => {
      const angle = angleForIndex(index, values.length);
      const x = centerX + Math.cos(angle) * radius * value;
      const y = centerY + Math.sin(angle) * radius * value;
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.closePath();
    context.fillStyle = fillStyle;
    context.fill();
    context.lineWidth = 2.5;
    context.strokeStyle = strokeStyle;
    context.stroke();
  }

  function shortLabel(label) {
    const text = String(label || '');
    return text.length > 16 ? `${text.slice(0, 14)}...` : text;
  }

  document.addEventListener('DOMContentLoaded', async () => {
    bindElements();
    if (!els.form) return;

    drawRadar(null);
    els.form.addEventListener('submit', runAnalysis);
    if (els.routeForm) els.routeForm.addEventListener('submit', generateLearningRoute);
    if (els.uploadForm) els.uploadForm.addEventListener('submit', uploadResumeFromLab);
    if (els.uploadFileInput) {
      els.uploadFileInput.addEventListener('change', (event) => {
        setSelectedUploadFile(event.target.files?.[0]);
      });
    }
    if (els.uploadArea) {
      els.uploadArea.addEventListener('dragover', (event) => {
        event.preventDefault();
        els.uploadArea.classList.add('dragging');
      });
      els.uploadArea.addEventListener('dragleave', () => {
        els.uploadArea.classList.remove('dragging');
      });
      els.uploadArea.addEventListener('drop', (event) => {
        event.preventDefault();
        els.uploadArea.classList.remove('dragging');
        setSelectedUploadFile(event.dataTransfer?.files?.[0]);
      });
    }
    els.resumeSelect.addEventListener('change', async () => {
      state.latestAnalysis = null;
      resetRouteDashboard();
      updateRunButtonState();
      await loadResumeSkillReview();
    });
    els.targetRoleSelect.addEventListener('change', () => {
      state.latestAnalysis = null;
      resetRouteDashboard();
      updateRunButtonState();
    });
    if (els.skillReviewList) els.skillReviewList.addEventListener('click', handleSkillReviewAction);
    if (els.manualSkillForm) els.manualSkillForm.addEventListener('submit', addManualSkill);

    try {
      await Promise.all([
        loadAnalyticsStatus(),
        loadCatalogQuality(),
        loadRouteRuns(),
        loadTargetRoles(),
        loadResumes(),
      ]);
    } catch (error) {
      setStatus(error.message || 'Unable to load resumes.', 'error');
      els.resumeSelect.innerHTML = '<option value="">Could not load resumes</option>';
      updateRunButtonState();
    }
  });
})();

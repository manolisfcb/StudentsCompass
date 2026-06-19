(function () {
  const state = {
    resumes: [],
    roles: [],
    latestAnalysis: null,
    analyticsStatus: null,
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
    els.analyticsReadiness = document.querySelector('.analytics-readiness');
    els.analyticsReadinessBadge = document.getElementById('analyticsReadinessBadge');
    els.analyticsReadinessTitle = document.getElementById('analyticsReadinessTitle');
    els.analyticsReadinessCopy = document.getElementById('analyticsReadinessCopy');
    els.analyticsReadinessStats = document.getElementById('analyticsReadinessStats');
    els.matchScore = document.getElementById('matchScore');
    els.missingSkillsCount = document.getElementById('missingSkillsCount');
    els.recommendedCourseCount = document.getElementById('recommendedCourseCount');
    els.requirementsSource = document.getElementById('requirementsSource');
    els.skillComparisonList = document.getElementById('skillComparisonList');
    els.improvementList = document.getElementById('improvementList');
    els.courseRouteList = document.getElementById('courseRouteList');
    els.marketSourceCopy = document.getElementById('marketSourceCopy');
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

  async function apiFetch(url, options) {
    const response = await fetch(url, {
      credentials: 'include',
      cache: 'no-store',
      ...(options || {}),
    });
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
  }

  async function loadResumes() {
    updateRunButtonState();
    const resumes = await apiFetch('/api/v1/profile/cv');
    if (!resumes) return;

    state.resumes = Array.isArray(resumes) ? resumes : [];
    if (!state.resumes.length) {
      els.resumeSelect.innerHTML = '<option value="">No resume uploaded</option>';
      els.empty.hidden = false;
      setStatus('Upload a CV first so the Career Lab can analyze your current skill profile.');
      drawRadar(null);
      updateRunButtonState();
      return;
    }

    els.empty.hidden = true;
    els.resumeSelect.innerHTML = state.resumes.map((resume, index) => {
      const label = `${resume.original_filename || 'Resume'} - ${formatDate(resume.created_at)}`;
      return `<option value="${escapeHtml(resume.id)}" ${index === 0 ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    updateRunButtonState();
    setStatus('Ready. Pick a target role and run your gap analysis.');
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
  }

  async function runAnalysis(event) {
    event.preventDefault();
    const resumeId = els.resumeSelect.value;
    const targetRole = els.targetRoleSelect.value;
    if (!resumeId || !targetRole) return;

    els.runButton.disabled = true;
    setStatus('Analyzing your resume skills and comparing them with role requirements...');

    try {
      await apiFetch(`/api/v1/capstone/resumes/${encodeURIComponent(resumeId)}/skills/sync`, {
        method: 'POST',
      });
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

  function renderAnalysis(analysis) {
    if (analysis.status !== 'ok') {
      setStatus('This resume could not be analyzed yet.', 'error');
      return;
    }

    const matchScore = Math.round((Number(analysis.coverage_ratio) || 0) * 100);
    const missing = analysis.missing_skills || [];
    const recommendations = analysis.recommended_courses || [];

    els.matchScore.textContent = `${matchScore}%`;
    els.missingSkillsCount.textContent = String(missing.length);
    els.recommendedCourseCount.textContent = String(recommendations.length);
    els.requirementsSource.textContent = sourceLabel(analysis.requirements_source);
    els.marketSourceCopy.textContent = sourceExplanation(analysis.requirements_source);

    if (!analysis.required_skills?.length) {
      setStatus('The analytical catalog is not seeded yet for this role. Add starter skills or sync job postings to activate the lab.', 'error');
    } else {
      setStatus(`Analysis ready for ${analysis.target_role}. Review the gaps and turn them into a learning route.`);
    }

    renderSkillComparison(analysis);
    renderImprovements(analysis);
    renderCourses(analysis);
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
    const missing = analysis.missing_skills || [];
    if (!missing.length) {
      els.improvementList.innerHTML = '<p class="panel-placeholder">No major gaps found for this role. Keep strengthening your proof through projects and applications.</p>';
      return;
    }

    els.improvementList.innerHTML = missing
      .slice()
      .sort((a, b) => Number(b.importance_score || 0) - Number(a.importance_score || 0))
      .slice(0, 6)
      .map((skill) => `
        <div class="improvement-item">
          <span>${escapeHtml(skill.category || 'Skill gap')}</span>
          <strong>${escapeHtml(skill.display_name)}</strong>
          <p>${escapeHtml(skill.evidence_text || 'Required by the selected role profile.')}</p>
        </div>
      `).join('');
  }

  function renderCourses(analysis) {
    const courses = analysis.recommended_courses || [];
    if (!courses.length) {
      els.courseRouteList.innerHTML = '<p class="panel-placeholder">No course recommendations yet. This usually means there are no mapped resources for the current gaps.</p>';
      return;
    }

    els.courseRouteList.innerHTML = courses.slice(0, 5).map((course, index) => {
      const covered = (course.skills_covered || []).map((skill) => skill.display_name).slice(0, 3).join(', ');
      const cost = course.cost ? `${course.currency || 'CAD'} ${Number(course.cost).toFixed(0)}` : 'Free or internal';
      const duration = course.duration_hours ? `${Number(course.duration_hours).toFixed(0)}h` : 'Self-paced';
      const resourceUrl = safeExternalUrl(course.url);
      const link = resourceUrl ? `<a href="${escapeHtml(resourceUrl)}" target="_blank" rel="noopener">Open resource</a>` : '';
      return `
        <div class="course-route-item">
          <span>Step ${index + 1}</span>
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
    els.resumeSelect.addEventListener('change', updateRunButtonState);
    els.targetRoleSelect.addEventListener('change', updateRunButtonState);

    try {
      await Promise.all([loadAnalyticsStatus(), loadTargetRoles(), loadResumes()]);
    } catch (error) {
      setStatus(error.message || 'Unable to load resumes.', 'error');
      els.resumeSelect.innerHTML = '<option value="">Could not load resumes</option>';
      updateRunButtonState();
    }
  });
})();

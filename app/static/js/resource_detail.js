(function () {
  const raw = document.getElementById('resource-payload-json');
  if (!raw) return;

  const payload = JSON.parse(raw.textContent || '{}');
  const lessonTitle = document.getElementById('lesson-title');
  const lessonMeta = document.getElementById('lesson-meta');
  const lessonContent = document.getElementById('lesson-content');
  const contentPanel = document.querySelector('.content-panel');
  const lessonButtons = Array.from(document.querySelectorAll('[data-lesson-id]'));
  const moduleButtons = Array.from(document.querySelectorAll('[data-module-toggle]'));
  const moduleSections = Array.from(document.querySelectorAll('[data-module]'));
  const moduleProgressLabels = Array.from(document.querySelectorAll('[data-module-progress]'));
  const resourceProgressValue = document.getElementById('resource-progress-value');
  const searchInput = document.getElementById('lesson-search');
  const searchEmpty = document.getElementById('lesson-search-empty');
  const completedLessonIds = new Set((payload.completed_lesson_ids || []).map((id) => String(id)));
  const progressRequestsInFlight = new Set();
  let currentLessonId = null;

  function sanitizeHtml(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html || '', 'text/html');
    doc.querySelectorAll('script,style,iframe,object,embed').forEach((el) => el.remove());

    doc.querySelectorAll('*').forEach((el) => {
      Array.from(el.attributes).forEach((attr) => {
        const name = attr.name.toLowerCase();
        const value = attr.value.trim().toLowerCase();
        if (name.startsWith('on')) el.removeAttribute(attr.name);
        if ((name === 'href' || name === 'src') && value.startsWith('javascript:')) {
          el.removeAttribute(attr.name);
        }
      });
    });

    return doc.body.innerHTML;
  }

  function normalize(value) {
    return (value || '').toString().trim().toLowerCase();
  }

  function escapeHtml(value) {
    return (value || '')
      .toString()
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function readableType(type) {
    const key = normalize(type);
    if (key === 'video_url') return 'Video lesson';
    if (key === 'external_link') return 'External resource';
    if (key === 'resume_upload') return 'Resume challenge';
    if (key === 'html') return 'HTML lesson';
    return 'Text lesson';
  }

  function isSafeHttpUrl(url) {
    if (!url) return false;
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  }

  function toEmbedUrl(url) {
    if (!isSafeHttpUrl(url)) return null;
    try {
      const parsed = new URL(url);
      const host = parsed.hostname.toLowerCase();

      if (host === 'youtu.be') {
        const id = parsed.pathname.replace('/', '');
        return id ? `https://www.youtube.com/embed/${id}` : url;
      }

      if (host.includes('youtube.com')) {
        if (parsed.pathname.startsWith('/embed/')) return url;
        const id = parsed.searchParams.get('v');
        return id ? `https://www.youtube.com/embed/${id}` : url;
      }

      if (host.includes('vimeo.com')) {
        const id = parsed.pathname.split('/').filter(Boolean).pop();
        return id ? `https://player.vimeo.com/video/${id}` : url;
      }

      return url;
    } catch {
      return url;
    }
  }

  function parseVideoContent(rawContent) {
    const raw = (rawContent || '').trim();
    if (!raw) return { url: '', description: '' };

    if (raw.startsWith('{') && raw.endsWith('}')) {
      try {
        const parsed = JSON.parse(raw);
        return {
          url: (parsed.url || '').toString().trim(),
          description: (parsed.description || '').toString().trim(),
        };
      } catch {
        // Fallback to line-based parsing when invalid JSON.
      }
    }

    const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const firstUrlLine = lines.find((line) => isSafeHttpUrl(line)) || '';
    if (!firstUrlLine) return { url: raw, description: '' };

    const description = lines.filter((line) => line !== firstUrlLine).join(' ');
    return { url: firstUrlLine, description };
  }

  function parseResumeUploadContent(rawContent) {
    const text = (rawContent || '').trim();
    if (!text) {
      return 'Upload your resume after completing previous lessons. We will review it in the next phase.';
    }
    return text;
  }

  function getLessonContextById(lessonId) {
    for (const module of payload.modules || []) {
      const found = (module.lessons || []).find((lesson) => lesson.id === lessonId);
      if (found) return { lesson: found, module };
    }
    return null;
  }

  function updateLessonUrl(lessonId) {
    if (!lessonId) return;
    const url = new URL(window.location.href);
    url.searchParams.set('lesson', lessonId);
    window.history.replaceState({}, '', url.toString());
  }

  function countModuleProgress(moduleId) {
    const module = (payload.modules || []).find((item) => item.id === moduleId);
    if (!module) return { completed: 0, total: 0, percent: 0 };

    const lessons = module.lessons || [];
    const total = lessons.length;
    let completed = 0;
    lessons.forEach((lesson) => {
      if (completedLessonIds.has(String(lesson.id))) completed += 1;
    });
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    return { completed, total, percent };
  }

  function countResourceProgress() {
    const total = Number(payload.lesson_count || 0);
    const completed = completedLessonIds.size;
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    return { completed, total, percent };
  }

  function refreshProgressUI() {
    lessonButtons.forEach((btn) => {
      const lessonId = String(btn.dataset.lessonId || '');
      const isCompleted = completedLessonIds.has(lessonId);
      btn.classList.toggle('is-completed', isCompleted);

      const icon = btn.querySelector('.course-lesson-icon');
      if (icon) icon.textContent = isCompleted ? '✅' : '📄';
    });

    moduleProgressLabels.forEach((label) => {
      const moduleId = String(label.dataset.moduleProgress || '');
      const stats = countModuleProgress(moduleId);
      label.textContent = `${stats.completed}/${stats.total} Completed`;
    });

    if (resourceProgressValue) {
      const stats = countResourceProgress();
      resourceProgressValue.textContent = `${stats.percent}%`;
    }
  }

  function applyProgressPayload(progressPayload) {
    if (!progressPayload || !Array.isArray(progressPayload.completed_lesson_ids)) return;

    completedLessonIds.clear();
    progressPayload.completed_lesson_ids.forEach((id) => completedLessonIds.add(String(id)));
    refreshProgressUI();
  }

  async function markLessonCompleted(lessonId) {
    const id = String(lessonId || '');
    if (!id || completedLessonIds.has(id) || progressRequestsInFlight.has(id)) return;

    progressRequestsInFlight.add(id);
    try {
      const response = await fetch(`/api/v1/resources/lessons/${id}/progress`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: true }),
      });
      if (!response.ok) return;
      const progressPayload = await response.json();
      applyProgressPayload(progressPayload);
    } catch (error) {
      console.error('Failed to persist lesson progress', error);
    } finally {
      progressRequestsInFlight.delete(id);
    }
  }

  function getPrerequisiteProgress(currentLessonId) {
    const prerequisiteIds = [];
    (payload.modules || []).forEach((module) => {
      (module.lessons || []).forEach((lesson) => {
        if (String(lesson.id) !== String(currentLessonId)) {
          prerequisiteIds.push(String(lesson.id));
        }
      });
    });

    const completed = prerequisiteIds.filter((id) => completedLessonIds.has(id)).length;
    const total = prerequisiteIds.length;
    return {
      completed,
      total,
      unlocked: completed >= total,
    };
  }

  async function fetchCourseAuditAttempts() {
    const response = await fetch('/api/v1/profile/cv/course-audit-attempts', { credentials: 'include' });
    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return null;
    }
    if (!response.ok) throw new Error('Failed to load daily attempts');
    return response.json();
  }

  async function fetchResourceProgress() {
    if (!payload?.id) return null;
    const response = await fetch(`/api/v1/resources/${payload.id}/progress`, {
      credentials: 'include',
    });
    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return null;
    }
    if (!response.ok) return null;
    return response.json();
  }

  function formatFileSize(bytes) {
    if (!Number.isFinite(bytes)) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  function renderResumeUploadLesson(lesson) {
    let maxAttemptsPerDay = 3;
    const prerequisite = getPrerequisiteProgress(lesson.id);
    const helperText = parseResumeUploadContent(lesson.content);

    lessonContent.innerHTML = `
      <section class="resume-upload-lesson">
        <div class="resume-upload-head">
          <h4>Final Resume Submission Challenge</h4>
          <p id="resume-upload-helper"></p>
        </div>

        <div class="resume-upload-meta">
          <span class="resume-upload-pill">Daily limit: <strong id="resume-upload-attempts">0/${maxAttemptsPerDay}</strong></span>
          <span class="resume-upload-pill">Format: PDF, DOCX</span>
        </div>

        <div id="resume-upload-lock" class="resume-upload-lock" hidden></div>

        <div id="resume-upload-widget" class="resume-upload-widget">
          <label id="resume-upload-dropzone" class="resume-upload-dropzone" for="resume-upload-input">
            <span class="resume-upload-icon">📤</span>
            <strong>Click to upload or drag and drop</strong>
            <small>Max size 5MB</small>
          </label>
          <input id="resume-upload-input" type="file" accept=".pdf,.docx" hidden />

          <div id="resume-upload-preview" class="resume-upload-preview" hidden>
            <div>
              <strong id="resume-upload-filename"></strong>
              <small id="resume-upload-filesize"></small>
            </div>
            <button id="resume-upload-remove" class="resume-upload-remove-btn" type="button">Remove</button>
          </div>

          <button id="resume-upload-submit" class="resume-upload-submit-btn" type="button" disabled>
            Upload resume
          </button>
          <div id="resume-upload-analyzing" class="resume-upload-analyzing" hidden aria-live="polite">
            <span class="resume-upload-spinner" aria-hidden="true"></span>
            <span>Compass esta analizando tu resume...</span>
          </div>
          <p id="resume-upload-status" class="resume-upload-status"></p>
          <section id="resume-upload-feedback" class="resume-audit-feedback" hidden></section>
        </div>
      </section>
    `;

    const helper = document.getElementById('resume-upload-helper');
    const attemptsNode = document.getElementById('resume-upload-attempts');
    const lockNode = document.getElementById('resume-upload-lock');
    const widgetNode = document.getElementById('resume-upload-widget');
    const dropzone = document.getElementById('resume-upload-dropzone');
    const input = document.getElementById('resume-upload-input');
    const preview = document.getElementById('resume-upload-preview');
    const fileName = document.getElementById('resume-upload-filename');
    const fileSize = document.getElementById('resume-upload-filesize');
    const removeBtn = document.getElementById('resume-upload-remove');
    const submitBtn = document.getElementById('resume-upload-submit');
    const analyzingNode = document.getElementById('resume-upload-analyzing');
    const statusNode = document.getElementById('resume-upload-status');
    const feedbackNode = document.getElementById('resume-upload-feedback');

    if (helper) helper.textContent = helperText;
    if (analyzingNode) analyzingNode.hidden = true;

    let selectedFile = null;
    let attemptsToday = 0;
    let isAnalyzing = false;
    const defaultSubmitLabel = submitBtn?.textContent?.trim() || 'Upload resume';

    function setStatus(message, tone = 'neutral') {
      if (!statusNode) return;
      statusNode.textContent = message;
      statusNode.dataset.tone = tone;
    }

    function setAttempts(count) {
      attemptsToday = count;
      if (attemptsNode) attemptsNode.textContent = `${attemptsToday}/${maxAttemptsPerDay}`;
    }

    function setDailyLimit(limit) {
      const parsed = Number(limit);
      if (!Number.isFinite(parsed) || parsed <= 0) return;
      maxAttemptsPerDay = Math.round(parsed);
      if (attemptsNode) attemptsNode.textContent = `${attemptsToday}/${maxAttemptsPerDay}`;
    }

    function disableWidget(reason) {
      widgetNode?.classList.add('is-disabled');
      submitBtn.disabled = true;
      input.disabled = true;
      if (removeBtn) removeBtn.disabled = true;
      if (reason) setStatus(reason, 'warning');
    }

    function enableWidget() {
      if (isAnalyzing) return;
      widgetNode?.classList.remove('is-disabled');
      input.disabled = false;
      if (removeBtn) removeBtn.disabled = false;
      submitBtn.disabled = !selectedFile;
    }

    function setAnalyzing(active) {
      isAnalyzing = Boolean(active);
      if (analyzingNode) analyzingNode.hidden = !isAnalyzing;
      if (widgetNode) widgetNode.classList.toggle('is-analyzing', isAnalyzing);
      if (dropzone) dropzone.classList.toggle('is-disabled', isAnalyzing);
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = isAnalyzing ? 'Analizando...' : defaultSubmitLabel;
      }
      if (input) input.disabled = isAnalyzing;
      if (removeBtn) removeBtn.disabled = isAnalyzing;
    }

    function renderAuditFeedback(result) {
      if (!feedbackNode) return;
      const score = Number(result?.overall_score || 0);
      const confidence = Number(result?.llm_confidence || 0);
      const passed = Boolean(result?.pass_status);
      const reason = (result?.reason_for_score || '').trim();
      const weaknesses = Array.isArray(result?.main_weaknesses) ? result.main_weaknesses : [];
      const improvements = Array.isArray(result?.improvements) ? result.improvements : [];
      const scores = result?.scores && typeof result.scores === 'object' ? result.scores : {};

      const scoreLabels = [
        ['ats', 'ATS Compatibility'],
        ['canadian_format', 'Canadian Format'],
        ['keywords', 'Keyword Strength'],
        ['achievements', 'Achievement Quality'],
        ['readability', 'Recruiter Readability'],
        ['ai_risk', 'Human Tone (AI Risk)'],
        ['differentiation', 'Differentiation'],
        ['formatting', 'Formatting'],
      ];

      const scoreRows = scoreLabels.map(([key, label]) => {
        const value = Number(scores[key] || 0);
        const safeValue = Number.isFinite(value) ? Math.max(0, Math.min(10, value)) : 0;
        const percent = Math.round((safeValue / 10) * 100);
        return `
          <div class="resume-audit-score-row">
            <div class="resume-audit-score-head">
              <span>${escapeHtml(label)}</span>
              <strong>${safeValue.toFixed(1)}/10</strong>
            </div>
            <div class="resume-audit-score-track">
              <span class="resume-audit-score-fill" style="width:${percent}%"></span>
            </div>
          </div>
        `;
      }).join('');

      const weaknessItems = (weaknesses.length ? weaknesses : ['No major weaknesses were listed.'])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join('');

      const improvementItems = (improvements.length ? improvements : ['No specific improvements were listed.'])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join('');

      feedbackNode.innerHTML = `
        <div class="resume-audit-summary ${passed ? 'is-pass' : 'is-fail'}">
          <p class="resume-audit-kicker">${passed ? 'PASS' : 'NOT PASSING YET'}</p>
          <h5>${score.toFixed(1)}/10</h5>
          <p>Confidence: ${confidence.toFixed(2)} · Target: 8.0+</p>
        </div>

        <div class="resume-audit-card">
          <h6>Why this score</h6>
          <p>${escapeHtml(reason || 'No detailed explanation provided by the evaluator.')}</p>
        </div>

        <div class="resume-audit-grid">
          <div class="resume-audit-card">
            <h6>What is hurting your score</h6>
            <ul>${weaknessItems}</ul>
          </div>
          <div class="resume-audit-card">
            <h6>How to push this to 10/10</h6>
            <ul>${improvementItems}</ul>
          </div>
        </div>

        <div class="resume-audit-card">
          <h6>Score breakdown</h6>
          <div class="resume-audit-score-list">${scoreRows}</div>
        </div>
      `;
      feedbackNode.hidden = false;
    }

    function resetFileSelection() {
      selectedFile = null;
      if (input) input.value = '';
      if (preview) preview.hidden = true;
      submitBtn.disabled = true;
    }

    function handleSelectedFile(file) {
      const validTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ];
      const maxSize = 5 * 1024 * 1024;

      if (!validTypes.includes(file.type)) {
        setStatus('Only PDF or DOCX files are allowed.', 'error');
        return;
      }
      if (file.size > maxSize) {
        setStatus('File size must be under 5MB.', 'error');
        return;
      }

      selectedFile = file;
      if (fileName) fileName.textContent = file.name;
      if (fileSize) fileSize.textContent = formatFileSize(file.size);
      if (preview) preview.hidden = false;
      submitBtn.disabled = false;
      setStatus('');
    }

    if (!prerequisite.unlocked) {
      if (lockNode) {
        lockNode.hidden = false;
        lockNode.textContent = `Complete previous lessons first (${prerequisite.completed}/${prerequisite.total}) to unlock this upload challenge.`;
      }
      disableWidget('Upload is locked until you finish earlier lessons.');
      return;
    }

    fetchCourseAuditAttempts()
      .then((meta) => {
        const count = Number(meta?.attempts_today || 0);
        setDailyLimit(meta?.daily_limit);
        setAttempts(count);
        if (count >= maxAttemptsPerDay) {
          disableWidget(`You reached the ${maxAttemptsPerDay} uploads/day limit for this challenge.`);
        } else {
          enableWidget();
        }
      })
      .catch(() => {
        setStatus('Could not load upload attempts right now.', 'warning');
      });

    dropzone?.addEventListener('dragover', (event) => {
      event.preventDefault();
      if (input.disabled) return;
      dropzone.classList.add('is-dragover');
    });

    dropzone?.addEventListener('dragleave', () => {
      dropzone.classList.remove('is-dragover');
    });

    dropzone?.addEventListener('drop', (event) => {
      event.preventDefault();
      dropzone.classList.remove('is-dragover');
      if (input.disabled) return;
      const files = event.dataTransfer?.files;
      if (files?.length) handleSelectedFile(files[0]);
    });

    input?.addEventListener('change', (event) => {
      const files = event.target?.files;
      if (files?.length) handleSelectedFile(files[0]);
    });

    removeBtn?.addEventListener('click', resetFileSelection);

    submitBtn?.addEventListener('click', async () => {
      if (!selectedFile || submitBtn.disabled) return;
      if (attemptsToday >= maxAttemptsPerDay) {
        disableWidget(`You reached the ${maxAttemptsPerDay} uploads/day limit for this challenge.`);
        return;
      }

      submitBtn.disabled = true;
      setAnalyzing(true);
      setStatus('Compass esta analizando tu resume...', 'neutral');
      if (feedbackNode) feedbackNode.hidden = true;

      const formData = new FormData();
      formData.append('cv', selectedFile);

      try {
        const response = await fetch('/api/v1/profile/cv/course-audit-upload', {
          method: 'POST',
          credentials: 'include',
          body: formData,
        });

        if (response.status === 401 || response.status === 403) {
          setAnalyzing(false);
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          throw new Error('Upload failed');
        }

        const result = await response.json();
        const score = Number(result?.overall_score || 0);
        const confidence = Number(result?.llm_confidence || 0);
        const passed = Boolean(result?.pass_status);

        const nextAttempts = attemptsToday + 1;
        const persistedAttempts = Number(result?.attempts_today || nextAttempts);
        setDailyLimit(result?.daily_limit);
        setAttempts(persistedAttempts);
        renderAuditFeedback(result);
        if (passed) {
          setStatus(`Great work. Score: ${score.toFixed(1)}/10 (confidence ${confidence.toFixed(2)}). You passed this challenge.`, 'success');
          const updatedProgress = await fetchResourceProgress();
          applyProgressPayload(updatedProgress);
        } else {
          setStatus(
            `Score: ${score.toFixed(1)}/10 (confidence ${confidence.toFixed(2)}). You need at least 8.0. Review the feedback below and try again.`,
            'warning',
          );
        }
        resetFileSelection();
        setAnalyzing(false);

        if (persistedAttempts >= maxAttemptsPerDay) {
          disableWidget(`You reached the ${maxAttemptsPerDay} uploads/day limit for this challenge.`);
        } else {
          enableWidget();
        }
      } catch (error) {
        setAnalyzing(false);
        setStatus('Upload failed. Please try again.', 'error');
        submitBtn.disabled = false;
      }
    });
  }

  function firstLessonId() {
    for (const module of payload.modules || []) {
      if (module.lessons && module.lessons.length) return module.lessons[0].id;
    }
    return null;
  }

  function isLessonVisible(lessonId) {
    const button = lessonButtons.find((btn) => btn.dataset.lessonId === lessonId);
    if (!button) return false;
    const row = button.closest('[data-lesson-item]');
    if (!row || row.hidden) return false;
    const lessonGroup = row.closest('[data-module-lessons]');
    if (lessonGroup && lessonGroup.hidden) return false;
    const section = row.closest('[data-module]');
    if (section && section.hidden) return false;
    return true;
  }

  function firstVisibleLessonId() {
    const firstVisible = lessonButtons.find((btn) => {
      const row = btn.closest('[data-lesson-item]');
      if (!row || row.hidden) return false;
      const lessonGroup = row.closest('[data-module-lessons]');
      if (lessonGroup && lessonGroup.hidden) return false;
      const section = row.closest('[data-module]');
      return !(section && section.hidden);
    });
    return firstVisible ? firstVisible.dataset.lessonId : null;
  }

  function renderLesson(lessonId) {
    const context = getLessonContextById(lessonId) || getLessonContextById(firstVisibleLessonId()) || getLessonContextById(firstLessonId());
    if (!context) {
      lessonTitle.textContent = 'No lesson available';
      lessonMeta.textContent = '';
      lessonContent.innerHTML = '<p>There are no lessons published for this resource yet.</p>';
      currentLessonId = null;
      return;
    }

    const { lesson, module } = context;
    currentLessonId = lesson.id;

    lessonButtons.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.lessonId === lesson.id);
    });

    lessonTitle.textContent = lesson.title;
    const metaParts = [`Module ${module.position}: ${module.title}`];
    if (lesson.reading_time_minutes) {
      metaParts.push(`${lesson.reading_time_minutes} min read`);
    } else {
      metaParts.push(readableType(lesson.content_type));
    }
    lessonMeta.textContent = metaParts.join(' · ');
    updateLessonUrl(lesson.id);

    if (lesson.content_type === 'resume_upload') {
      renderResumeUploadLesson(lesson);
      return;
    }

    markLessonCompleted(lesson.id);

    if (lesson.content_type === 'video_url') {
      const parsedVideo = parseVideoContent(lesson.content);
      const embedUrl = toEmbedUrl(parsedVideo.url);
      if (!embedUrl) {
        lessonContent.textContent = 'This video URL is not valid.';
        return;
      }
      const descriptionHtml = parsedVideo.description
        ? `<p class=\"lesson-video-note\">${parsedVideo.description}</p>`
        : '';
      const directLinkHtml = isSafeHttpUrl(parsedVideo.url)
        ? `<p><a class=\"open-resource\" href=\"${parsedVideo.url}\" target=\"_blank\" rel=\"noopener noreferrer\">Open video in YouTube</a></p>`
        : '';
      lessonContent.innerHTML = `${descriptionHtml}<div class=\"video-wrap\"><iframe src=\"${embedUrl}\" allowfullscreen loading=\"lazy\" referrerpolicy=\"strict-origin-when-cross-origin\"></iframe></div>${directLinkHtml}`;
      return;
    }

    if (lesson.content_type === 'external_link') {
      if (isSafeHttpUrl(lesson.content)) {
        lessonContent.innerHTML = `<p>This lesson opens an external resource.</p><p><a class=\"open-resource\" href=\"${lesson.content}\" target=\"_blank\" rel=\"noopener noreferrer\">Open resource</a></p>`;
      } else {
        lessonContent.textContent = lesson.content || 'External link unavailable.';
      }
      return;
    }

    if (lesson.content_type === 'html') {
      lessonContent.innerHTML = sanitizeHtml(lesson.content);
    } else {
      lessonContent.textContent = lesson.content;
    }
  }

  lessonButtons.forEach((btn) => {
    btn.addEventListener('click', () => renderLesson(btn.dataset.lessonId));
  });

  moduleButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const moduleId = btn.dataset.moduleToggle;
      const wrap = document.querySelector(`[data-module-lessons=\"${moduleId}\"]`);
      if (!wrap) return;
      const isCollapsed = wrap.hidden;
      wrap.hidden = !isCollapsed;
      btn.classList.toggle('is-collapsed', !isCollapsed);
      btn.setAttribute('aria-expanded', isCollapsed ? 'true' : 'false');
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const query = normalize(searchInput.value);
      let visibleCount = 0;

      moduleSections.forEach((section) => {
        const rows = Array.from(section.querySelectorAll('[data-lesson-item]'));
        const toggleBtn = section.querySelector('[data-module-toggle]');
        const lessonGroup = section.querySelector('[data-module-lessons]');
        let moduleHasVisibleLesson = false;

        rows.forEach((row) => {
          const title = normalize(row.dataset.lessonTitle);
          const module = normalize(row.dataset.moduleTitle);
          const matches = !query || title.includes(query) || module.includes(query);
          row.hidden = !matches;
          if (matches) {
            moduleHasVisibleLesson = true;
            visibleCount += 1;
          }
        });

        section.hidden = !moduleHasVisibleLesson;

        if (query && moduleHasVisibleLesson && lessonGroup) {
          lessonGroup.hidden = false;
        }
        if (toggleBtn && lessonGroup) {
          toggleBtn.classList.toggle('is-collapsed', lessonGroup.hidden);
          toggleBtn.setAttribute('aria-expanded', lessonGroup.hidden ? 'false' : 'true');
        }
      });

      if (searchEmpty) {
        searchEmpty.hidden = visibleCount > 0;
      }

      if (currentLessonId && isLessonVisible(currentLessonId)) return;
      renderLesson(firstVisibleLessonId());
    });
  }

  refreshProgressUI();
  renderLesson(payload.selected_lesson_id || firstLessonId());
})();

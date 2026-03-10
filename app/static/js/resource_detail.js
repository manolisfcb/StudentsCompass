(function () {
  const raw = document.getElementById('resource-payload-json');
  if (!raw) return;

  const payload = JSON.parse(raw.textContent || '{}');
  const lessonTitle = document.getElementById('lesson-title');
  const lessonMeta = document.getElementById('lesson-meta');
  const lessonContent = document.getElementById('lesson-content');
  const lessonActionBar = document.getElementById('lesson-action-bar');
  const lessonCompleteButton = document.getElementById('lesson-complete-btn');
  const lessonActionNote = document.getElementById('lesson-action-note');
  const lessonStepPill = document.getElementById('lesson-step-pill');
  const lessonProgressPill = document.getElementById('lesson-progress-pill');
  const courseOutline = document.querySelector('.course-outline');
  const outlineScrollHint = document.getElementById('course-outline-scroll-hint');
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

  function orderedLessonIds() {
    const ids = [];
    (payload.modules || []).forEach((module) => {
      (module.lessons || []).forEach((lesson) => ids.push(String(lesson.id)));
    });
    return ids;
  }

  function getLessonSequence(lessonId) {
    const ids = orderedLessonIds();
    const currentId = String(lessonId || '');
    const index = ids.findIndex((id) => id === currentId);
    return {
      ids,
      index,
      current: index >= 0 ? ids[index] : null,
      next: index >= 0 ? (ids[index + 1] || null) : null,
      total: ids.length,
    };
  }

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
    if (key === 'pdf_url') return 'PDF resource';
    if (key === 'ppt_url') return 'Slides resource';
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

  function getStructuredLessonContent(lesson) {
    const payload = lesson && typeof lesson.content_payload === 'object' && lesson.content_payload
      ? lesson.content_payload
      : null;
    const hasPayload = Boolean(payload && Object.keys(payload).length);
    const payloadBody = hasPayload && typeof payload.body === 'string' ? payload.body.trim() : '';
    const payloadNotes = hasPayload && typeof payload.notes === 'string' ? payload.notes.trim() : '';
    const payloadVideoUrl = hasPayload && typeof payload.video_url === 'string' ? payload.video_url.trim() : '';
    const payloadResourceUrl = hasPayload && typeof payload.resource_url === 'string' ? payload.resource_url.trim() : '';

    const explicitVideoUrl = typeof lesson.video_url === 'string' ? lesson.video_url.trim() : '';
    const explicitResourceUrl = typeof lesson.resource_url === 'string' ? lesson.resource_url.trim() : '';
    const explicitNotes = typeof lesson.notes === 'string' ? lesson.notes.trim() : '';
    const legacyContent = typeof lesson.content === 'string' ? lesson.content.trim() : '';

    return {
      hasPayload,
      videoUrl: explicitVideoUrl || payloadVideoUrl,
      resourceUrl: explicitResourceUrl || payloadResourceUrl,
      notes: explicitNotes || payloadNotes,
      body: hasPayload ? payloadBody : legacyContent,
      legacyContent,
    };
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
      if (lessonProgressPill) lessonProgressPill.textContent = `Progress ${stats.percent}%`;
    }
  }

  function applyProgressPayload(progressPayload) {
    if (!progressPayload || !Array.isArray(progressPayload.completed_lesson_ids)) return;

    completedLessonIds.clear();
    progressPayload.completed_lesson_ids.forEach((id) => completedLessonIds.add(String(id)));
    refreshProgressUI();
    if (currentLessonId) {
      const context = getLessonContextById(String(currentLessonId));
      if (context) renderLessonActionBar(context.lesson);
    }
  }

  async function markLessonCompleted(lessonId) {
    const id = String(lessonId || '');
    if (!id) return false;
    if (completedLessonIds.has(id)) return true;
    if (progressRequestsInFlight.has(id)) return false;

    progressRequestsInFlight.add(id);
    try {
      const response = await fetch(`/api/v1/resources/lessons/${id}/progress`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: true }),
      });
      if (!response.ok) return false;
      const progressPayload = await response.json();
      applyProgressPayload(progressPayload);
      return true;
    } catch (error) {
      console.error('Failed to persist lesson progress', error);
      return false;
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
    const structured = getStructuredLessonContent(lesson);
    const helperText = parseResumeUploadContent(structured.body || structured.notes || structured.legacyContent);

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

    function getTimeUntilNextUtcDayLabel() {
      const now = new Date();
      const nextUtcMidnight = Date.UTC(
        now.getUTCFullYear(),
        now.getUTCMonth(),
        now.getUTCDate() + 1,
        0,
        0,
        0,
      );
      const diffMs = Math.max(0, nextUtcMidnight - now.getTime());
      const totalMinutes = Math.ceil(diffMs / 60000);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      if (hours <= 0) return `${minutes}m`;
      if (minutes <= 0) return `${hours}h`;
      return `${hours}h ${minutes}m`;
    }

    function limitReachedMessage() {
      return `You reached the ${maxAttemptsPerDay} uploads/day limit for this challenge. Try again in ${getTimeUntilNextUtcDayLabel()}.`;
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
          disableWidget(limitReachedMessage());
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
        disableWidget(limitReachedMessage());
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
          let errorDetail = '';
          try {
            const errorPayload = await response.json();
            if (typeof errorPayload?.detail === 'string') {
              errorDetail = errorPayload.detail.trim();
            }
          } catch {
            // Keep fallback message below when response body is not JSON.
          }

          if (response.status === 429) {
            const retryMessage = errorDetail || limitReachedMessage();
            disableWidget(retryMessage);
            setAnalyzing(false);
            return;
          }

          throw new Error(errorDetail || 'Upload failed. Please try again.');
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
          disableWidget(limitReachedMessage());
        } else {
          enableWidget();
        }
      } catch (error) {
        setAnalyzing(false);
        const message = error instanceof Error && error.message
          ? error.message
          : 'Upload failed. Please try again.';
        setStatus(message, 'error');
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

  function updateOutlineScrollHint() {
    if (!courseOutline || !outlineScrollHint) return;
    const hasOverflow = courseOutline.scrollHeight > courseOutline.clientHeight + 8;
    const nearBottom = courseOutline.scrollTop + courseOutline.clientHeight >= courseOutline.scrollHeight - 8;
    outlineScrollHint.hidden = !hasOverflow || nearBottom;
  }

  function renderLessonActionBar(lesson) {
    if (!lessonActionBar || !lessonCompleteButton || !lessonActionNote) return;
    const lessonId = String(lesson?.id || '');
    const isResumeUpload = normalize(lesson?.content_type) === 'resume_upload';
    if (!lessonId || isResumeUpload) {
      lessonActionBar.hidden = true;
      return;
    }

    const sequence = getLessonSequence(lessonId);
    const isCompleted = completedLessonIds.has(lessonId);
    lessonActionBar.hidden = false;
    lessonCompleteButton.disabled = false;

    if (isCompleted) {
      if (sequence.next) {
        lessonCompleteButton.textContent = 'Next lesson';
        lessonActionNote.textContent = 'Great. This lesson is already completed.';
      } else {
        lessonCompleteButton.textContent = 'Course completed';
        lessonActionNote.textContent = 'You finished all lessons in this course.';
        lessonCompleteButton.disabled = true;
      }
      return;
    }

    lessonCompleteButton.textContent = 'Mark as complete';
    lessonActionNote.textContent = 'Progress updates when you mark this lesson as complete.';
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
    const sequence = getLessonSequence(lesson.id);

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
    if (lessonStepPill) {
      const position = sequence.index >= 0 ? sequence.index + 1 : 0;
      lessonStepPill.textContent = `Lesson ${position} of ${sequence.total}`;
    }
    updateLessonUrl(lesson.id);
    renderLessonActionBar(lesson);

    if (lesson.content_type === 'resume_upload') {
      renderResumeUploadLesson(lesson);
      return;
    }

    if (lesson.content_type === 'video_url') {
      const structured = getStructuredLessonContent(lesson);
      const parsedVideo = structured.videoUrl
        ? {
            url: structured.videoUrl,
            description: structured.notes || structured.body || '',
          }
        : parseVideoContent(lesson.content);
      const embedUrl = toEmbedUrl(parsedVideo.url);
      if (!embedUrl) {
        lessonContent.textContent = 'This video URL is not valid.';
        return;
      }
      const descriptionHtml = parsedVideo.description
        ? `<p class=\"lesson-video-note\">${parsedVideo.description}</p>`
        : '';
      lessonContent.innerHTML = `${descriptionHtml}<div class=\"video-wrap\"><iframe src=\"${embedUrl}\" allowfullscreen loading=\"lazy\" referrerpolicy=\"strict-origin-when-cross-origin\"></iframe></div>`;
      return;
    }

    if (lesson.content_type === 'external_link' || lesson.content_type === 'pdf_url' || lesson.content_type === 'ppt_url') {
      const structured = getStructuredLessonContent(lesson);
      const linkUrl = structured.resourceUrl || (isSafeHttpUrl(structured.legacyContent) ? structured.legacyContent : '');
      const noteHtml = structured.notes
        ? `<p class=\"lesson-video-note\">${escapeHtml(structured.notes)}</p>`
        : '';
      if (isSafeHttpUrl(linkUrl)) {
        lessonContent.innerHTML = `${noteHtml}<p>This lesson opens an external resource.</p><p><a class=\"open-resource\" href=\"${linkUrl}\" target=\"_blank\" rel=\"noopener noreferrer\">Open resource</a></p>`;
      } else {
        lessonContent.textContent = structured.legacyContent || 'External link unavailable.';
      }
      return;
    }

    if (lesson.content_type === 'html') {
      const structured = getStructuredLessonContent(lesson);
      const body = structured.body || structured.legacyContent;
      lessonContent.innerHTML = sanitizeHtml(body);
    } else {
      const structured = getStructuredLessonContent(lesson);
      lessonContent.textContent = structured.body || structured.legacyContent;
    }
  }

  lessonButtons.forEach((btn) => {
    btn.addEventListener('click', () => renderLesson(btn.dataset.lessonId));
  });

  lessonCompleteButton?.addEventListener('click', async () => {
    if (!currentLessonId) return;
    const sequence = getLessonSequence(currentLessonId);
    const alreadyCompleted = completedLessonIds.has(String(currentLessonId));

    if (alreadyCompleted) {
      if (sequence.next) renderLesson(sequence.next);
      return;
    }

    lessonCompleteButton.disabled = true;
    const completed = await markLessonCompleted(currentLessonId);
    lessonCompleteButton.disabled = false;
    if (!completed) return;

    renderLesson(currentLessonId);
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
      updateOutlineScrollHint();
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

      updateOutlineScrollHint();
      if (currentLessonId && isLessonVisible(currentLessonId)) return;
      renderLesson(firstVisibleLessonId());
    });
  }

  outlineScrollHint?.addEventListener('click', () => {
    if (!courseOutline) return;
    courseOutline.scrollBy({ top: 240, behavior: 'smooth' });
  });
  courseOutline?.addEventListener('scroll', updateOutlineScrollHint);
  window.addEventListener('resize', updateOutlineScrollHint);

  refreshProgressUI();
  renderLesson(payload.selected_lesson_id || firstLessonId());
  updateOutlineScrollHint();
})();

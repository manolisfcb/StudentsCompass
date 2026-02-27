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
  const linkLikeTypes = new Set(['external_link', 'document_url']);
  const resourceId = payload.id || null;
  const resourceApiBase = '/api/v1/resources';
  let enrollmentPromise = null;
  let isEnrolled = false;

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

  function toSafeUrl(rawUrl) {
    if (typeof rawUrl === 'string' && rawUrl.startsWith('/')) {
      return rawUrl;
    }
    try {
      const parsed = new URL(rawUrl);
      if (!['http:', 'https:'].includes(parsed.protocol)) return null;
      return parsed.toString();
    } catch {
      return null;
    }
  }

  function updateLessonUrl(lessonId) {
    const url = new URL(window.location.href);
    url.searchParams.set('lesson', lessonId);
    window.history.replaceState({}, '', url.toString());
  }

  async function ensureEnrollment() {
    if (!resourceId) return false;
    if (isEnrolled) return true;
    if (enrollmentPromise) return enrollmentPromise;

    enrollmentPromise = fetch(`${resourceApiBase}/${resourceId}/enroll`, {
      method: 'POST',
      credentials: 'include',
    })
      .then((res) => {
        if (res.ok) {
          isEnrolled = true;
          return true;
        }
        return false;
      })
      .catch(() => false)
      .finally(() => {
        enrollmentPromise = null;
      });

    return enrollmentPromise;
  }

  async function trackLessonOpen(lessonId) {
    if (!resourceId || !lessonId) return;
    await ensureEnrollment();
    fetch(`${resourceApiBase}/${resourceId}/lessons/${lessonId}/open`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
  }

  function isEmbeddedVideoProvider(url) {
    try {
      const host = new URL(url).hostname.toLowerCase();
      return host.includes('youtube.com') || host.includes('youtu.be') || host.includes('vimeo.com');
    } catch {
      return false;
    }
  }

  function toVideoEmbedUrl(url) {
    try {
      const parsed = new URL(url);
      const host = parsed.hostname.toLowerCase();

      if (host.includes('youtu.be')) {
        const id = parsed.pathname.replace('/', '');
        return id ? `https://www.youtube.com/embed/${id}` : url;
      }

      if (host.includes('youtube.com')) {
        const watchId = parsed.searchParams.get('v');
        if (watchId) return `https://www.youtube.com/embed/${watchId}`;
        if (parsed.pathname.startsWith('/shorts/')) {
          const shortsId = parsed.pathname.split('/shorts/')[1];
          if (shortsId) return `https://www.youtube.com/embed/${shortsId}`;
        }
      }

      if (host.includes('vimeo.com')) {
        const segments = parsed.pathname.split('/').filter(Boolean);
        const videoId = segments[0];
        if (videoId) return `https://player.vimeo.com/video/${videoId}`;
      }
    } catch {
      return url;
    }

    return url;
  }

  function renderInvalidUrl() {
    lessonContent.innerHTML = '<p>This resource URL is invalid or not supported.</p>';
  }

  function setMediaLayoutMode(enabled) {
    if (!contentPanel) return;
    contentPanel.classList.toggle('full-media', enabled);
  }

  function renderVideo(url) {
    if (isEmbeddedVideoProvider(url)) {
      const embedUrl = toVideoEmbedUrl(url);
      lessonContent.innerHTML = `<div class=\"video-wrap\"><iframe src=\"${embedUrl}\" allowfullscreen loading=\"lazy\"></iframe></div><p class=\"lesson-link-note\"><a class=\"open-resource\" href=\"${url}\" target=\"_blank\" rel=\"noopener noreferrer\">Open video in new tab</a></p>`;
      return;
    }
    lessonContent.innerHTML = `<div class=\"video-wrap\"><video controls preload=\"metadata\"><source src=\"${url}\"></video></div><p class=\"lesson-link-note\"><a class=\"open-resource\" href=\"${url}\" target=\"_blank\" rel=\"noopener noreferrer\">Open video file</a></p>`;
  }

  function renderPdf(url) {
    lessonContent.innerHTML = `<div class=\"doc-frame-wrap\"><iframe src=\"${url}\" loading=\"lazy\" title=\"PDF preview\"></iframe></div><p class=\"lesson-link-note\"><a class=\"open-resource\" href=\"${url}\" target=\"_blank\" rel=\"noopener noreferrer\">Open PDF</a></p>`;
  }

  function renderPpt(url) {
    if (url.startsWith('/')) {
      lessonContent.innerHTML = `<div class=\"doc-frame-wrap\"><iframe src=\"${url}\" loading=\"lazy\" title=\"PPT preview\"></iframe></div><p class=\"lesson-link-note\"><a class=\"open-resource\" href=\"${url}\" target=\"_blank\" rel=\"noopener noreferrer\">Open PPT/PPTX</a></p>`;
      return;
    }
    const officeViewerUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(url)}`;
    lessonContent.innerHTML = `<div class=\"doc-frame-wrap\"><iframe src=\"${officeViewerUrl}\" loading=\"lazy\" title=\"PPT preview\"></iframe></div><p class=\"lesson-link-note\"><a class=\"open-resource\" href=\"${url}\" target=\"_blank\" rel=\"noopener noreferrer\">Open PPT/PPTX</a></p>`;
  }

  function getLessonById(lessonId) {
    for (const module of payload.modules || []) {
      const found = (module.lessons || []).find((lesson) => lesson.id === lessonId);
      if (found) return found;
    }
    return null;
  }

  function firstLessonId() {
    for (const module of payload.modules || []) {
      if (module.lessons && module.lessons.length) return module.lessons[0].id;
    }
    return null;
  }

  function renderLesson(lessonId) {
    const lesson = getLessonById(lessonId) || getLessonById(firstLessonId());
    if (!lesson) {
      lessonTitle.textContent = 'No lesson available';
      lessonMeta.textContent = '';
      lessonContent.innerHTML = '<p>There are no lessons published for this resource yet.</p>';
      return;
    }

    lessonButtons.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.lessonId === lesson.id);
    });

    lessonTitle.textContent = lesson.title;
    lessonMeta.textContent = lesson.reading_time_minutes
      ? `${lesson.reading_time_minutes} min read`
      : 'Lesson content';
    void trackLessonOpen(lesson.id);

    setMediaLayoutMode(false);

    const safeUrl = toSafeUrl(lesson.content);

    if (lesson.content_type === 'video_url') {
      setMediaLayoutMode(true);
      if (!safeUrl) {
        renderInvalidUrl();
      } else {
        renderVideo(safeUrl);
      }
      updateLessonUrl(lesson.id);
      return;
    }

    if (lesson.content_type === 'pdf_url') {
      setMediaLayoutMode(true);
      if (!safeUrl) {
        renderInvalidUrl();
      } else {
        renderPdf(safeUrl);
      }
      updateLessonUrl(lesson.id);
      return;
    }

    if (lesson.content_type === 'ppt_url') {
      setMediaLayoutMode(true);
      if (!safeUrl) {
        renderInvalidUrl();
      } else {
        renderPpt(safeUrl);
      }
      updateLessonUrl(lesson.id);
      return;
    }

    if (linkLikeTypes.has(lesson.content_type)) {
      if (!safeUrl) {
        renderInvalidUrl();
      } else {
        const safe = sanitizeHtml(lesson.content);
        lessonContent.innerHTML = `<p>${safe}</p><p class=\"lesson-link-note\"><a class=\"open-resource\" href=\"${safeUrl}\" target=\"_blank\" rel=\"noopener noreferrer\">Open resource</a></p>`;
      }
      updateLessonUrl(lesson.id);
      return;
    }

    if (lesson.content_type === 'html') {
      lessonContent.innerHTML = sanitizeHtml(lesson.content);
    } else {
      lessonContent.textContent = lesson.content;
    }

    updateLessonUrl(lesson.id);
  }

  lessonButtons.forEach((btn) => {
    btn.addEventListener('click', () => renderLesson(btn.dataset.lessonId));
  });

  moduleButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const moduleId = btn.dataset.moduleToggle;
      const wrap = document.querySelector(`[data-module-lessons=\"${moduleId}\"]`);
      if (!wrap) return;
      const current = wrap.style.display !== 'none';
      wrap.style.display = current ? 'none' : '';
    });
  });

  void ensureEnrollment();
  renderLesson(payload.selected_lesson_id || firstLessonId());
})();

(function () {
  const raw = document.getElementById('resource-payload-json');
  if (!raw) return;

  const payload = JSON.parse(raw.textContent || '{}');
  const lessonTitle = document.getElementById('lesson-title');
  const lessonMeta = document.getElementById('lesson-meta');
  const lessonContent = document.getElementById('lesson-content');
  const lessonButtons = Array.from(document.querySelectorAll('[data-lesson-id]'));
  const moduleButtons = Array.from(document.querySelectorAll('[data-module-toggle]'));
  const moduleSections = Array.from(document.querySelectorAll('[data-module]'));
  const searchInput = document.getElementById('lesson-search');
  const searchEmpty = document.getElementById('lesson-search-empty');
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

  function readableType(type) {
    const key = normalize(type);
    if (key === 'video_url') return 'Video lesson';
    if (key === 'external_link') return 'External resource';
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

  function getLessonContextById(lessonId) {
    for (const module of payload.modules || []) {
      const found = (module.lessons || []).find((lesson) => lesson.id === lessonId);
      if (found) return { lesson: found, module };
    }
    return null;
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

    const url = new URL(window.location.href);
    url.searchParams.set('lesson', lesson.id);
    window.history.replaceState({}, '', url.toString());
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

  renderLesson(payload.selected_lesson_id || firstLessonId());
})();

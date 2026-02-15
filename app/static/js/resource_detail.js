(function () {
  const raw = document.getElementById('resource-payload-json');
  if (!raw) return;

  const payload = JSON.parse(raw.textContent || '{}');
  const lessonTitle = document.getElementById('lesson-title');
  const lessonMeta = document.getElementById('lesson-meta');
  const lessonContent = document.getElementById('lesson-content');
  const lessonButtons = Array.from(document.querySelectorAll('[data-lesson-id]'));
  const moduleButtons = Array.from(document.querySelectorAll('[data-module-toggle]'));

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

    if (lesson.content_type === 'video_url') {
      lessonContent.innerHTML = `<div class=\"video-wrap\"><iframe src=\"${lesson.content}\" allowfullscreen loading=\"lazy\"></iframe></div>`;
      return;
    }

    if (lesson.content_type === 'external_link') {
      const safe = sanitizeHtml(lesson.content);
      lessonContent.innerHTML = `<p>${safe}</p><p><a class=\"open-resource\" href=\"${lesson.content}\" target=\"_blank\" rel=\"noopener noreferrer\">Open</a></p>`;
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
      const current = wrap.style.display !== 'none';
      wrap.style.display = current ? 'none' : '';
    });
  });

  renderLesson(payload.selected_lesson_id || firstLessonId());
})();

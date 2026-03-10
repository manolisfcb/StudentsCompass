/* ================================================================
       Community Feed — JS
       ================================================================ */

    /* ── Helpers ──────────────────────────────────────────────── */
    function escapeHtml(str) {
      const d = document.createElement('div');
      d.textContent = str ?? '';
      return d.innerHTML;
    }

    function timeAgo(iso) {
      const diff = Date.now() - new Date(iso).getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1)  return 'Just now';
      if (mins < 60) return `${mins} min ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h ago`;
      const days = Math.floor(hrs / 24);
      if (days < 7) return `${days}d ago`;
      return new Date(iso).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function initials(name) {
      return name.split(' ').filter(Boolean).map(w => w[0]).join('').toUpperCase().slice(0, 2);
    }

    async function apiFetch(url, opts = {}) {
      return fetch(url, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
        ...opts,
      });
    }

    let toastTimer;
    function showToast(msg, isError = false) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast' + (isError ? ' error' : '');
      requestAnimationFrame(() => t.classList.add('show'));
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
    }

    /* ── Get community ID from URL ───────────────────────────── */
    const pathParts = window.location.pathname.split('/');
    const COMMUNITY_ID = pathParts[pathParts.length - 1];

    /* ── DOM refs ─────────────────────────────────────────────── */
    const $loading     = document.getElementById('loading');
    const $gate        = document.getElementById('gate');
    const $feedWrap    = document.getElementById('feed-wrapper');
    const $bannerIcon  = document.getElementById('banner-icon');
    const $bannerName  = document.getElementById('banner-name');
    const $bannerDesc  = document.getElementById('banner-desc');
    const $bannerMemb  = document.getElementById('banner-members');
    const $bannerStat  = document.getElementById('banner-status');
    const $bannerTags  = document.getElementById('banner-tags');
    const $sideAbout   = document.getElementById('sidebar-about');
    const $sideTags    = document.getElementById('sidebar-tags');
    const $bannerJoin  = document.getElementById('banner-join-btn');
    const $bannerLeave = document.getElementById('banner-leave-btn');
    const $gateJoinBtn = document.getElementById('gate-join-btn');
    const $feedLayout  = document.getElementById('feed-layout');
    const $composer    = document.getElementById('composer');
    const $compTitle   = document.getElementById('compose-title');
    const $compBody    = document.getElementById('compose-body');
    const $compSubmit  = document.getElementById('compose-submit');
    const $feedList    = document.getElementById('feed-list');
    const $feedEmpty   = document.getElementById('feed-empty');

    let communityData = null;
    let isMember = false;

    /* ── Init ────────────────────────────────────────────────── */
    async function init() {
      try {
        /* 1) Load community info */
        const cRes = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}`);
        if (cRes.status === 401) { window.location.href = '/login'; return; }
        if (!cRes.ok) { showToast('Community not found', true); return; }
        communityData = await cRes.json();

        /* 2) Check membership */
        const mRes = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}/membership`);
        const mData = mRes.ok ? await mRes.json() : { is_member: false };
        isMember = mData.is_member;

        $loading.style.display = 'none';
        renderBanner();
        updateMembershipUI();

        $feedWrap.style.display = 'block';
        if (isMember) {
          await loadFeed();
        }

      } catch (err) {
        console.error(err);
        showToast('Error loading community', true);
      }
    }

    /* ── Render banner ───────────────────────────────────────── */
    function renderBanner() {
      const c = communityData;
      document.title = `${c.name} - StudentsCompass`;
      $bannerIcon.textContent = c.icon || '👥';
      $bannerName.textContent = c.name;
      $bannerDesc.textContent = c.description || '';
      $bannerMemb.querySelector('span').textContent = `${c.member_count ?? 0} members`;
      $bannerStat.textContent = c.activity_status || 'Active';

      const tagsHtml = (c.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
      $bannerTags.innerHTML = tagsHtml;

      /* Sidebar */
      $sideAbout.textContent = c.description || 'No description available.';
      $sideTags.innerHTML = tagsHtml || '<span style="color:#94A3B8;font-size:.85rem;">No tags</span>';
    }

    /* ── Membership UI ─────────────────────────────────────── */
    function updateMembershipUI() {
      if (isMember) {
        $bannerJoin.style.display = 'none';
        $bannerLeave.style.display = 'inline-flex';
        $composer.style.display = '';
        $gate.style.display = 'none';
        $feedLayout.style.display = '';
        /* hide leave for creator */
        if (communityData && communityData.created_by === getCurrentUserId()) {
          $bannerLeave.style.display = 'none';
        }
      } else {
        $bannerJoin.style.display = 'inline-flex';
        $bannerLeave.style.display = 'none';
        $composer.style.display = 'none';
        $feedEmpty.style.display = 'none';
        $feedList.innerHTML = '';
        $feedLayout.style.display = 'none';
        $gate.style.display = 'block';
      }
    }

    function getCurrentUserId() {
      /* Best-effort: read from cookie or return empty so comparison fails */
      return null;
    }

    /* Banner: Join */
    $bannerJoin.addEventListener('click', async () => {
      $bannerJoin.disabled = true;
      $bannerJoin.textContent = 'Joining…';
      const res = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}/join`, { method: 'POST' });
      if (!res.ok && res.status !== 409) {
        showToast('Could not join the community', true);
        $bannerJoin.disabled = false;
        $bannerJoin.textContent = 'Join';
        return;
      }
      isMember = true;
      $bannerJoin.disabled = false;
      $bannerJoin.textContent = 'Join';
      /* Refresh community */
      const cRes = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}`);
      if (cRes.ok) { communityData = await cRes.json(); renderBanner(); }
      updateMembershipUI();
      showToast('You joined the community!');
      await loadFeed();
    });

    $gateJoinBtn?.addEventListener('click', () => {
      $bannerJoin.click();
    });

    /* Banner: Leave */
    $bannerLeave.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to leave this community?')) return;
      $bannerLeave.disabled = true;
      $bannerLeave.textContent = 'Leaving…';
      const res = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}/leave`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || 'Could not leave the community', true);
        $bannerLeave.disabled = false;
        $bannerLeave.textContent = 'Leave';
        return;
      }
      isMember = false;
      $bannerLeave.disabled = false;
      $bannerLeave.textContent = 'Leave';
      /* Refresh community */
      const cRes = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}`);
      if (cRes.ok) { communityData = await cRes.json(); renderBanner(); }
      updateMembershipUI();
      showToast('You left the community');
    });

    /* ── Load feed ───────────────────────────────────────────── */
    async function loadFeed() {
      $feedList.innerHTML = '';
      $feedEmpty.style.display = 'none';

      const res = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}/posts/enriched`);
      if (!res.ok) { showToast('Could not load posts', true); return; }

      const posts = await res.json();
      if (!posts.length) { $feedEmpty.style.display = 'block'; return; }
      posts.forEach(p => $feedList.appendChild(createPostCard(p)));
    }

    /* ── Create post card ────────────────────────────────────── */
    function createPostCard(post) {
      const card = document.createElement('article');
      card.className = 'post-card';
      card.setAttribute('aria-label', `Post by ${escapeHtml(post.author_name)}`);

      const avatar = initials(post.author_name);
      const liked = post.liked_by_me;

      card.innerHTML = `
        <div class="post-card__body">
          <div class="post-author">
            <div class="post-avatar">${escapeHtml(avatar)}</div>
            <div class="post-author-info">
              <h4>${escapeHtml(post.author_name)}</h4>
              <time datetime="${post.created_at}">${timeAgo(post.created_at)}</time>
            </div>
          </div>
          ${post.title ? `<h3 class="post-title">${escapeHtml(post.title)}</h3>` : ''}
          <p class="post-content">${escapeHtml(post.content)}</p>
        </div>
        <div class="post-counters">
          <span data-like-count>${post.like_count} likes</span>
          <span data-comment-count>${post.comment_count} comments</span>
        </div>
        <div class="post-actions">
          <button class="btn-ghost${liked ? ' active' : ''}" data-like aria-pressed="${liked}">
            <svg xmlns="http://www.w3.org/2000/svg" fill="${liked ? 'currentColor' : 'none'}" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6.633 10.5c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3.06a.5.5 0 01.5-.55 2.234 2.234 0 012.013 1.262c.349.694.523 1.46.523 2.227 0 .753-.14 1.46-.397 2.106a.5.5 0 00.471.682h3.036c1.067 0 1.935.866 1.869 1.932a18.27 18.27 0 01-2.639 8.29c-.267.434-.713.692-1.2.692H13.5m-5.25 0A2.25 2.25 0 016 19.5H4.5A2.25 2.25 0 012.25 17.25V11.25A2.25 2.25 0 014.5 9h1.086c.53 0 1.04-.211 1.414-.586L8.25 7.17"/>
            </svg>
            Like
          </button>
          <button class="btn-ghost" data-toggle-comments>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>
            </svg>
            Comment
          </button>
        </div>
        <div class="comments-section" data-comments-section>
          <div data-comments-list></div>
          <form class="comment-form" data-comment-form>
            <input type="text" placeholder="Write a comment…" required aria-label="Write a comment">
            <button type="submit">Send</button>
          </form>
        </div>
      `;

      /* Like toggle */
      const likeBtn = card.querySelector('[data-like]');
      const likeCountEl = card.querySelector('[data-like-count]');
      let localLiked = liked;
      let localLikeCount = post.like_count;

      likeBtn.addEventListener('click', async () => {
        const method = localLiked ? 'DELETE' : 'POST';
        const res = await apiFetch(`/api/v1/community-posts/${post.id}/likes`, { method });
        if (res.ok || res.status === 409) {
          localLiked = !localLiked;
          localLikeCount += localLiked ? 1 : -1;
          likeBtn.classList.toggle('active', localLiked);
          likeBtn.setAttribute('aria-pressed', String(localLiked));
          likeBtn.querySelector('svg').setAttribute('fill', localLiked ? 'currentColor' : 'none');
          likeCountEl.textContent = `${localLikeCount} likes`;
        } else {
          showToast('Could not process like', true);
        }
      });

      /* Toggle comments */
      const toggleBtn = card.querySelector('[data-toggle-comments]');
      const commentsSection = card.querySelector('[data-comments-section]');
      const commentsList = card.querySelector('[data-comments-list]');
      const commentForm = card.querySelector('[data-comment-form]');
      const commentInput = commentForm.querySelector('input');
      const commentCountEl = card.querySelector('[data-comment-count]');
      let localCommentCount = post.comment_count;
      let commentsLoaded = false;

      toggleBtn.addEventListener('click', async () => {
        const isOpen = commentsSection.classList.toggle('open');
        if (isOpen && !commentsLoaded) {
          await loadComments(post.id, commentsList);
          commentsLoaded = true;
        }
      });

      /* Submit comment */
      commentForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const content = commentInput.value.trim();
        if (!content) return;

        const res = await apiFetch(`/api/v1/community-posts/${post.id}/comments`, {
          method: 'POST',
          body: JSON.stringify({ content }),
        });
        if (!res.ok) { showToast('Could not send comment', true); return; }

        commentInput.value = '';
        localCommentCount++;
        commentCountEl.textContent = `${localCommentCount} comments`;
        await loadComments(post.id, commentsList);
      });

      return card;
    }

    /* ── Load comments ───────────────────────────────────────── */
    async function loadComments(postId, container) {
      container.innerHTML = '<p style="font-size:.85rem;color:#94A3B8;padding:.5rem 0;">Loading…</p>';

      const res = await apiFetch(`/api/v1/community-posts/${postId}/comments/enriched`);
      if (!res.ok) {
        container.innerHTML = '<p style="font-size:.85rem;color:#DC2626;">Error loading comments.</p>';
        return;
      }

      const comments = await res.json();
      if (!comments.length) {
        container.innerHTML = '<p style="font-size:.85rem;color:#94A3B8;padding:.4rem 0;">No comments yet.</p>';
        return;
      }

      container.innerHTML = '';
      comments.forEach(c => {
        const el = document.createElement('div');
        el.className = 'comment-item';
        el.innerHTML = `
          <div class="comment-avatar">${escapeHtml(initials(c.author_name))}</div>
          <div class="comment-body">
            <strong>${escapeHtml(c.author_name)}</strong>
            <time datetime="${c.created_at}">${timeAgo(c.created_at)}</time>
            <p>${escapeHtml(c.content)}</p>
          </div>
        `;
        container.appendChild(el);
      });
    }

    /* ── Composer ─────────────────────────────────────────────── */
    $compBody.addEventListener('input', () => {
      $compSubmit.disabled = !$compBody.value.trim();
    });

    $compSubmit.addEventListener('click', async () => {
      const content = $compBody.value.trim();
      if (!content) return;
      $compSubmit.disabled = true;

      const title = $compTitle.value.trim();
      const res = await apiFetch(`/api/v1/communities/${COMMUNITY_ID}/posts`, {
        method: 'POST',
        body: JSON.stringify({ title: title || null, content }),
      });

      if (!res.ok) {
        showToast('Could not publish', true);
        $compSubmit.disabled = false;
        return;
      }

      $compTitle.value = '';
      $compBody.value = '';
      $compSubmit.disabled = true;
      showToast('Post published!');
      await loadFeed();
    });

    /* ── Start ───────────────────────────────────────────────── */
    init();

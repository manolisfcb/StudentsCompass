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

    function formatPostTypeLabel(postType) {
      const labels = {
        discussion: 'Discussion',
        question: 'Question',
        resource: 'Resource',
        win: 'Win',
        accountability: 'Accountability',
        introduction: 'Introduction',
      };
      return labels[postType] || 'Discussion';
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
    const $promptCard  = document.getElementById('community-prompt-card');
    const $promptTitle = document.getElementById('prompt-title');
    const $promptBody  = document.getElementById('prompt-body');
    const $promptUse   = document.getElementById('prompt-use-btn');
    const $promptIntro = document.getElementById('prompt-intro-btn');
    const $promptFeedback = document.getElementById('prompt-feedback-btn');
    const $compType    = document.getElementById('compose-type');
    const $compHint    = document.getElementById('compose-hint');
    const $compTitle   = document.getElementById('compose-title');
    const $compBody    = document.getElementById('compose-body');
    const $compSubmit  = document.getElementById('compose-submit');
    const $quickIntro  = document.getElementById('compose-quick-intro');
    const $quickFeedback = document.getElementById('compose-quick-feedback');
    const $quickWin    = document.getElementById('compose-quick-win');
    const $feedList    = document.getElementById('feed-list');
    const $feedEmpty   = document.getElementById('feed-empty');

    let communityData = null;
    let isMember = false;
    let weeklyPrompt = null;
    let currentUserId = null;

    const POST_TYPE_META = {
      discussion: {
        titlePlaceholder: 'Start a discussion',
        bodyPlaceholder: 'Share a concrete idea, blocker, or insight that others can build on.',
        hint: 'Best for conversations, reflections, and useful observations from your journey.',
      },
      question: {
        titlePlaceholder: 'Ask a focused question',
        bodyPlaceholder: 'What are you trying to figure out? Include context so people can help well.',
        hint: 'Ask one specific question and include enough context to get useful answers.',
      },
      resource: {
        titlePlaceholder: 'Share a useful resource',
        bodyPlaceholder: 'What is the resource, why is it helpful, and who will benefit from it?',
        hint: 'Great for templates, tools, articles, events, and learning resources.',
      },
      win: {
        titlePlaceholder: 'Share a win',
        bodyPlaceholder: 'What progress did you make, and what helped you get there?',
        hint: 'Celebrate milestones so others can learn from what worked.',
      },
      accountability: {
        titlePlaceholder: 'Share your next step',
        bodyPlaceholder: 'What are you committing to this week, and what support do you need?',
        hint: 'Use this to stay consistent and make your next action public.',
      },
      introduction: {
        titlePlaceholder: 'Introduce yourself',
        bodyPlaceholder: 'Tell the community who you are, what you are aiming for, and what support would help right now.',
        hint: 'Ideal when you join a community and want to make it easier for others to help you.',
      },
    };

    /* ── Init ────────────────────────────────────────────────── */
    async function init() {
      try {
        const profileRes = await apiFetch('/api/v1/profile', {
          cache: 'no-store',
        });
        if (profileRes.status === 401) { window.location.href = '/login'; return; }
        if (profileRes.ok) {
          const profile = await profileRes.json();
          currentUserId = profile.id || null;
        }

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
      weeklyPrompt = buildWeeklyPrompt(c);
      renderPromptCard();
    }

    function buildWeeklyPrompt(community) {
      const text = `${community.name} ${(community.description || '')} ${(community.tags || []).join(' ')}`.toLowerCase();

      if (/(interview|mock interview|behavioral|star)/.test(text)) {
        return {
          title: 'Weekly prompt: practice one interview story',
          body: 'Share one STAR example you could use in an interview and ask the community to strengthen it with sharper outcomes or clearer impact.',
          preset: {
            postType: 'question',
            title: 'Can you help me sharpen this interview story?',
            content: 'I am preparing for interviews and want feedback on this STAR example.\n\nSituation:\nTask:\nAction:\nResult:\n\nThe part I want help with is:',
          },
        };
      }

      if (/(resume|cv|linkedin|portfolio)/.test(text)) {
        return {
          title: 'Weekly prompt: ask for one piece of profile feedback',
          body: 'Post one resume bullet, LinkedIn headline, or portfolio snippet and ask the community to make it clearer, stronger, and more aligned with your target role.',
          preset: {
            postType: 'question',
            title: 'Could I get feedback on this profile section?',
            content: 'I am improving my profile for roles in:\n\nHere is the section I want feedback on:\n\nWhat I want help with:\n- Clarity\n- Impact\n- Relevance to target roles',
          },
        };
      }

      if (/(data|analytics|python|sql|backend|software|developer|engineering)/.test(text)) {
        return {
          title: 'Weekly prompt: share what you are building',
          body: 'Show one project, workflow, or technical concept you are learning right now, and explain the next step you are taking to make it portfolio-ready.',
          preset: {
            postType: 'accountability',
            title: 'This is the project step I am tackling this week',
            content: 'I am currently working on:\n\nWhy it matters for my career goal:\n\nMy next concrete step this week:\n\nThe blocker I would love help with:',
          },
        };
      }

      if (/(design|ux|ui|product)/.test(text)) {
        return {
          title: 'Weekly prompt: explain one design decision',
          body: 'Share a screen, case-study moment, or design choice you made and ask the community whether your reasoning is clear to recruiters and hiring teams.',
          preset: {
            postType: 'discussion',
            title: 'Does this design decision make sense?',
            content: 'I am working on this design/project:\n\nThe decision I made was:\n\nI chose it because:\n\nI would love feedback on whether the reasoning feels clear and strong.',
          },
        };
      }

      return {
        title: 'Weekly prompt: make your next career step visible',
        body: 'Share one thing you are working on right now, one blocker you are facing, and one kind of support that would help you move forward this week.',
        preset: {
          postType: 'accountability',
          title: 'My next step this week',
          content: 'This week I am focused on:\n\nThe blocker I am facing:\n\nSupport that would help me move faster:',
        },
      };
    }

    function renderPromptCard() {
      if (!weeklyPrompt) return;
      $promptTitle.textContent = weeklyPrompt.title;
      $promptBody.textContent = weeklyPrompt.body;
    }

    function buildIntroductionPreset() {
      const communityName = communityData?.name || 'this community';
      return {
        postType: 'introduction',
        title: `Hello from a new member in ${communityName}`,
        content: 'Hi everyone! I am excited to be here.\n\nI am currently exploring:\n\nMy career goal right now is:\n\nThis is what I am working on this month:\n\nI would love support or advice on:',
      };
    }

    function buildFeedbackPreset() {
      return {
        postType: 'question',
        title: 'Could I get feedback on my next step?',
        content: 'I am currently targeting roles in:\n\nThe thing I want feedback on is:\n\nContext:\n\nSpecific feedback I would find helpful:',
      };
    }

    function buildWinPreset() {
      return {
        postType: 'win',
        title: 'Small win from this week',
        content: 'This week I made progress on:\n\nWhy it matters for my career goal:\n\nWhat helped me move forward:\n\nMy next step is:',
      };
    }

    function applyComposerPreset(preset) {
      if (!preset) return;
      $compType.value = preset.postType || 'discussion';
      $compTitle.value = preset.title || '';
      $compBody.value = preset.content || '';
      updateComposerMeta();
      $compSubmit.disabled = !$compBody.value.trim();
      $compBody.focus();
      $compBody.setSelectionRange($compBody.value.length, $compBody.value.length);
    }

    function updateComposerMeta() {
      const meta = POST_TYPE_META[$compType.value] || POST_TYPE_META.discussion;
      $compTitle.placeholder = meta.titlePlaceholder;
      $compBody.placeholder = meta.bodyPlaceholder;
      $compHint.textContent = meta.hint;
    }

    /* ── Membership UI ─────────────────────────────────────── */
    function updateMembershipUI() {
      if (isMember) {
        $bannerJoin.style.display = 'none';
        $bannerLeave.style.display = 'inline-flex';
        $composer.style.display = '';
        $promptCard.hidden = false;
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
        $promptCard.hidden = true;
        $feedEmpty.style.display = 'none';
        $feedList.innerHTML = '';
        $feedLayout.style.display = 'none';
        $gate.style.display = 'block';
      }
    }

    function getCurrentUserId() {
      return currentUserId;
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

    $promptUse?.addEventListener('click', () => applyComposerPreset(weeklyPrompt?.preset));
    $promptIntro?.addEventListener('click', () => applyComposerPreset(buildIntroductionPreset()));
    $promptFeedback?.addEventListener('click', () => applyComposerPreset(buildFeedbackPreset()));

    $quickIntro?.addEventListener('click', () => applyComposerPreset(buildIntroductionPreset()));
    $quickFeedback?.addEventListener('click', () => applyComposerPreset(buildFeedbackPreset()));
    $quickWin?.addEventListener('click', () => applyComposerPreset(buildWinPreset()));
    $compType?.addEventListener('change', updateComposerMeta);

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
      const friendshipStatuses = await loadFriendshipStatuses(posts.map((post) => post.user_id));
      posts.forEach((post) => {
        $feedList.appendChild(createPostCard(post, friendshipStatuses.get(post.user_id)));
      });
    }

    async function loadFriendshipStatuses(userIds) {
      const uniqueUserIds = [...new Set((userIds || []).filter(Boolean))];
      if (!uniqueUserIds.length) {
        return new Map();
      }

      const query = encodeURIComponent(uniqueUserIds.join(','));
      const response = await apiFetch(`/api/v1/friends/status?user_ids=${query}`);
      if (!response.ok) {
        return new Map();
      }

      const statuses = await response.json();
      return new Map(statuses.map((status) => [status.user_id, status]));
    }

    function getFriendshipActionMarkup(friendshipStatus) {
      const status = friendshipStatus?.status || 'none';
      const requestId = friendshipStatus?.request_id || '';

      if (status === 'self') {
        return '';
      }

      if (status === 'friends') {
        return '<span class="friend-pill friend-pill--friends">Friends</span>';
      }

      if (status === 'incoming_request') {
        return `
          <div class="friend-actions-inline">
            <button class="friend-mini-btn friend-mini-btn--primary" data-friend-action="accept" data-request-id="${escapeHtml(requestId)}">Accept</button>
            <button class="friend-mini-btn" data-friend-action="reject" data-request-id="${escapeHtml(requestId)}">Ignore</button>
          </div>
        `;
      }

      if (status === 'outgoing_request') {
        return `
          <div class="friend-actions-inline">
            <span class="friend-pill friend-pill--pending">Pending</span>
            <button class="friend-mini-btn" data-friend-action="cancel" data-request-id="${escapeHtml(requestId)}">Cancel</button>
          </div>
        `;
      }

      return `<button class="friend-mini-btn friend-mini-btn--primary" data-friend-action="send" data-user-id="${escapeHtml(friendshipStatus?.user_id || '')}">Add friend</button>`;
    }

    async function handleFriendshipAction({ action, userId, requestId }) {
      let endpoint = '';
      let method = 'POST';
      let successMessage = 'Updated friendship';
      let body = undefined;

      if (action === 'send') {
        endpoint = '/api/v1/friends/requests';
        body = JSON.stringify({ receiver_id: userId });
        successMessage = 'Friend request sent';
      } else if (action === 'accept') {
        endpoint = `/api/v1/friends/requests/${requestId}/accept`;
        successMessage = 'Friend request accepted';
      } else if (action === 'reject') {
        endpoint = `/api/v1/friends/requests/${requestId}/reject`;
        successMessage = 'Friend request ignored';
      } else if (action === 'cancel') {
        endpoint = `/api/v1/friends/requests/${requestId}/cancel`;
        successMessage = 'Friend request cancelled';
      } else {
        return;
      }

      const response = await apiFetch(endpoint, { method, body });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        showToast(error.detail || 'Could not update friendship', true);
        return;
      }

      showToast(successMessage);
      await loadFeed();
    }

    /* ── Create post card ────────────────────────────────────── */
    function createPostCard(post, friendshipStatus) {
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
            <div class="post-author-action">
              ${getFriendshipActionMarkup(friendshipStatus || { status: 'none', user_id: post.user_id })}
            </div>
          </div>
          <div class="post-meta-row">
            <span class="post-type-badge post-type-badge--${escapeHtml(post.post_type || 'discussion')}">${escapeHtml(formatPostTypeLabel(post.post_type))}</span>
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

      card.querySelectorAll('[data-friend-action]').forEach((button) => {
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            await handleFriendshipAction({
              action: button.dataset.friendAction,
              userId: button.dataset.userId || post.user_id,
              requestId: button.dataset.requestId,
            });
          } finally {
            if (card.isConnected) {
              button.disabled = false;
            }
          }
        });
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
    updateComposerMeta();

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
        body: JSON.stringify({
          title: title || null,
          content,
          post_type: $compType.value,
        }),
      });

      if (!res.ok) {
        showToast('Could not publish', true);
        $compSubmit.disabled = false;
        return;
      }

      $compTitle.value = '';
      $compBody.value = '';
      $compType.value = 'discussion';
      updateComposerMeta();
      $compSubmit.disabled = true;
      showToast('Post published!');
      await loadFeed();
    });

    /* ── Start ───────────────────────────────────────────────── */
    init();

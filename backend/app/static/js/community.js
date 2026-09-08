/* ── Helpers ──────────────────────────────────────────────── */
    function escapeHtml(str) {
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    }

    async function apiFetch(url, options = {}) {
      const res = await fetch(url, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options,
      });
      return res;
    }

    /* ── State ───────────────────────────────────────────────── */
    let allCommunities = [];
    let selectedTags = [];
    let tagSuggestions = [];
    let tagSearchRequestId = 0;

    /* ── DOM refs ─────────────────────────────────────────────── */
    const gridEl       = document.getElementById('communities-grid');
    const emptyEl      = document.getElementById('community-list-empty');
    const searchInput  = document.getElementById('search-input');
    const sortSelect   = document.getElementById('sort-select');
    const selectedTagsEl = document.getElementById('selected-tags');
    const tagSearchInput = document.getElementById('tag-search-input');
    const tagsDropdownEl = document.getElementById('tags-dropdown');

    /* Modal refs */
    const createModal       = document.getElementById('create-community-modal');
    const openModalBtn      = document.getElementById('open-create-modal');
    const closeModalBtn     = document.getElementById('close-create-modal');
    const createForm        = document.getElementById('create-community-form');
    const nameInput         = document.getElementById('community-name');
    const descInput         = document.getElementById('community-description');
    const tagsInput         = document.getElementById('community-tags');
    const iconInput         = document.getElementById('community-icon');
    const emojiPreview      = document.getElementById('emoji-preview');
    const emojiTrigger      = document.getElementById('emoji-trigger');
    const emojiPicker       = document.getElementById('emoji-picker');
    const emojiGrid         = document.getElementById('emoji-grid');
    const emojiSearch       = document.getElementById('emoji-search');
    const emojiClose        = document.getElementById('emoji-close');

    const emojiList = ['😀','😄','😊','😍','🤩','😎','🤓','🧠','📊','📈','💡','🚀','🐍','🗄️','📉','📚','🎯','🧩','🧪','💻','🌐','🤖','🎓','📝','🔬'];

    /* ── Load & render ───────────────────────────────────────── */
    function getSelectedTagsQuery() {
      return selectedTags.length ? `?tags=${encodeURIComponent(selectedTags.join(','))}` : '';
    }

    async function loadCommunities() {
      const res = await apiFetch(`/api/v1/communities${getSelectedTagsQuery()}`);
      if (!res.ok) { allCommunities = []; renderGrid(); return; }
      allCommunities = await res.json();
      renderGrid();
    }

    function getFiltered() {
      const q = searchInput.value.trim().toLowerCase();
      let list = allCommunities;
      if (q) {
        list = list.filter(c =>
          c.name.toLowerCase().includes(q) ||
          (c.description || '').toLowerCase().includes(q) ||
          (c.tags || []).some(t => t.toLowerCase().includes(q))
        );
      }
      const sort = sortSelect.value;
      if (sort === 'members') list.sort((a, b) => (b.member_count ?? 0) - (a.member_count ?? 0));
      else if (sort === 'name') list.sort((a, b) => a.name.localeCompare(b.name));
      else list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      return list;
    }

    function closeTagDropdown() {
      tagsDropdownEl.classList.remove('is-open');
    }

    function renderTagDropdown() {
      tagsDropdownEl.innerHTML = '';

      const term = tagSearchInput.value.trim();
      if (term.length < 3) {
        closeTagDropdown();
        return;
      }

      if (!tagSuggestions.length) {
        tagsDropdownEl.innerHTML = '<div class="tags-filter__message">No matching tags found.</div>';
        tagsDropdownEl.classList.add('is-open');
        return;
      }

      tagSuggestions.forEach((tag) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'tags-filter__option';
        option.textContent = `#${tag}`;
        option.addEventListener('click', async () => {
          if (!selectedTags.includes(tag)) {
            selectedTags = [...selectedTags, tag];
            renderSelectedTags();
            await loadCommunities();
          }
          tagSearchInput.value = '';
          tagSuggestions = [];
          renderTagDropdown();
          tagSearchInput.focus();
        });
        tagsDropdownEl.appendChild(option);
      });

      tagsDropdownEl.classList.add('is-open');
    }

    function renderSelectedTags() {
      selectedTagsEl.innerHTML = '';

      if (!selectedTags.length) {
        selectedTagsEl.innerHTML = '<span class="tags-filter__empty">No hay tags seleccionados.</span>';
        return;
      }

      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'tag-filter-chip tag-filter-chip--clear';
      clearBtn.textContent = 'Clear all';
      clearBtn.addEventListener('click', async () => {
        selectedTags = [];
        renderSelectedTags();
        await loadCommunities();
      });
      selectedTagsEl.appendChild(clearBtn);

      selectedTags.forEach((tag) => {
        const chip = document.createElement('span');
        chip.className = 'tag-filter-chip';
        chip.innerHTML = `#${escapeHtml(tag)} <button type="button" class="tag-filter-chip__remove" aria-label="Remove ${escapeHtml(tag)}">&times;</button>`;
        chip.querySelector('.tag-filter-chip__remove').addEventListener('click', async () => {
          selectedTags = selectedTags.filter((selectedTag) => selectedTag !== tag);
          renderSelectedTags();
          await loadCommunities();
        });
        selectedTagsEl.appendChild(chip);
      });
    }

    async function searchTags(term) {
      const normalizedTerm = term.trim();
      if (normalizedTerm.length < 3) {
        tagSuggestions = [];
        renderTagDropdown();
        return;
      }

      const requestId = ++tagSearchRequestId;
      const res = await apiFetch(`/api/v1/communities/tags?q=${encodeURIComponent(normalizedTerm)}&limit=10`);
      if (requestId !== tagSearchRequestId) return;

      if (!res.ok) {
        tagSuggestions = [];
        renderTagDropdown();
        return;
      }

      const results = await res.json();
      tagSuggestions = results.filter((tag) => !selectedTags.includes(tag));
      renderTagDropdown();
    }

    function renderGrid() {
      const list = getFiltered();
      gridEl.innerHTML = '';
      if (!list.length) { emptyEl.style.display = 'block'; return; }
      emptyEl.style.display = 'none';

      list.forEach(c => {
        const card = document.createElement('div');
        card.className = 'community-card';
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'link');
        card.setAttribute('aria-label', `Go to ${escapeHtml(c.name)}`);

        const tagsHtml = (c.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
        const members = c.member_count ?? 0;
        const status = c.activity_status || 'Active';

        card.innerHTML = `
          <div class="community-icon">${escapeHtml(c.icon || '👥')}</div>
          <h3 class="community-title">${escapeHtml(c.name)}</h3>
          <p class="community-description">${escapeHtml(c.description || 'No description.')}</p>
          <div class="community-stats">
            <div class="stat-item">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3.87-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
              <span>${members} members</span>
            </div>
            <span class="community-status">${escapeHtml(status)}</span>
          </div>
          <div class="community-tags">${tagsHtml}</div>
          <button class="join-btn" data-id="${c.id}">View community</button>
        `;

        /* Click on card → go to feed */
        const navigate = () => { window.location.href = '/community/' + c.id; };
        card.addEventListener('click', (e) => {
          if (e.target.closest('[data-id]')) return; /* button handles its own click */
          navigate();
        });
        card.addEventListener('keydown', (e) => { if (e.key === 'Enter') navigate(); });

        /* "View community" button */
        card.querySelector('[data-id]').addEventListener('click', (e) => {
          e.stopPropagation();
          navigate();
        });

        gridEl.appendChild(card);
      });
    }

    searchInput.addEventListener('input', renderGrid);
    sortSelect.addEventListener('change', renderGrid);
    tagSearchInput.addEventListener('input', (e) => { searchTags(e.target.value); });
    tagSearchInput.addEventListener('focus', () => { renderTagDropdown(); });

    /* ── Modal: create community ─────────────────────────────── */
    function openModal() {
      createModal.style.display = 'flex';
      document.body.classList.add('modal-open');
      nameInput.focus();
    }
    function closeModal() {
      createModal.style.display = 'none';
      document.body.classList.remove('modal-open');
      closeEmojiPicker();
    }

    openModalBtn.addEventListener('click', openModal);
    closeModalBtn.addEventListener('click', closeModal);
    createModal.addEventListener('click', (e) => { if (e.target === createModal) closeModal(); });

    createForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = nameInput.value.trim();
      if (!name) return;
      const description = descInput.value.trim();
      const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);
      const icon = iconInput.value.trim();

      const res = await apiFetch('/api/v1/communities', {
        method: 'POST',
        body: JSON.stringify({
          name,
          description: description || null,
          tags: tags.length ? tags : null,
          icon: icon || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Unable to create the community.');
        return;
      }
      const created = await res.json();
      nameInput.value = ''; descInput.value = ''; tagsInput.value = ''; iconInput.value = '';
      emojiPreview.textContent = '👥';
      closeModal();
      /* Go directly to the new community feed */
      window.location.href = '/community/' + created.id;
    });

    /* ── Emoji picker ────────────────────────────────────────── */
    function renderEmojis(filter = '') {
      emojiGrid.innerHTML = '';
      emojiList.filter(e => e.includes(filter)).forEach(emoji => {
        const btn = document.createElement('button');
        btn.type = 'button'; btn.className = 'emoji-picker__item';
        btn.textContent = emoji;
        btn.addEventListener('click', () => {
          emojiPreview.textContent = emoji; iconInput.value = emoji;
          closeEmojiPicker();
        });
        emojiGrid.appendChild(btn);
      });
    }
    function openEmojiPicker() {
      emojiPicker.style.display = 'block';
      emojiPicker.setAttribute('aria-hidden','false');
      emojiTrigger.setAttribute('aria-expanded','true');
      emojiSearch.focus();
    }
    function closeEmojiPicker() {
      emojiPicker.style.display = 'none';
      emojiPicker.setAttribute('aria-hidden','true');
      emojiTrigger.setAttribute('aria-expanded','false');
    }

    emojiTrigger.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      emojiPicker.style.display === 'block' ? closeEmojiPicker() : openEmojiPicker();
    });
    emojiClose.addEventListener('click', closeEmojiPicker);
    emojiSearch.addEventListener('input', (e) => renderEmojis(e.target.value));

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (emojiPicker.style.display === 'block') { closeEmojiPicker(); return; }
        if (createModal.style.display === 'flex') closeModal();
      }
    });
    document.addEventListener('click', (e) => {
      if (emojiPicker.style.display === 'block' &&
          !emojiPicker.contains(e.target) && !emojiTrigger.contains(e.target))
        closeEmojiPicker();
      if (!e.target.closest('.tags-filter')) closeTagDropdown();
    });

    /* ── Init ────────────────────────────────────────────────── */
    renderEmojis();
    renderSelectedTags();
    loadCommunities();

/* ============================================================
       Admin Panel – Client-side Logic
       ============================================================ */

    const API = '/api/v1/admin';

    // ── Helpers ───────────────────────────────────────────────────
    function esc(str) {
        if (!str) return '—';
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    function formatDate(iso) {
        if (!iso) return '—';
        const d = new Date(iso);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function avatarColor(email) {
        let hash = 0;
        for (let i = 0; i < (email || '').length; i++) hash = email.charCodeAt(i) + ((hash << 5) - hash);
        const colors = ['#6366f1', '#14b8a6', '#f59e0b', '#f43f5e', '#0ea5e9', '#8b5cf6', '#10b981', '#ec4899'];
        return colors[Math.abs(hash) % colors.length];
    }

    // ── Toast ─────────────────────────────────────────────────────
    function toast(msg, type = 'success') {
        const wrap = document.getElementById('toastWrap');
        const icons = { success: '✅', error: '❌', warning: '⚠️' };
        const el = document.createElement('div');
        el.className = `admin-toast ${type}`;
        el.innerHTML = `<span>${icons[type] || ''}</span> ${esc(msg)}`;
        wrap.appendChild(el);
        setTimeout(() => {
            el.style.animation = 'toastSlideOut 0.3s ease-out forwards';
            setTimeout(() => el.remove(), 300);
        }, 3500);
    }

    // ── Confirm Modal ─────────────────────────────────────────────
    let confirmCallback = null;
    function openConfirm(title, desc, cb) {
        document.getElementById('confirmTitle').textContent = title;
        document.getElementById('confirmDesc').textContent = desc;
        document.getElementById('confirmModal').style.display = '';
        confirmCallback = cb;
    }
    function closeConfirm() {
        document.getElementById('confirmModal').style.display = 'none';
        confirmCallback = null;
    }
    document.getElementById('confirmOk').onclick = async () => {
        if (confirmCallback) { await confirmCallback(); }
        closeConfirm();
    };

    // ── Sidebar ───────────────────────────────────────────────────
    function toggleSidebar() {
        document.getElementById('sidebar').classList.toggle('open');
        document.getElementById('sidebarOverlay').classList.toggle('open');
    }

    // ── Section Switching ─────────────────────────────────────────
    const sectionLoaded = {};

    function showSection(name, btn) {
        document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.admin-nav-item').forEach(n => n.classList.remove('active'));
        document.getElementById(`section-${name}`).classList.add('active');
        if (btn) btn.classList.add('active');

        const titles = {
            dashboard: 'Dashboard',
            users: 'Users',
            resources: 'Resources'
        };
        document.getElementById('headerTitle').textContent = titles[name] || name;

        // Lazy-load data
        if (!sectionLoaded[name]) {
            sectionLoaded[name] = true;
            loaders[name]?.();
        }

        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('sidebarOverlay').classList.remove('open');
    }

    // ── Data loaders ──────────────────────────────────────────────
    const loaders = {
        dashboard: loadDashboard,
        users: loadUsers,
        resources: loadResources,
    };

    // -- Dashboard Stats --
    async function loadDashboard() {
        try {
            const res = await fetch(`${API}/stats`, { credentials: 'include' });
            if (!res.ok) throw new Error();
            const d = await res.json();
            const cards = [
                { icon: '👥', cls: 'users', label: 'Total Users', value: d.total_users },
                { icon: '📚', cls: 'resources', label: 'Resources', value: d.total_resources },
                { icon: '📄', cls: 'resumes', label: 'Resumes', value: d.total_resumes },
                { icon: '📝', cls: 'questionnaires', label: 'Questionnaires', value: d.total_questionnaires },
            ];
            document.getElementById('statsGrid').innerHTML = cards.map(c => `
      <div class="admin-stat-card">
        <div class="admin-stat-header">
          <div class="admin-stat-icon ${c.cls}">${c.icon}</div>
        </div>
        <div class="admin-stat-value">${c.value.toLocaleString()}</div>
        <div class="admin-stat-label">${c.label}</div>
      </div>
    `).join('');
            document.getElementById('navBadgeUsers').textContent = d.total_users;
        } catch { toast('Failed to load stats', 'error'); }
    }

    // -- Users --
    let allUsers = [];
    async function loadUsers() {
        try {
            const res = await fetch(`${API}/users?limit=200`, { credentials: 'include' });
            if (!res.ok) throw new Error();
            const d = await res.json();
            allUsers = d.users;
            renderUsers(allUsers);
        } catch { toast('Failed to load users', 'error'); }
    }

    function renderUsers(users) {
        const tbody = document.getElementById('usersTableBody');
        if (!users.length) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="admin-empty"><div class="admin-empty-icon">👥</div><div class="admin-empty-title">No users found</div></div></td></tr>';
            return;
        }
        tbody.innerHTML = users.map(u => {
            const initial = (u.first_name || u.email || '?')[0].toUpperCase();
            const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || '—';
            return `<tr data-search="${(u.email + ' ' + name).toLowerCase()}">
      <td>
        <div class="admin-user-cell">
          <div class="admin-user-mini-avatar" style="background:${avatarColor(u.email)}">${initial}</div>
          <span>${esc(u.email)}</span>
        </div>
      </td>
      <td>${esc(name)}</td>
      <td><span class="admin-badge ${u.is_active ? 'active' : 'inactive'}">${u.is_active ? '● Active' : '● Inactive'}</span></td>
      <td>${u.is_superuser ? '<span class="admin-badge admin">⚡ Admin</span>' : 'User'}</td>
      <td>${u.is_verified ? '✅' : '❌'}</td>
      <td>
        <div class="admin-actions-cell">
          <button class="admin-btn-icon" title="Toggle active" onclick="toggleActive('${u.id}')">
            ${u.is_active ? '🔒' : '🔓'}
          </button>
          <button class="admin-btn-icon" title="Toggle admin" onclick="toggleSuperuser('${u.id}')">
            ⚡
          </button>
          <button class="admin-btn-icon danger" title="Delete" onclick="deleteUser('${u.id}', '${esc(u.email)}')">
            🗑️
          </button>
        </div>
      </td>
    </tr>`;
        }).join('');
    }

    async function toggleActive(id) {
        try {
            const res = await fetch(`${API}/users/${id}/toggle-active`, { method: 'PATCH', credentials: 'include' });
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
            const u = await res.json();
            toast(`User ${u.email} is now ${u.is_active ? 'active' : 'inactive'}`);
            await loadUsers();
        } catch (e) { toast(e.message || 'Failed', 'error'); }
    }

    async function toggleSuperuser(id) {
        openConfirm('Toggle Admin Role', 'Are you sure you want to change this user\'s admin privileges?', async () => {
            try {
                const res = await fetch(`${API}/users/${id}/toggle-superuser`, { method: 'PATCH', credentials: 'include' });
                if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
                const u = await res.json();
                toast(`User ${u.email} is now ${u.is_superuser ? 'an admin' : 'a regular user'}`);
                await loadUsers();
            } catch (e) { toast(e.message || 'Failed', 'error'); }
        });
    }

    async function deleteUser(id, email) {
        openConfirm('Delete User', `Are you sure you want to permanently delete "${email}"? This action cannot be undone.`, async () => {
            try {
                const res = await fetch(`${API}/users/${id}`, { method: 'DELETE', credentials: 'include' });
                if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
                toast(`User ${email} deleted`);
                await loadUsers();
                loadDashboard();
            } catch (e) { toast(e.message || 'Failed', 'error'); }
        });
    }

    // -- Resources --
    let moduleDraftCounter = 0;
    let resourceDraftCounter = 0;
    let editingResourceId = null;

    function normalizeTags(rawTags) {
        return String(rawTags || '')
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean);
    }

    function resetResourceStructureBuilder() {
        moduleDraftCounter = 0;
        resourceDraftCounter = 0;
        document.getElementById('resourceModulesBuilder').innerHTML = '';
    }

    function setResourceModalMode(mode) {
        const isEdit = mode === 'edit';
        document.getElementById('resourceModalTitle').textContent = isEdit ? 'Edit Resource' : 'Create Resource';
        document.getElementById('resourceModalDesc').textContent = isEdit
            ? 'Modify any field and save changes to this resource.'
            : 'Fill in the details and build the course structure.';
    }

    function openResourceModal() {
        editingResourceId = null;
        document.getElementById('resourceForm').reset();
        document.getElementById('resPublished').checked = true;
        document.getElementById('resLocked').checked = false;
        resetResourceStructureBuilder();
        addModuleBlock();
        setResourceModalMode('create');
        document.getElementById('resourceModal').style.display = '';
    }

    async function openEditResourceModal(resourceId) {
        try {
            const res = await fetch(`${API}/resources/${resourceId}`, { credentials: 'include' });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data?.detail || 'Failed to load resource details');
            }
            const resource = await res.json();
            editingResourceId = resource.id;
            setResourceModalMode('edit');
            document.getElementById('resTitle').value = resource.title || '';
            document.getElementById('resDesc').value = resource.description || '';
            document.getElementById('resCategory').value = resource.category || '';
            document.getElementById('resLevel').value = resource.level || '';
            document.getElementById('resIcon').value = resource.icon || '';
            document.getElementById('resDuration').value = resource.estimated_duration_minutes ?? '';
            document.getElementById('resUrl').value = resource.external_url || '';
            document.getElementById('resTags').value = Array.isArray(resource.tags) ? resource.tags.join(', ') : '';
            document.getElementById('resPublished').checked = Boolean(resource.is_published);
            document.getElementById('resLocked').checked = Boolean(resource.is_locked);

            resetResourceStructureBuilder();
            const modules = Array.isArray(resource.modules) ? resource.modules : [];
            if (!modules.length) {
                addModuleBlock();
            } else {
                modules.forEach((module) => addModuleBlock(module));
            }
            document.getElementById('resourceModal').style.display = '';
        } catch (e) {
            toast(e.message || 'Failed to load resource details', 'error');
        }
    }

    function closeResourceModal() {
        editingResourceId = null;
        document.getElementById('resourceModal').style.display = 'none';
    }

    function addModuleBlock(prefill = null) {
        moduleDraftCounter += 1;
        const moduleId = moduleDraftCounter;
        const moduleWrap = document.getElementById('resourceModulesBuilder');
        const moduleEl = document.createElement('div');
        moduleEl.className = 'resource-module-block';
        moduleEl.dataset.moduleId = String(moduleId);
        moduleEl.innerHTML = `
      <div class="resource-module-head">
        <h5 class="resource-module-title">Module ${moduleId}</h5>
        <button type="button" class="admin-btn admin-btn-danger" onclick="removeModuleBlock(${moduleId})">Remove module</button>
      </div>
      <div class="admin-form-group">
        <label class="admin-form-label">Module title</label>
        <input class="admin-form-input module-title" placeholder="e.g. Chapter 1: Fundamentals" required>
      </div>
      <div class="admin-form-group">
        <label class="admin-form-label">Module description (optional)</label>
        <textarea class="admin-form-input module-description" rows="2" placeholder="What will students learn in this module?"></textarea>
      </div>
      <div class="resource-items-wrap">
        <div class="resource-structure-header" style="margin-bottom:8px;">
          <span class="module-resources-title">Module lessons/resources</span>
          <button type="button" class="admin-btn admin-btn-ghost" onclick="addResourceBlock(${moduleId})">+ Add lesson</button>
        </div>
        <div id="moduleResources-${moduleId}"></div>
      </div>
    `;
        moduleWrap.appendChild(moduleEl);

        if (prefill?.title) moduleEl.querySelector('.module-title').value = prefill.title;
        if (prefill?.description) moduleEl.querySelector('.module-description').value = prefill.description;

        if (prefill?.lessons?.length) {
            prefill.lessons.forEach((lesson) => addResourceBlock(moduleId, lesson));
        } else {
            addResourceBlock(moduleId);
        }

        reindexModuleLabels();
    }

    function removeModuleBlock(moduleId) {
        const el = document.querySelector(`.resource-module-block[data-module-id="${moduleId}"]`);
        if (!el) return;
        el.remove();
        reindexModuleLabels();
    }

    function reindexModuleLabels() {
        document.querySelectorAll('.resource-module-block').forEach((moduleEl, idx) => {
            const title = moduleEl.querySelector('.resource-module-title');
            if (title) title.textContent = `Module ${idx + 1}`;
        });
    }

    function addResourceBlock(moduleId, prefill = null) {
        const list = document.getElementById(`moduleResources-${moduleId}`);
        if (!list) return;

        resourceDraftCounter += 1;
        const resourceId = resourceDraftCounter;
        const row = document.createElement('div');
        row.className = 'resource-item-row';
        row.dataset.resourceId = String(resourceId);
        row.innerHTML = `
      <div class="resource-item-head">
        <span class="resource-item-label">Lesson item</span>
        <button type="button" class="admin-btn admin-btn-danger" onclick="removeResourceBlock(${moduleId}, ${resourceId})">Remove</button>
      </div>
      <div class="admin-form-group">
        <label class="admin-form-label">Lesson title</label>
        <input class="admin-form-input lesson-title" placeholder="e.g. Intro video" required>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;">
        <div class="admin-form-group" style="flex:1;min-width:220px;">
          <label class="admin-form-label">Content type</label>
          <input class="admin-form-input lesson-type" list="lessonTypeSuggestions" placeholder="e.g. video_url">
        </div>
        <div class="admin-form-group" style="flex:1;min-width:240px;">
          <label class="admin-form-label">Primary URL (video/resource)</label>
          <input class="admin-form-input lesson-url" type="url" placeholder="https://...">
        </div>
        <div class="admin-form-group" style="width:180px;">
          <label class="admin-form-label">Reading time (mins)</label>
          <input type="number" min="1" class="admin-form-input lesson-reading-time" placeholder="e.g. 8">
        </div>
      </div>
      <div class="admin-form-group">
        <label class="admin-form-label">Lesson notes (optional)</label>
        <textarea class="admin-form-input lesson-notes" rows="2" placeholder="Short note, context, or guidance for this lesson"></textarea>
      </div>
      <div class="admin-form-group">
        <label class="admin-form-label">Lesson body/content</label>
        <textarea class="admin-form-input lesson-content" rows="3" placeholder="Detailed content or prompt text"></textarea>
      </div>
      <div class="resource-upload-row">
        <div class="admin-form-group" style="flex:1;margin-bottom:0;">
          <label class="admin-form-label">Upload file to S3 (optional)</label>
          <input type="file" class="admin-form-input lesson-file">
        </div>
        <button type="button" class="admin-btn admin-btn-ghost" onclick="uploadLessonFile(${moduleId}, ${resourceId})">
          Upload file
        </button>
      </div>
      <div class="resource-upload-status" aria-live="polite"></div>
    `;
        list.appendChild(row);

        if (prefill?.title) row.querySelector('.lesson-title').value = prefill.title;
        if (prefill?.content_type) row.querySelector('.lesson-type').value = prefill.content_type;
        if (prefill?.reading_time_minutes) row.querySelector('.lesson-reading-time').value = prefill.reading_time_minutes;
        const prefillUrl = prefill?.video_url || prefill?.resource_url || '';
        if (prefillUrl) row.querySelector('.lesson-url').value = prefillUrl;
        if (prefill?.notes) row.querySelector('.lesson-notes').value = prefill.notes;
        const payloadBody = prefill?.content_payload?.body || '';
        if (payloadBody) {
            row.querySelector('.lesson-content').value = payloadBody;
        } else if (prefill?.content && (prefill?.content_type === 'text' || prefill?.content_type === 'html' || prefill?.content_type === 'resume_upload')) {
            row.querySelector('.lesson-content').value = prefill.content;
        }

        reindexResourceLabels(moduleId);
    }

    function getResourceRow(moduleId, resourceId) {
        const moduleEl = document.querySelector(`.resource-module-block[data-module-id="${moduleId}"]`);
        if (!moduleEl) return null;
        return moduleEl.querySelector(`.resource-item-row[data-resource-id="${resourceId}"]`);
    }

    function detectLessonTypeFromFile(fileName = '', mimeType = '') {
        const name = String(fileName || '').toLowerCase();
        const mime = String(mimeType || '').toLowerCase();
        const ext = name.includes('.') ? name.split('.').pop() : '';

        if (mime.startsWith('video/') || ['mp4', 'webm', 'ogg', 'mov', 'm4v'].includes(ext)) {
            return 'video_url';
        }
        if (mime === 'application/pdf' || ext === 'pdf') {
            return 'pdf_url';
        }
        if (
            mime.includes('powerpoint') ||
            mime.includes('presentation') ||
            ['ppt', 'pptx', 'pps', 'ppsx'].includes(ext)
        ) {
            return 'ppt_url';
        }
        return 'external_link';
    }

    async function uploadLessonFile(moduleId, resourceId) {
        const row = getResourceRow(moduleId, resourceId);
        if (!row) {
            toast('Lesson item not found', 'error');
            return;
        }

        const fileInput = row.querySelector('.lesson-file');
        const uploadStatus = row.querySelector('.resource-upload-status');
        const urlField = row.querySelector('.lesson-url');
        const contentField = row.querySelector('.lesson-content');
        const typeField = row.querySelector('.lesson-type');
        const uploadBtn = row.querySelector('button[onclick*="uploadLessonFile"]');
        const file = fileInput?.files?.[0];

        if (!file) {
            toast('Select a file first', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        if (uploadStatus) uploadStatus.textContent = 'Uploading...';
        if (uploadBtn) {
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
        }

        try {
            const res = await fetch(`${API}/resources/upload-file`, {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });
            if (!res.ok) {
                let message = 'Failed to upload file';
                try {
                    const data = await res.json();
                    message = data?.detail || message;
                } catch { }
                throw new Error(message);
            }

            const data = await res.json();
            if (urlField) {
                urlField.value = data.file_url || '';
            } else {
                contentField.value = data.file_url || '';
            }
            if (typeField && !typeField.value.trim()) {
                typeField.value = detectLessonTypeFromFile(
                    data.original_filename || file.name,
                    data.content_type || file.type
                );
            }
            if (uploadStatus) uploadStatus.textContent = `Uploaded: ${data.original_filename || file.name}`;
            if (fileInput) fileInput.value = '';
            toast('File uploaded and lesson content updated');
        } catch (err) {
            if (uploadStatus) uploadStatus.textContent = err?.message || 'Upload failed';
            toast(err?.message || 'Failed to upload file', 'error');
        } finally {
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload file';
            }
        }
    }

    function removeResourceBlock(moduleId, resourceId) {
        const moduleEl = document.querySelector(`.resource-module-block[data-module-id="${moduleId}"]`);
        if (!moduleEl) return;
        const row = moduleEl.querySelector(`.resource-item-row[data-resource-id="${resourceId}"]`);
        if (!row) return;
        row.remove();
        reindexResourceLabels(moduleId);
    }

    function reindexResourceLabels(moduleId) {
        const moduleEl = document.querySelector(`.resource-module-block[data-module-id="${moduleId}"]`);
        if (!moduleEl) return;
        moduleEl.querySelectorAll('.resource-item-row').forEach((row, idx) => {
            const label = row.querySelector('.resource-item-label');
            if (label) label.textContent = `Lesson item ${idx + 1}`;
        });
    }

    function buildModulesPayload() {
        const moduleEls = Array.from(document.querySelectorAll('.resource-module-block'));
        if (!moduleEls.length) {
            throw new Error('Add at least one module.');
        }

        return moduleEls.map((moduleEl, moduleIndex) => {
            const moduleTitle = moduleEl.querySelector('.module-title')?.value.trim() || '';
            const moduleDescription = moduleEl.querySelector('.module-description')?.value.trim() || '';
            if (!moduleTitle) {
                throw new Error(`Module ${moduleIndex + 1} needs a title.`);
            }

            const lessonEls = Array.from(moduleEl.querySelectorAll('.resource-item-row'));
            if (!lessonEls.length) {
                throw new Error(`Module "${moduleTitle}" must include at least one lesson.`);
            }

            const lessons = lessonEls.map((lessonEl, lessonIndex) => {
                const title = lessonEl.querySelector('.lesson-title')?.value.trim() || '';
                const contentType = lessonEl.querySelector('.lesson-type')?.value.trim() || 'text';
                const primaryUrl = lessonEl.querySelector('.lesson-url')?.value.trim() || '';
                const notes = lessonEl.querySelector('.lesson-notes')?.value.trim() || '';
                const content = lessonEl.querySelector('.lesson-content')?.value.trim() || '';
                const readingTimeRaw = lessonEl.querySelector('.lesson-reading-time')?.value;
                const readingTime = readingTimeRaw ? parseInt(readingTimeRaw, 10) : null;

                if (!title) {
                    throw new Error(`Lesson ${lessonIndex + 1} in module "${moduleTitle}" needs a title.`);
                }
                if (contentType === 'video_url' && !primaryUrl) {
                    throw new Error(`Lesson "${title}" requires a video URL.`);
                }
                if ((contentType === 'external_link' || contentType === 'pdf_url' || contentType === 'ppt_url') && !primaryUrl) {
                    throw new Error(`Lesson "${title}" requires a resource URL.`);
                }
                if ((contentType === 'text' || contentType === 'html') && !content) {
                    throw new Error(`Lesson "${title}" requires body content.`);
                }

                return {
                    title,
                    content_type: contentType,
                    content: content || (contentType === 'resume_upload' ? 'Upload your resume and receive AI feedback.' : ''),
                    video_url: contentType === 'video_url' ? (primaryUrl || null) : null,
                    resource_url: (contentType === 'external_link' || contentType === 'pdf_url' || contentType === 'ppt_url') ? (primaryUrl || null) : null,
                    notes: notes || null,
                    reading_time_minutes: Number.isFinite(readingTime) ? readingTime : null
                };
            });

            return {
                title: moduleTitle,
                description: moduleDescription || null,
                lessons
            };
        });
    }

    async function handleCreateResource(e) {
        e.preventDefault();
        const btn = document.getElementById('resSubmit');
        const isEdit = Boolean(editingResourceId);
        btn.disabled = true;
        btn.textContent = isEdit ? 'Saving...' : 'Creating...';

        try {
            const payload = {
                title: document.getElementById('resTitle').value.trim(),
                description: document.getElementById('resDesc').value.trim(),
                category: document.getElementById('resCategory').value.trim(),
                level: document.getElementById('resLevel').value.trim() || null,
                icon: document.getElementById('resIcon').value.trim() || null,
                tags: normalizeTags(document.getElementById('resTags').value),
                estimated_duration_minutes: parseInt(document.getElementById('resDuration').value, 10) || null,
                external_url: document.getElementById('resUrl').value.trim() || null,
                is_published: document.getElementById('resPublished').checked,
                is_locked: document.getElementById('resLocked').checked,
                modules: buildModulesPayload()
            };

            const endpoint = isEdit ? `${API}/resources/${editingResourceId}` : `${API}/resources`;
            const method = isEdit ? 'PUT' : 'POST';

            const res = await fetch(endpoint, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                credentials: 'include'
            });

            if (!res.ok) {
                let message = isEdit ? 'Failed to update resource' : 'Failed to create resource';
                try {
                    const data = await res.json();
                    message = data?.detail || message;
                } catch { }
                throw new Error(message);
            }
            toast(isEdit ? 'Resource updated successfully!' : 'Resource created successfully!');
            closeResourceModal();
            await loadResources();
            loadDashboard();
        } catch (err) {
            toast(err?.message || 'Failed to save resource', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save Resource';
        }
    }

    let allResources = [];
    async function loadResources() {
        try {
            const res = await fetch(`${API}/resources?limit=200`, { credentials: 'include' });
            if (!res.ok) throw new Error();
            const d = await res.json();
            allResources = d.resources;
            renderResources(allResources);
        } catch { toast('Failed to load resources', 'error'); }
    }

    function renderResources(items) {
        const tbody = document.getElementById('resourcesTableBody');
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="9"><div class="admin-empty"><div class="admin-empty-icon">📚</div><div class="admin-empty-title">No resources yet</div></div></td></tr>';
            return;
        }
        tbody.innerHTML = items.map(r => {
            const tags = Array.isArray(r.tags) ? r.tags : [];
            const searchText = [r.title, r.category, r.level, tags.join(' '), r.description].filter(Boolean).join(' ').toLowerCase();
            const safeSearch = searchText.replace(/"/g, '&quot;');
            return `<tr data-search="${safeSearch}">
    <td><strong>${esc(r.title)}</strong></td>
    <td>${esc(r.category)}</td>
    <td>${esc(r.level) || '—'}</td>
    <td>${r.estimated_duration_minutes ? `${r.estimated_duration_minutes} min` : '—'}</td>
    <td>${tags.length ? esc(tags.join(', ')) : '—'}</td>
    <td><span class="admin-badge ${r.is_published ? 'published' : 'draft'}">${r.is_published ? '● Published' : '● Draft'}</span></td>
    <td><span class="admin-badge ${r.is_locked ? 'locked' : 'unlocked'}">${r.is_locked ? '🔒 Locked' : '🔓 Unlocked'}</span></td>
    <td>${formatDate(r.created_at)}</td>
    <td>
      <div class="admin-actions-cell">
        <button class="admin-btn-icon" title="Edit resource" onclick="openEditResourceModal('${r.id}')">✏️</button>
        <button class="admin-btn-icon" title="Toggle publish" onclick="toggleResourcePublished('${r.id}')">
          ${r.is_published ? '📤' : '📥'}
        </button>
        <button class="admin-btn-icon" title="Toggle lock" onclick="toggleResourceLocked('${r.id}')">
          ${r.is_locked ? '🔓' : '🔒'}
        </button>
        <button class="admin-btn-icon danger" title="Delete" onclick="deleteResource('${r.id}','${esc(r.title)}')">🗑️</button>
      </div>
    </td>
  </tr>`;
        }).join('');
    }

    async function toggleResourcePublished(id) {
        try {
            const res = await fetch(`${API}/resources/${id}/toggle-published`, { method: 'PATCH', credentials: 'include' });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data?.detail || 'Failed to toggle publish state');
            }
            const d = await res.json();
            toast(`Resource is now ${d.is_published ? 'published' : 'unpublished'}`);
            await loadResources();
        } catch (e) { toast(e?.message || 'Failed', 'error'); }
    }

    async function toggleResourceLocked(id) {
        try {
            const res = await fetch(`${API}/resources/${id}/toggle-locked`, { method: 'PATCH', credentials: 'include' });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data?.detail || 'Failed to toggle lock state');
            }
            const d = await res.json();
            toast(`Resource is now ${d.is_locked ? 'locked' : 'unlocked'}`);
            await loadResources();
        } catch (e) { toast(e?.message || 'Failed', 'error'); }
    }

    async function deleteResource(id, title) {
        openConfirm('Delete Resource', `Delete "${title}" and all its modules/lessons? This cannot be undone.`, async () => {
            try {
                const res = await fetch(`${API}/resources/${id}`, { method: 'DELETE', credentials: 'include' });
                if (!res.ok) throw new Error();
                toast(`Resource deleted`);
                await loadResources();
                loadDashboard();
            } catch { toast('Failed to delete', 'error'); }
        });
    }

    // ── Table Search / Filter ─────────────────────────────────────
    function filterTable(section) {
        const input = document.getElementById(`search${section.charAt(0).toUpperCase() + section.slice(1)}`);
        const q = (input?.value || '').toLowerCase();
        const tbody = document.getElementById(`${section}TableBody`);
        tbody.querySelectorAll('tr[data-search]').forEach(tr => {
            tr.style.display = (tr.dataset.search || '').includes(q) ? '' : 'none';
        });
    }

    // ── Identify admin user ───────────────────────────────────────
    async function loadAdminInfo() {
        try {
            const res = await fetch('/api/v1/users/me', { credentials: 'include' });
            if (res.ok) {
                const u = await res.json();
                const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.email;
                document.getElementById('adminName').textContent = name;
                document.getElementById('adminAvatar').textContent = (name[0] || 'A').toUpperCase();
            }
        } catch { }
    }

    // ── Init ──────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        sectionLoaded['dashboard'] = true;
        loadDashboard();
        loadAdminInfo();
    });

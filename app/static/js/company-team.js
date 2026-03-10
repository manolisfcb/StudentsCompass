const recruiterList = document.getElementById('recruiter-list');
const recruiterForm = document.getElementById('recruiter-form');
const recruiterFeedback = document.getElementById('recruiter-feedback');
const recruiterIdInput = document.getElementById('recruiter-id');
const recruiterFirstNameInput = document.getElementById('recruiter-first-name');
const recruiterLastNameInput = document.getElementById('recruiter-last-name');
const recruiterEmailInput = document.getElementById('recruiter-email');
const recruiterPasswordInput = document.getElementById('recruiter-password');
const recruiterRoleInput = document.getElementById('recruiter-role');
const recruiterActiveInput = document.getElementById('recruiter-active');
const recruiterSubmitButton = document.getElementById('recruiter-submit');

let recruitersCache = [];

function escapeRecruiterHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatRecruiterDate(isoDate) {
    if (!isoDate) {
        return '';
    }

    const date = new Date(isoDate);
    if (Number.isNaN(date.getTime())) {
        return '';
    }

    return date.toLocaleDateString();
}

function setRecruiterFeedback(message, tone = 'success') {
    recruiterFeedback.hidden = false;
    recruiterFeedback.className = `feedback-message ${tone}`;
    recruiterFeedback.textContent = message;
}

function clearRecruiterFeedback() {
    recruiterFeedback.hidden = true;
    recruiterFeedback.textContent = '';
    recruiterFeedback.className = 'feedback-message success';
}

function formatRecruiterName(recruiter) {
    const fullName = [recruiter.first_name, recruiter.last_name].filter(Boolean).join(' ').trim();
    return fullName || recruiter.email || 'Recruiter';
}

function normalizeRecruiterError(payload) {
    if (!payload) {
        return 'Request failed.';
    }

    if (typeof payload.detail === 'string') {
        return payload.detail;
    }

    if (Array.isArray(payload.detail)) {
        return payload.detail.map((item) => item.msg || item.message || 'Validation error').join(', ');
    }

    return 'Request failed.';
}

function renderRecruiters(recruiters) {
    if (!Array.isArray(recruiters) || recruiters.length === 0) {
        recruiterList.innerHTML = '<div class="recruiter-empty">No recruiters added yet.</div>';
        return;
    }

    recruiterList.innerHTML = recruiters.map((recruiter) => {
        const name = escapeRecruiterHtml(formatRecruiterName(recruiter));
        const role = escapeRecruiterHtml(recruiter.role || 'recruiter');
        const email = escapeRecruiterHtml(recruiter.email || '');
        const activeLabel = recruiter.is_active ? 'Active' : 'Inactive';
        const joinedAt = formatRecruiterDate(recruiter.created_at);
        const recruiterId = escapeRecruiterHtml(recruiter.id);

        return `
            <div class="recruiter-row">
                <div class="recruiter-details">
                    <div class="recruiter-name">${name}</div>
                    <div class="recruiter-meta">
                        <span>${email}</span>
                        <span class="badge role-${role}">${role}</span>
                        <span class="badge status-${recruiter.is_active ? 'active' : 'inactive'}">${activeLabel}</span>
                        <span>${joinedAt ? `Joined ${joinedAt}` : 'Recently added'}</span>
                    </div>
                </div>
                <div class="recruiter-row-actions">
                    <button class="btn btn-secondary" type="button" data-action="edit-recruiter" data-recruiter-id="${recruiterId}">Edit</button>
                    <button class="btn btn-danger" type="button" data-action="delete-recruiter" data-recruiter-id="${recruiterId}">Delete</button>
                </div>
            </div>
        `;
    }).join('');
}

async function loadRecruiters() {
    try {
        const response = await fetch('/api/v1/companies/me/recruiters', {
            credentials: 'include',
        });

        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(normalizeRecruiterError(errorPayload));
        }

        recruitersCache = await response.json();
        renderRecruiters(recruitersCache);
    } catch (error) {
        recruiterList.innerHTML = `<div class="recruiter-empty">${escapeRecruiterHtml(error.message || 'Unable to load recruiters.')}</div>`;
    }
}

function resetRecruiterForm(clearFeedback = true) {
    recruiterForm.reset();
    recruiterIdInput.value = '';
    recruiterRoleInput.value = 'recruiter';
    recruiterActiveInput.checked = true;
    recruiterActiveInput.disabled = true;
    recruiterPasswordInput.required = false;
    recruiterSubmitButton.textContent = 'Add Recruiter';

    if (clearFeedback) {
        clearRecruiterFeedback();
    }
}

function editRecruiter(recruiterId) {
    const recruiter = recruitersCache.find((item) => item.id === recruiterId);
    if (!recruiter) {
        return;
    }

    recruiterIdInput.value = recruiter.id;
    recruiterFirstNameInput.value = recruiter.first_name || '';
    recruiterLastNameInput.value = recruiter.last_name || '';
    recruiterEmailInput.value = recruiter.email || '';
    recruiterRoleInput.value = recruiter.role || 'recruiter';
    recruiterPasswordInput.value = '';
    recruiterPasswordInput.required = false;
    recruiterActiveInput.disabled = false;
    recruiterActiveInput.checked = Boolean(recruiter.is_active);
    recruiterSubmitButton.textContent = 'Save Recruiter';
    clearRecruiterFeedback();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function deleteRecruiter(recruiterId) {
    const recruiter = recruitersCache.find((item) => item.id === recruiterId);
    const recruiterName = recruiter ? formatRecruiterName(recruiter) : 'this recruiter';
    if (!window.confirm(`Delete ${recruiterName}? This action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/companies/me/recruiters/${recruiterId}`, {
            method: 'DELETE',
            credentials: 'include',
        });

        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(normalizeRecruiterError(errorPayload));
        }

        resetRecruiterForm(false);
        await loadRecruiters();
        setRecruiterFeedback('Recruiter deleted successfully.');
    } catch (error) {
        setRecruiterFeedback(error.message || 'Unable to delete recruiter.', 'error');
    }
}

async function handleRecruiterSubmit(event) {
    event.preventDefault();
    clearRecruiterFeedback();

    const recruiterId = recruiterIdInput.value;
    const payload = {
        email: recruiterEmailInput.value.trim(),
        first_name: recruiterFirstNameInput.value.trim() || null,
        last_name: recruiterLastNameInput.value.trim() || null,
        role: recruiterRoleInput.value,
    };

    const password = recruiterPasswordInput.value;
    const isEdit = Boolean(recruiterId);

    if (!isEdit) {
        if (!password || password.length < 8) {
            setRecruiterFeedback('Password must be at least 8 characters long.', 'error');
            return;
        }
        payload.password = password;
    } else {
        payload.is_active = recruiterActiveInput.checked;
        if (password) {
            if (password.length < 8) {
                setRecruiterFeedback('Password must be at least 8 characters long.', 'error');
                return;
            }
            payload.password = password;
        }
    }

    try {
        const response = await fetch(
            isEdit ? `/api/v1/companies/me/recruiters/${recruiterId}` : '/api/v1/companies/me/recruiters',
            {
                method: isEdit ? 'PATCH' : 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            }
        );

        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(normalizeRecruiterError(errorPayload));
        }

        resetRecruiterForm(false);
        await loadRecruiters();
        setRecruiterFeedback(isEdit ? 'Recruiter updated successfully.' : 'Recruiter created successfully.');
    } catch (error) {
        setRecruiterFeedback(error.message || 'Unable to save recruiter.', 'error');
    }
}

document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) {
        return;
    }

    const action = button.dataset.action;
    if (action === 'reset-form') {
        resetRecruiterForm();
        return;
    }

    if (action === 'edit-recruiter') {
        editRecruiter(button.dataset.recruiterId);
        return;
    }

    if (action === 'delete-recruiter') {
        deleteRecruiter(button.dataset.recruiterId);
    }
});

recruiterForm.addEventListener('submit', handleRecruiterSubmit);

document.addEventListener('DOMContentLoaded', () => {
    resetRecruiterForm();
    loadRecruiters();
});

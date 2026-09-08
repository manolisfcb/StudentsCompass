document.addEventListener('DOMContentLoaded', () => {
  const heading = document.getElementById('selected-candidates-heading');
  const candidatesList = document.getElementById('selected-candidates-list');
  const candidatesMessage = document.getElementById('selected-candidates-message');
  const jobFilter = document.getElementById('selected-candidates-job-filter');
  const statusFilter = document.getElementById('selected-candidates-status-filter');
  const refreshButton = document.getElementById('refresh-selected-candidates-btn');
  const previewOverlay = document.getElementById('selected-resume-preview-overlay');
  const previewFrame = document.getElementById('selected-resume-preview-frame');
  const previewSubtitle = document.getElementById('selected-resume-preview-subtitle');
  const previewCloseButton = document.getElementById('selected-resume-preview-close');
  const interviewOverlay = document.getElementById('interview-availability-overlay');
  const interviewCloseButton = document.getElementById('interview-availability-close');
  const interviewCancelButton = document.getElementById('interview-availability-cancel');
  const interviewForm = document.getElementById('interview-availability-form');
  const interviewList = document.getElementById('interview-availability-list');
  const interviewNotes = document.getElementById('interview-availability-notes');
  const interviewAddSlotButton = document.getElementById('add-interview-slot-btn');
  const interviewSubmitButton = document.getElementById('interview-availability-submit');
  const inReviewCount = document.getElementById('pipeline-in-review-count');
  const interviewCount = document.getElementById('pipeline-interview-count');

  if (!heading || !candidatesList || !candidatesMessage || !jobFilter || !statusFilter || !refreshButton || !previewOverlay || !previewFrame || !previewSubtitle || !previewCloseButton || !interviewOverlay || !interviewCloseButton || !interviewCancelButton || !interviewForm || !interviewList || !interviewNotes || !interviewAddSlotButton || !interviewSubmitButton || !inReviewCount || !interviewCount) {
    return;
  }

  const selectedStatuses = ['in_review', 'interview', 'offer'];
  let selectedApplicants = [];
  let selectedJobId = '';
  let activeInterviewApplicationId = '';

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDate(isoDate) {
    if (!isoDate) {
      return '';
    }
    const date = new Date(isoDate);
    if (Number.isNaN(date.getTime())) {
      return '';
    }
    return date.toLocaleDateString();
  }

  function formatApplicantStatus(status) {
    return String(status || 'in_review').replace(/_/g, ' ');
  }

  function formatMatchStrength(strength) {
    return String(strength || 'match').replace(/_/g, ' ');
  }

  function showMessage(message, variant = 'success') {
    candidatesMessage.textContent = message;
    candidatesMessage.className = `dashboard-message active ${variant}`;
  }

  function clearMessage() {
    candidatesMessage.textContent = '';
    candidatesMessage.className = 'dashboard-message';
  }

  function setBodyOverflow() {
    const hasActiveOverlay = previewOverlay.classList.contains('active') || interviewOverlay.classList.contains('active');
    document.body.style.overflow = hasActiveOverlay ? 'hidden' : '';
  }

  function openResumePreview(url, filename) {
    previewFrame.src = url;
    previewSubtitle.textContent = filename ? `Previewing ${filename}` : 'Previewing candidate resume.';
    previewOverlay.classList.add('active');
    previewOverlay.setAttribute('aria-hidden', 'false');
    setBodyOverflow();
  }

  function closeResumePreview() {
    previewFrame.src = '';
    previewOverlay.classList.remove('active');
    previewOverlay.setAttribute('aria-hidden', 'true');
    setBodyOverflow();
  }

  function buildInterviewSlotRow(index, slot = null) {
    const startValue = slot?.starts_at ? slot.starts_at.slice(0, 16) : '';
    const endValue = slot?.ends_at ? slot.ends_at.slice(0, 16) : '';
    const notesValue = slot?.notes || '';
    return `
      <div class="interview-slot-row" data-interview-slot-row="${index}">
        <div class="form-field">
          <label>Start</label>
          <input type="datetime-local" name="slot-start" value="${escapeHtml(startValue)}" required>
        </div>
        <div class="form-field">
          <label>End</label>
          <input type="datetime-local" name="slot-end" value="${escapeHtml(endValue)}" required>
        </div>
        <div class="form-field">
          <label>Slot notes</label>
          <input type="text" name="slot-notes" value="${escapeHtml(notesValue)}" placeholder="Optional note for this slot">
        </div>
        <button type="button" class="applicant-icon-btn applicant-icon-btn-reset" data-remove-slot="${index}" title="Remove slot" aria-label="Remove slot">−</button>
      </div>
    `;
  }

  function renderInterviewSlotRows(slots = []) {
    const sourceSlots = slots.length ? slots : [null];
    interviewList.innerHTML = sourceSlots.map((slot, index) => buildInterviewSlotRow(index, slot)).join('');
  }

  function openInterviewModal(applicationId, existingSlots = []) {
    activeInterviewApplicationId = applicationId;
    interviewNotes.value = '';
    renderInterviewSlotRows(existingSlots);
    interviewOverlay.classList.add('active');
    interviewOverlay.setAttribute('aria-hidden', 'false');
    setBodyOverflow();
  }

  function closeInterviewModal() {
    activeInterviewApplicationId = '';
    interviewForm.reset();
    interviewOverlay.classList.remove('active');
    interviewOverlay.setAttribute('aria-hidden', 'true');
    setBodyOverflow();
  }

  async function parseErrorMessage(response, fallbackMessage) {
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        return payload.detail.trim();
      }
    } catch (_) {
      // Keep fallback message.
    }
    return fallbackMessage;
  }

  async function fetchDashboardData() {
    const response = await fetch('/api/v1/company_dashboard', {
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return null;
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to load company dashboard.'));
    }

    return response.json();
  }

  async function fetchJobPostings() {
    const response = await fetch('/api/v1/companies/me/job-postings', {
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return [];
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to load company job postings.'));
    }

    return response.json();
  }

  async function fetchSelectedApplicants(jobId = '') {
    const searchParams = new URLSearchParams();
    if (jobId) {
      searchParams.set('job_posting_id', jobId);
    }
    selectedStatuses.forEach((status) => searchParams.append('status', status));

    const response = await fetch(`/api/v1/companies/me/applicants?${searchParams.toString()}`, {
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return [];
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to load selected candidates.'));
    }

    return response.json();
  }

  async function updateApplicantStatusRequest(applicationId, payload) {
    const response = await fetch(`/api/v1/companies/me/applicants/${applicationId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    });

    if (response.status === 401 || response.status === 403) {
      throw new Error(await parseErrorMessage(response, 'You do not have permission to update this applicant.'));
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to update applicant stage.'));
    }

    return response.json();
  }

  async function publishInterviewAvailabilitiesRequest(applicationId, payload) {
    const response = await fetch(`/api/v1/companies/me/applicants/${applicationId}/interview-availabilities`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    });

    if (response.status === 401 || response.status === 403) {
      throw new Error(await parseErrorMessage(response, 'You do not have permission to share interview availability.'));
    }
    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to share interview availability.'));
    }
    return response.json();
  }

  function buildApplicantMatchBadge(application) {
    if (!application || !application.match_strength) {
      return '';
    }

    const matchStrength = application.match_strength;
    return `
      <span
        class="match-badge match-badge-${escapeHtml(matchStrength)}"
        title="${escapeHtml(formatMatchStrength(matchStrength))}"
        aria-label="${escapeHtml(formatMatchStrength(matchStrength))}"
      >
        ★
      </span>
    `;
  }

  function setJobFilterOptions(jobPostings) {
    const options = ['<option value="">All job postings</option>'].concat(
      (Array.isArray(jobPostings) ? jobPostings : []).map((job) => {
        return `<option value="${escapeHtml(job.id)}">${escapeHtml(job.title || 'Untitled role')}</option>`;
      })
    );
    jobFilter.innerHTML = options.join('');
    jobFilter.value = selectedJobId;
  }

  function updatePipelineStats(applicants) {
    const inReview = applicants.filter((item) => item?.application?.status === 'in_review').length;
    const interview = applicants.filter((item) => item?.application?.status === 'interview').length;
    inReviewCount.textContent = inReview;
    interviewCount.textContent = interview;
  }

  function getVisibleApplicants() {
    const stage = statusFilter.value;
    if (!stage) {
      return selectedApplicants;
    }
    return selectedApplicants.filter((item) => item?.application?.status === stage);
  }

  function renderApplicants(applicants) {
    if (!Array.isArray(applicants) || applicants.length === 0) {
      candidatesList.innerHTML = '<div class="applicant-empty">No selected candidates match this filter yet.</div>';
      return;
    }

    candidatesList.innerHTML = applicants.map((item) => {
      const application = item.application || {};
      const candidate = item.candidate || {};
      const resume = item.resume || null;
      const phone = candidate.phone || (resume ? resume.phone : null) || 'Not provided';
      const address = candidate.address || 'Address not provided';
      const summary = resume && resume.summary
        ? resume.summary
        : 'No AI resume summary is available yet for this candidate.';
      const previewButton = resume
        ? `<button type="button" class="applicant-link primary" data-preview-url="${escapeHtml(resume.preview_url)}" data-preview-name="${escapeHtml(resume.original_filename)}">Preview CV</button>`
        : '<span class="applicant-link" aria-disabled="true">No CV attached</span>';
      const downloadButton = resume
        ? `<a class="applicant-link" href="${escapeHtml(resume.download_url)}">Download CV</a>`
        : '';
      const matchBadge = buildApplicantMatchBadge(application);

      let pipelineButton = '';
      if (application.status === 'in_review' || application.status === 'interview') {
        const slotCount = Array.isArray(application.available_interview_slots) ? application.available_interview_slots.length : 0;
        const buttonTitle = slotCount > 0 ? 'Update interview availability' : 'Mark interview';
        pipelineButton = `
          <button
            type="button"
            class="applicant-icon-btn applicant-icon-btn-interview"
            data-open-interview-modal="${escapeHtml(application.id)}"
            data-application-id="${escapeHtml(application.id)}"
            title="${escapeHtml(buttonTitle)}"
            aria-label="${escapeHtml(buttonTitle)}"
          >
            🎙
          </button>
        `;
      } else if (application.status === 'offer') {
        pipelineButton = '<span class="applicant-selection-state applicant-selection-state-offer" aria-disabled="true">Offer</span>';
      }

      const selectedInterviewSlot = application.selected_interview_slot
        ? `<div class="interview-slot-summary"><strong>Interview confirmed:</strong> ${escapeHtml(formatDate(application.selected_interview_slot.starts_at))} ${escapeHtml(new Date(application.selected_interview_slot.starts_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }))}</div>`
        : '';
      const availabilitySummary = !selectedInterviewSlot && Array.isArray(application.available_interview_slots) && application.available_interview_slots.length
        ? `<div class="interview-slot-summary"><strong>${application.available_interview_slots.length}</strong> availability option(s) shared with the candidate.</div>`
        : '';

      return `
        <article class="applicant-card">
          <div class="applicant-head">
            <div>
              <p class="applicant-name">${escapeHtml(candidate.full_name || candidate.email || 'Candidate')}</p>
              <div class="applicant-meta">
                Applied for <strong>${escapeHtml(application.job_title || 'Untitled role')}</strong> on ${escapeHtml(formatDate(application.application_date))}
              </div>
            </div>
            <div class="applicant-head-badges">
              <span class="status-pill status-pill-${escapeHtml(application.status || 'in_review')}">${escapeHtml(formatApplicantStatus(application.status))}</span>
              ${matchBadge}
            </div>
          </div>
          <div class="applicant-contact">
            <span><strong>Email:</strong> ${escapeHtml(candidate.email || 'Not provided')}</span>
            <span><strong>Phone:</strong> ${escapeHtml(phone)}</span>
            <span><strong>Address:</strong> ${escapeHtml(address)}</span>
          </div>
          <div class="applicant-summary">${escapeHtml(summary)}</div>
          ${selectedInterviewSlot}
          ${availabilitySummary}
          <div class="applicant-actions">
            ${previewButton}
            ${downloadButton}
            ${pipelineButton}
          </div>
        </article>
      `;
    }).join('');
  }

  function renderVisibleApplicants() {
    renderApplicants(getVisibleApplicants());
  }

  async function loadSelectedCandidates() {
    clearMessage();
    candidatesList.innerHTML = '<div class="applicant-empty">Loading selected candidates...</div>';

    try {
      const [dashboardData, jobPostings, applicants] = await Promise.all([
        fetchDashboardData(),
        fetchJobPostings(),
        fetchSelectedApplicants(selectedJobId),
      ]);

      if (dashboardData?.company?.company_name) {
        heading.textContent = `${dashboardData.company.company_name} Selected Candidates`;
      }

      setJobFilterOptions(jobPostings);
      selectedApplicants = Array.isArray(applicants) ? applicants : [];
      updatePipelineStats(selectedApplicants);
      renderVisibleApplicants();
    } catch (error) {
      candidatesList.innerHTML = `<div class="applicant-empty">${escapeHtml(error?.message || 'Failed to load selected candidates.')}</div>`;
    }
  }

  jobFilter.addEventListener('change', async () => {
    selectedJobId = jobFilter.value || '';
    await loadSelectedCandidates();
  });

  statusFilter.addEventListener('change', () => {
    renderVisibleApplicants();
  });

  refreshButton.addEventListener('click', () => loadSelectedCandidates());

  candidatesList.addEventListener('click', async (event) => {
    const previewButton = event.target.closest('[data-preview-url]');
    if (previewButton) {
      const previewUrl = previewButton.getAttribute('data-preview-url');
      const previewName = previewButton.getAttribute('data-preview-name');
      if (!previewUrl) {
        return;
      }
      openResumePreview(previewUrl, previewName || '');
      return;
    }

    const interviewButton = event.target.closest('[data-open-interview-modal]');
    if (interviewButton) {
      const applicationId = interviewButton.getAttribute('data-application-id');
      if (!applicationId) {
        return;
      }
      const applicationItem = selectedApplicants.find((item) => item?.application?.id === applicationId);
      const existingSlots = applicationItem?.application?.available_interview_slots || [];
      const notes = applicationItem?.application?.notes || '';
      interviewNotes.value = notes;
      openInterviewModal(applicationId, existingSlots);
      return;
    }

    const updateButton = event.target.closest('[data-application-status-update]');
    if (!updateButton) {
      return;
    }

    const applicationId = updateButton.getAttribute('data-application-id');
    const nextStatus = updateButton.getAttribute('data-application-status-update');
    if (!applicationId || !nextStatus) {
      return;
    }

    updateButton.disabled = true;

    try {
      await updateApplicantStatusRequest(applicationId, {
        status: nextStatus,
        notes: 'Interview stage marked by company recruiter.',
      });
      showMessage('Candidate marked for interview. The student dashboard now reflects the interview stage.', 'success');
      await loadSelectedCandidates();
    } catch (error) {
      showMessage(error?.message || 'Failed to mark interview.', 'error');
      updateButton.disabled = false;
    }
  });

  interviewAddSlotButton.addEventListener('click', () => {
    const nextIndex = interviewList.querySelectorAll('[data-interview-slot-row]').length;
    interviewList.insertAdjacentHTML('beforeend', buildInterviewSlotRow(nextIndex));
  });

  interviewList.addEventListener('click', (event) => {
    const removeButton = event.target.closest('[data-remove-slot]');
    if (!removeButton) {
      return;
    }
    const row = removeButton.closest('[data-interview-slot-row]');
    if (row && interviewList.querySelectorAll('[data-interview-slot-row]').length > 1) {
      row.remove();
    }
  });

  interviewForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!activeInterviewApplicationId) {
      return;
    }

    interviewSubmitButton.disabled = true;
    try {
      const slots = Array.from(interviewList.querySelectorAll('[data-interview-slot-row]')).map((row) => {
        const startValue = row.querySelector('input[name="slot-start"]')?.value || '';
        const endValue = row.querySelector('input[name="slot-end"]')?.value || '';
        const notesValue = row.querySelector('input[name="slot-notes"]')?.value || '';
        return {
          starts_at: startValue,
          ends_at: endValue,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Toronto',
          notes: notesValue.trim() || null,
        };
      });

      if (!slots.length || slots.some((slot) => !slot.starts_at || !slot.ends_at || Number.isNaN(new Date(slot.starts_at).getTime()) || Number.isNaN(new Date(slot.ends_at).getTime()))) {
        throw new Error('Every interview slot needs a valid start and end date.');
      }

      await publishInterviewAvailabilitiesRequest(activeInterviewApplicationId, {
        slots,
        notes: interviewNotes.value.trim() || null,
      });
      closeInterviewModal();
      showMessage('Interview availability shared. The candidate now has the options in their applications area, and the email flow was queued in mock mode.', 'success');
      await loadSelectedCandidates();
    } catch (error) {
      showMessage(error?.message || 'Failed to share interview availability.', 'error');
    } finally {
      interviewSubmitButton.disabled = false;
    }
  });

  previewCloseButton.addEventListener('click', closeResumePreview);
  interviewCloseButton.addEventListener('click', closeInterviewModal);
  interviewCancelButton.addEventListener('click', closeInterviewModal);
  previewOverlay.addEventListener('click', (event) => {
    if (event.target === previewOverlay) {
      closeResumePreview();
    }
  });
  interviewOverlay.addEventListener('click', (event) => {
    if (event.target === interviewOverlay) {
      closeInterviewModal();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && previewOverlay.classList.contains('active')) {
      closeResumePreview();
      return;
    }
    if (event.key === 'Escape' && interviewOverlay.classList.contains('active')) {
      closeInterviewModal();
    }
  });

  loadSelectedCandidates();
});

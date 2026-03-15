document.addEventListener('DOMContentLoaded', () => {
  const welcomeHeading = document.getElementById('company-welcome');
  const jobList = document.getElementById('job-list');
  const dashboardMessage = document.getElementById('dashboard-message');
  const jobModalOverlay = document.getElementById('job-modal-overlay');
  const applicantsModalOverlay = document.getElementById('applicants-modal-overlay');
  const applicantsModalCloseBtn = document.getElementById('applicants-modal-close');
  const applicantsList = document.getElementById('applicants-list');
  const applicantsJobFilter = document.getElementById('applicants-job-filter');
  const refreshApplicantsBtn = document.getElementById('refresh-applicants-btn');
  const resumePreviewOverlay = document.getElementById('resume-preview-overlay');
  const resumePreviewCloseBtn = document.getElementById('resume-preview-close');
  const resumePreviewFrame = document.getElementById('resume-preview-frame');
  const resumePreviewSubtitle = document.getElementById('resume-preview-subtitle');
  const jobPostingForm = document.getElementById('job-posting-form');
  const jobModalCloseBtn = document.getElementById('job-modal-close');
  const jobFormCancelBtn = document.getElementById('job-form-cancel');
  const jobFormSubmitBtn = document.getElementById('job-form-submit');

  if (!welcomeHeading || !jobList || !dashboardMessage || !jobModalOverlay || !applicantsModalOverlay || !applicantsList || !applicantsJobFilter || !resumePreviewOverlay || !resumePreviewFrame || !jobPostingForm || !jobFormSubmitBtn) {
    return;
  }

  let dashboardJobPostings = [];
  let activeApplicantsJobId = '';

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
    return String(status || 'applied').replace(/_/g, ' ');
  }

  function formatMatchStrength(strength) {
    return String(strength || 'match').replace(/_/g, ' ');
  }

  function showMessage(message, variant = 'success') {
    dashboardMessage.textContent = message;
    dashboardMessage.className = `dashboard-message active ${variant}`;
  }

  function clearMessage() {
    dashboardMessage.textContent = '';
    dashboardMessage.className = 'dashboard-message';
  }

  function setBodyOverflow() {
    const hasOpenOverlay = (
      jobModalOverlay.classList.contains('active') ||
      applicantsModalOverlay.classList.contains('active') ||
      resumePreviewOverlay.classList.contains('active')
    );
    document.body.style.overflow = hasOpenOverlay ? 'hidden' : '';
  }

  function openJobPostingModal() {
    clearMessage();
    jobModalOverlay.classList.add('active');
    jobModalOverlay.setAttribute('aria-hidden', 'false');
    setBodyOverflow();
  }

  function closeJobPostingModal() {
    jobModalOverlay.classList.remove('active');
    jobModalOverlay.setAttribute('aria-hidden', 'true');
    setBodyOverflow();
  }

  function openApplicantsModal() {
    clearMessage();
    applicantsModalOverlay.classList.add('active');
    applicantsModalOverlay.setAttribute('aria-hidden', 'false');
    setBodyOverflow();
  }

  function closeApplicantsModal() {
    applicantsModalOverlay.classList.remove('active');
    applicantsModalOverlay.setAttribute('aria-hidden', 'true');
    setBodyOverflow();
  }

  function openResumePreview(url, filename) {
    resumePreviewFrame.src = url;
    resumePreviewSubtitle.textContent = filename ? `Previewing ${filename}` : 'Previewing candidate resume.';
    resumePreviewOverlay.classList.add('active');
    resumePreviewOverlay.setAttribute('aria-hidden', 'false');
    setBodyOverflow();
  }

  function closeResumePreview() {
    resumePreviewFrame.src = '';
    resumePreviewOverlay.classList.remove('active');
    resumePreviewOverlay.setAttribute('aria-hidden', 'true');
    setBodyOverflow();
  }

  function setApplicantsFilterOptions(jobPostings) {
    const selected = activeApplicantsJobId;
    const options = ['<option value="">All job postings</option>'].concat(
      jobPostings.map((job) => `<option value="${escapeHtml(job.id)}">${escapeHtml(job.title || 'Untitled role')}</option>`)
    );
    applicantsJobFilter.innerHTML = options.join('');
    applicantsJobFilter.value = selected || '';
  }

  function buildApplicantSelectionControls(application) {
    if (!application) {
      return '';
    }

    if (application.status === 'applied') {
      return `
        <div class="applicant-selection-controls">
          <button
            type="button"
            class="applicant-icon-btn applicant-icon-btn-select"
            title="Select candidate"
            aria-label="Select candidate"
            data-application-status-update="in_review"
            data-application-id="${escapeHtml(application.id)}"
          >
            ✓
          </button>
        </div>
      `;
    }

    if (application.status === 'in_review' || application.status === 'interview') {
      return `
        <div class="applicant-selection-controls">
          <span class="applicant-selection-state" title="Selected candidate">Selected</span>
          <button
            type="button"
            class="applicant-icon-btn applicant-icon-btn-reset"
            title="Unselect candidate"
            aria-label="Unselect candidate"
            data-application-status-update="applied"
            data-application-id="${escapeHtml(application.id)}"
          >
            ↺
          </button>
        </div>
      `;
    }

    return '';
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

  function renderApplicants(applicants) {
    if (!Array.isArray(applicants) || applicants.length === 0) {
      applicantsList.innerHTML = '<div class="applicant-empty">No applicants found for this selection yet.</div>';
      return;
    }

    applicantsList.innerHTML = applicants.map((item) => {
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
      const selectionControls = buildApplicantSelectionControls(application);
      const matchBadge = buildApplicantMatchBadge(application);

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
              <span class="status-pill status-pill-${escapeHtml(application.status || 'applied')}">${escapeHtml(formatApplicantStatus(application.status))}</span>
              ${matchBadge}
            </div>
          </div>
          <div class="applicant-contact">
            <span><strong>Email:</strong> ${escapeHtml(candidate.email || 'Not provided')}</span>
            <span><strong>Phone:</strong> ${escapeHtml(phone)}</span>
            <span><strong>Address:</strong> ${escapeHtml(address)}</span>
          </div>
          <div class="applicant-summary">${escapeHtml(summary)}</div>
          <div class="applicant-actions">
            ${previewButton}
            ${downloadButton}
          </div>
          ${selectionControls}
        </article>
      `;
    }).join('');
  }

  function renderJobPostings(jobPostings) {
    dashboardJobPostings = Array.isArray(jobPostings) ? jobPostings : [];
    setApplicantsFilterOptions(dashboardJobPostings);

    if (!Array.isArray(jobPostings) || jobPostings.length === 0) {
      jobList.innerHTML = `
        <li class="job-item">
          <div>
            <div class="job-title">No job postings yet</div>
            <div class="job-info">Create your first job posting to attract talented students</div>
          </div>
        </li>
      `;
      return;
    }

    jobList.innerHTML = jobPostings.map((job) => {
      const location = job.location ? escapeHtml(job.location) : 'Location not specified';
      const postedAt = formatDate(job.created_at);
      const postedLabel = postedAt ? `Posted ${postedAt}` : 'Recently posted';
      const applicationCount = Number(job.application_count || 0);
      const applicationsText = `${applicationCount} application${applicationCount === 1 ? '' : 's'}`;

      return `
        <li class="job-item">
          <div>
            <div class="job-title">${escapeHtml(job.title || 'Untitled role')}</div>
            <div class="job-info">${location} • ${applicationsText} • ${postedLabel}</div>
          </div>
          <div class="job-item-actions">
            <button
              class="job-status job-icon-btn ${escapeHtml(job.status || 'closed')}"
              type="button"
              data-job-toggle="${escapeHtml(job.id)}"
              data-job-active="${job.is_active ? 'true' : 'false'}"
              title="${job.is_active ? 'Deactivate this posting and hide it from the student job board' : 'Activate this posting and publish it to the student job board'}"
              aria-label="${job.is_active ? 'Deactivate posting' : 'Activate posting'}"
            >
              <span class="job-icon-symbol">⏻</span>
            </button>
            <button
              class="job-icon-btn"
              type="button"
              data-view-applicants="${escapeHtml(job.id)}"
              title="View applicants"
              aria-label="View applicants"
            >
              <span class="job-icon-symbol">👥</span>
            </button>
            <button
              class="job-delete-btn job-icon-btn"
              type="button"
              data-job-delete="${escapeHtml(job.id)}"
              title="Delete posting"
              aria-label="Delete posting"
            >
              <span class="job-icon-symbol">🗑</span>
            </button>
          </div>
        </li>
      `;
    }).join('');
  }

  async function parseErrorMessage(response, fallbackMessage) {
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        return payload.detail.trim();
      }
    } catch (_) {
      // Ignore parsing failure and keep fallback.
    }
    return fallbackMessage;
  }

  async function fetchApplicants(jobId = '') {
    const searchParams = new URLSearchParams();
    if (jobId) {
      searchParams.set('job_posting_id', jobId);
    }
    const query = searchParams.toString();
    const response = await fetch(`/api/v1/companies/me/applicants${query ? `?${query}` : ''}`, {
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return [];
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to load applicants.'));
    }

    return response.json();
  }

  async function fetchCompanyJobPostings() {
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
      const errorMessage = await parseErrorMessage(response, 'You do not have permission to update this applicant.');
      throw new Error(errorMessage);
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to update applicant status.'));
    }

    return response.json();
  }

  async function loadApplicants(jobId = '') {
    activeApplicantsJobId = jobId || '';
    applicantsList.innerHTML = '<div class="applicant-empty">Loading applicants...</div>';

    try {
      const companyJobs = await fetchCompanyJobPostings();
      dashboardJobPostings = Array.isArray(companyJobs) ? companyJobs : dashboardJobPostings;
      setApplicantsFilterOptions(dashboardJobPostings);
      applicantsJobFilter.value = activeApplicantsJobId;
      const applicants = await fetchApplicants(activeApplicantsJobId);
      renderApplicants(applicants);
    } catch (error) {
      applicantsList.innerHTML = `<div class="applicant-empty">${escapeHtml(error?.message || 'Failed to load applicants.')}</div>`;
    }
  }

  async function createJobPostingRequest(payload) {
    const response = await fetch('/api/v1/companies/me/job-postings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return null;
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to create job posting.'));
    }

    return response.json();
  }

  async function updateJobPostingRequest(jobId, payload) {
    const response = await fetch(`/api/v1/companies/me/job-postings/${jobId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return null;
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to update job posting.'));
    }

    return response.json();
  }

  async function deleteJobPostingRequest(jobId) {
    const response = await fetch(`/api/v1/companies/me/job-postings/${jobId}`, {
      method: 'DELETE',
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      window.location.href = '/login';
      return false;
    }

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, 'Failed to delete job posting.'));
    }

    return true;
  }

  async function loadDashboardData() {
    try {
      const response = await fetch('/api/v1/company_dashboard', {
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        const companyName = data.company && data.company.company_name ? data.company.company_name : 'Company';
        welcomeHeading.textContent = `${companyName} Dashboard`;

        document.getElementById('active-jobs').textContent = data.stats.active_job_postings ?? 0;
        document.getElementById('total-applications').textContent = data.stats.total_applications ?? 0;
        document.getElementById('scheduled-interviews').textContent = data.stats.scheduled_interviews ?? 0;
        document.getElementById('shortlisted').textContent = data.stats.shortlisted ?? 0;

        renderJobPostings(data.recent_job_postings);
        return;
      }

      if (response.status === 401 || response.status === 403) {
        window.location.href = '/login';
        return;
      }

      console.error('Failed to load company dashboard data');
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    }
  }

  function createJobPosting() {
    openJobPostingModal();
  }

  function viewAllJobs() {
    window.location.href = '/jobs';
  }

  function viewApplications() {
    openApplicantsModal();
    loadApplicants('');
  }

  function selectedCandidates() {
    window.location.href = '/company-candidates';
  }

  function companyProfile() {
    alert('Company profile feature coming soon!');
  }

  function handleDashboardAction(action) {
    if (action === 'create-job') {
      createJobPosting();
      return;
    }
    if (action === 'view-jobs') {
      viewAllJobs();
      return;
    }
    if (action === 'view-applications') {
      viewApplications();
      return;
    }
    if (action === 'selected-candidates') {
      selectedCandidates();
      return;
    }
    if (action === 'company-profile') {
      companyProfile();
    }
  }

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-dashboard-action]');
    if (!trigger) {
      return;
    }
    handleDashboardAction(trigger.dataset.dashboardAction);
  });

  document.addEventListener('keydown', (event) => {
    const trigger = event.target.closest('[data-dashboard-action]');
    if (!trigger || (event.key !== 'Enter' && event.key !== ' ')) {
      return;
    }
    event.preventDefault();
    handleDashboardAction(trigger.dataset.dashboardAction);
  });

  jobPostingForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessage();
    jobFormSubmitBtn.disabled = true;

    const formData = new FormData(jobPostingForm);
    const payload = {
      title: String(formData.get('title') || '').trim(),
      description: String(formData.get('description') || '').trim() || null,
      requirements: String(formData.get('requirements') || '').trim() || null,
      responsibilities: String(formData.get('responsibilities') || '').trim() || null,
      location: String(formData.get('location') || '').trim() || null,
      job_type: String(formData.get('job_type') || '').trim() || null,
      workplace_type: String(formData.get('workplace_type') || '').trim() || null,
      seniority_level: String(formData.get('seniority_level') || '').trim() || null,
      salary_range: String(formData.get('salary_range') || '').trim() || null,
      benefits: String(formData.get('benefits') || '').trim() || null,
      listed_context: String(formData.get('listed_context') || '').trim() || null,
      source_context: String(formData.get('source_context') || '').trim() || null,
      application_url: String(formData.get('application_url') || '').trim() || null,
      is_active: document.getElementById('job-is-active-input').checked,
      expires_at: String(formData.get('expires_at') || '').trim() ? `${formData.get('expires_at')}T23:59:59` : null,
    };

    if (!payload.title) {
      showMessage('Job title is required.', 'error');
      jobFormSubmitBtn.disabled = false;
      return;
    }

    try {
      await createJobPostingRequest(payload);
      closeJobPostingModal();
      jobPostingForm.reset();
      document.getElementById('job-is-active-input').checked = true;
      showMessage('Job posting published. Students can now see it on the job board.', 'success');
      await loadDashboardData();
    } catch (error) {
      showMessage(error?.message || 'Failed to create job posting.', 'error');
    } finally {
      jobFormSubmitBtn.disabled = false;
    }
  });

  jobModalCloseBtn.addEventListener('click', closeJobPostingModal);
  jobFormCancelBtn.addEventListener('click', closeJobPostingModal);
  applicantsModalCloseBtn.addEventListener('click', closeApplicantsModal);
  resumePreviewCloseBtn.addEventListener('click', closeResumePreview);
  refreshApplicantsBtn.addEventListener('click', () => loadApplicants(activeApplicantsJobId));
  applicantsJobFilter.addEventListener('change', () => loadApplicants(applicantsJobFilter.value));

  jobModalOverlay.addEventListener('click', (event) => {
    if (event.target === jobModalOverlay) {
      closeJobPostingModal();
    }
  });
  applicantsModalOverlay.addEventListener('click', (event) => {
    if (event.target === applicantsModalOverlay) {
      closeApplicantsModal();
    }
  });
  resumePreviewOverlay.addEventListener('click', (event) => {
    if (event.target === resumePreviewOverlay) {
      closeResumePreview();
    }
  });

  jobList.addEventListener('click', async (event) => {
    const applicantsButton = event.target.closest('[data-view-applicants]');
    if (applicantsButton) {
      const jobId = applicantsButton.getAttribute('data-view-applicants') || '';
      openApplicantsModal();
      await loadApplicants(jobId);
      return;
    }

    const toggleButton = event.target.closest('[data-job-toggle]');
    if (toggleButton) {
      const jobId = toggleButton.getAttribute('data-job-toggle');
      const isActive = toggleButton.getAttribute('data-job-active') === 'true';

      if (!jobId) {
        return;
      }

      toggleButton.disabled = true;
      try {
        await updateJobPostingRequest(jobId, { is_active: !isActive });
        if (isActive) {
          showMessage('Job posting deactivated. It will no longer appear on the student job board.', 'success');
        } else {
          showMessage('Job posting activated. Students can now see it on the job board.', 'success');
        }
        await loadDashboardData();
      } catch (error) {
        showMessage(error?.message || 'Failed to update job posting status.', 'error');
        toggleButton.disabled = false;
      }
      return;
    }

    const deleteButton = event.target.closest('[data-job-delete]');
    if (!deleteButton) {
      return;
    }

    const jobId = deleteButton.getAttribute('data-job-delete');
    if (!jobId) {
      return;
    }

    if (!window.confirm('Delete this job posting? This action cannot be undone.')) {
      return;
    }

    try {
      await deleteJobPostingRequest(jobId);
      showMessage('Job posting deleted.', 'success');
      await loadDashboardData();
    } catch (error) {
      showMessage(error?.message || 'Failed to delete job posting.', 'error');
    }
  });

  applicantsList.addEventListener('click', async (event) => {
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

    const statusButton = event.target.closest('[data-application-status-update]');
    if (!statusButton) {
      return;
    }

    const applicationId = statusButton.getAttribute('data-application-id');
    const nextStatus = statusButton.getAttribute('data-application-status-update');
    if (!applicationId || !nextStatus) {
      return;
    }

    statusButton.disabled = true;

    try {
      await updateApplicantStatusRequest(applicationId, {
        status: nextStatus,
        notes: nextStatus === 'in_review'
          ? 'Moved to in review by company recruiter.'
          : null,
      });
      if (nextStatus === 'in_review') {
        showMessage('Candidate selected. The student dashboard will now show this application under In Review.', 'success');
      } else {
        showMessage('Candidate moved back to Applied.', 'success');
      }
      await Promise.all([
        loadApplicants(activeApplicantsJobId),
        loadDashboardData(),
      ]);
    } catch (error) {
      showMessage(error?.message || 'Failed to move candidate to the next phase.', 'error');
      statusButton.disabled = false;
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && resumePreviewOverlay.classList.contains('active')) {
      closeResumePreview();
      return;
    }
    if (event.key === 'Escape' && applicantsModalOverlay.classList.contains('active')) {
      closeApplicantsModal();
      return;
    }
    if (event.key === 'Escape' && jobModalOverlay.classList.contains('active')) {
      closeJobPostingModal();
    }
  });

  loadDashboardData();
});

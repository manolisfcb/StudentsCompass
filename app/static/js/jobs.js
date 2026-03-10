const jobsPageData = JSON.parse(document.getElementById('jobs-page-data')?.textContent || '{}');
        const userDisplayName = jobsPageData.userDisplayName || 'Student';
        const keywordsInput = document.getElementById('keywords');
        const locationInput = document.getElementById('location');
        const limitSelect = document.getElementById('limit');
        const searchBtn = document.getElementById('searchBtn');
        const searchStatus = document.getElementById('searchStatus');
        const jobBoardLayout = document.getElementById('jobBoardLayout');
        const jobsList = document.getElementById('jobsList');
        const jobDetailPanel = document.getElementById('jobDetailPanel');
        const jobsCount = document.getElementById('jobsCount');
        const heroResultsCount = document.getElementById('heroResultsCount');
        const heroApplicationsCount = document.getElementById('heroApplicationsCount');
        const heroInterviewCount = document.getElementById('heroInterviewCount');
        const cvTabSummary = document.getElementById('cvTabSummary');
        const cvStatus = document.getElementById('cvStatus');
        const cvModal = document.getElementById('cvModal');
        const applyResumeModal = document.getElementById('applyResumeModal');
        const openCvModalBtn = document.getElementById('openCvModalBtn');
        const closeCvModalBtn = document.getElementById('closeCvModalBtn');
        const closeCvSecondaryBtn = document.getElementById('closeCvSecondaryBtn');
        const closeApplyResumeModalBtn = document.getElementById('closeApplyResumeModalBtn');
        const cancelApplyResumeBtn = document.getElementById('cancelApplyResumeBtn');
        const confirmApplyResumeBtn = document.getElementById('confirmApplyResumeBtn');
        const applyResumeStatus = document.getElementById('applyResumeStatus');
        const applyResumeOptions = document.getElementById('applyResumeOptions');
        const useCvBtn = document.getElementById('useCvBtn');
        const manualFocusBtn = document.getElementById('manualFocusBtn');
        const refreshApplicationsBtn = document.getElementById('refreshApplicationsBtn');
        const applicationsSummary = document.getElementById('applicationsSummary');
        const applicationsList = document.getElementById('applicationsList');
        const tabButtons = Array.from(document.querySelectorAll('.jobs-tab'));
        const tabPanels = Array.from(document.querySelectorAll('.tab-panel'));
        let lastSearchSource = 'manual';
        let activeJobKey = null;
        let currentJobResults = { students_compass: [], linkedin: [] };
        let renderedJobMap = new Map();
        let appliedJobPostingIds = new Set();
        let pendingApplyJobKey = null;

        function setGreeting() {
            const hour = new Date().getHours();
            let greeting = 'Hello';
            if (hour < 12) greeting = 'Good morning';
            else if (hour < 18) greeting = 'Good afternoon';
            else greeting = 'Good evening';

            document.getElementById('greetingTitle').textContent = `${greeting}, ${String(userDisplayName).toUpperCase()}`;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text ?? '';
            return div.innerHTML;
        }

        function formatDate(dateStr) {
            if (!dateStr) return 'Date unavailable';
            try {
                return new Date(dateStr).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                });
            } catch (_) {
                return dateStr;
            }
        }

        function formatStatus(status) {
            return String(status || '')
                .split('_')
                .filter(Boolean)
                .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
                .join(' ');
        }

        function getCompanyInitials(company) {
            const parts = String(company || 'SC')
                .split(/\s+/)
                .filter(Boolean)
                .slice(0, 2);

            if (!parts.length) return 'SC';
            return parts.map((part) => part[0].toUpperCase()).join('');
        }

        async function readErrorDetail(response, fallbackMessage) {
            try {
                const data = await response.json();
                if (typeof data?.detail === 'string' && data.detail.trim()) {
                    return data.detail.trim();
                }
            } catch (_) {
                // Use fallback when the body cannot be parsed.
            }
            return fallbackMessage;
        }

        function userFriendlyAutoModeError(message) {
            const raw = String(message || '').toLowerCase();
            if (!raw) return 'We could not analyze your CV right now.';
            if (raw.includes('daily limit') || raw.includes('429')) return 'You reached your daily AI analysis limit. Please try again tomorrow or use manual search.';
            if (raw.includes('quota') || raw.includes('credit') || raw.includes('billing') || raw.includes('resource_exhausted') || raw.includes('rate limit')) {
                return 'AI credits are temporarily exhausted. Please try again later or use manual search.';
            }
            if (raw.includes('timeout') || raw.includes('timed out')) return 'AI analysis took too long. Please try again in a few minutes.';
            if (raw.includes('no cv')) return 'No CV found. Please upload your CV first.';
            return 'We could not analyze your CV right now. Please try again later or use manual search.';
        }

        function switchTab(nextTab) {
            tabButtons.forEach((button) => {
                button.classList.toggle('active', button.dataset.tab === nextTab);
            });

            tabPanels.forEach((panel) => {
                panel.classList.toggle('active', panel.id === `tab-${nextTab}`);
            });
        }

        function syncModalBodyLock() {
            const hasActiveModal = cvModal.classList.contains('active') || applyResumeModal.classList.contains('active');
            document.body.style.overflow = hasActiveModal ? 'hidden' : '';
        }

        function openCvModal() {
            cvModal.classList.add('active');
            cvModal.setAttribute('aria-hidden', 'false');
            syncModalBodyLock();
        }

        function closeCvModal() {
            cvModal.classList.remove('active');
            cvModal.setAttribute('aria-hidden', 'true');
            syncModalBodyLock();
        }

        function setApplyResumeStatus(message, { loading = false, html = false } = {}) {
            applyResumeStatus.classList.toggle('loading', loading);
            if (html) {
                applyResumeStatus.innerHTML = message;
                return;
            }
            applyResumeStatus.textContent = message;
        }

        function closeApplyResumeModal() {
            pendingApplyJobKey = null;
            applyResumeModal.classList.remove('active');
            applyResumeModal.setAttribute('aria-hidden', 'true');
            confirmApplyResumeBtn.disabled = true;
            applyResumeOptions.innerHTML = '';
            setApplyResumeStatus('Loading your approved resumes...', { loading: true });
            syncModalBodyLock();
        }

        function getSelectedApprovedResumeId() {
            const selected = applyResumeOptions.querySelector('input[name="approvedResumeChoice"]:checked');
            return selected ? selected.value : null;
        }

        function refreshApprovedResumeSelectionUI() {
            const selectedId = getSelectedApprovedResumeId();
            const cards = applyResumeOptions.querySelectorAll('.resume-choice-card');
            cards.forEach((card) => {
                card.classList.toggle('active', card.getAttribute('data-resume-id') === selectedId);
            });
            confirmApplyResumeBtn.disabled = !selectedId;
        }

        function renderApprovedResumeOptions(resumes) {
            if (!Array.isArray(resumes) || !resumes.length) {
                applyResumeOptions.innerHTML = '';
                confirmApplyResumeBtn.disabled = true;
                setApplyResumeStatus(
                    'You do not have any approved resumes yet. Upload a CV in <a href="/user-profile">Profile</a> and get a Students Compass audit score of 8+ to apply here.',
                    { html: true }
                );
                return;
            }

            applyResumeOptions.innerHTML = resumes.map((resume, index) => {
                const summary = resume.ai_summary || 'No AI summary available for this resume yet.';
                const meta = [
                    `Score ${Number(resume.overall_score || 0).toFixed(1)}/10`,
                    `Approved ${escapeHtml(formatDate(resume.approved_at))}`,
                    `Uploaded ${escapeHtml(formatDate(resume.created_at))}`,
                ];
                return `
                    <label class="resume-choice-card ${index === 0 ? 'active' : ''}" data-resume-id="${escapeHtml(resume.id)}">
                        <div class="resume-choice-head">
                            <div class="resume-choice-main">
                                <input type="radio" name="approvedResumeChoice" value="${escapeHtml(resume.id)}" ${index === 0 ? 'checked' : ''}>
                                <div>
                                    <h3 class="resume-choice-title">${escapeHtml(resume.original_filename)}</h3>
                                    <div class="resume-choice-meta">
                                        ${meta.map((item) => `<span>${item}</span>`).join('')}
                                    </div>
                                </div>
                            </div>
                            ${resume.is_latest ? '<span class="resume-choice-pill">Latest approved</span>' : ''}
                        </div>
                        <p class="resume-choice-summary">${escapeHtml(summary)}</p>
                    </label>
                `;
            }).join('');
            setApplyResumeStatus('Select the approved resume you want to send to the company.');
            refreshApprovedResumeSelectionUI();
        }

        async function fetchEligibleResumes() {
            const response = await fetch('/api/v1/applications/eligible-resumes', {
                credentials: 'include',
            });

            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                return [];
            }

            if (!response.ok) {
                throw new Error(await readErrorDetail(response, 'Failed to load approved resumes.'));
            }

            return response.json();
        }

        async function openApplyResumeModal(jobKey) {
            pendingApplyJobKey = jobKey;
            applyResumeOptions.innerHTML = '';
            confirmApplyResumeBtn.disabled = true;
            setApplyResumeStatus(`
                <div class="loading-spinner"></div>
                <span>Loading your approved resumes...</span>
            `, { loading: true, html: true });
            applyResumeModal.classList.add('active');
            applyResumeModal.setAttribute('aria-hidden', 'false');
            syncModalBodyLock();

            try {
                const resumes = await fetchEligibleResumes();
                renderApprovedResumeOptions(Array.isArray(resumes) ? resumes : []);
            } catch (error) {
                applyResumeOptions.innerHTML = '';
                confirmApplyResumeBtn.disabled = true;
                setApplyResumeStatus(error?.message || 'Failed to load approved resumes.');
            }
        }

        function setCvSummary(message, { loading = false, html = false } = {}) {
            cvTabSummary.classList.toggle('loading', loading);
            cvStatus.classList.toggle('loading', loading);

            if (html) {
                cvTabSummary.innerHTML = message;
                cvStatus.innerHTML = message;
                return;
            }

            cvTabSummary.textContent = message;
            cvStatus.textContent = message;
        }

        function normalizeJob(job) {
            return {
                id: job.id || null,
                company_id: job.company_id || null,
                title: job.title || 'Untitled role',
                company: job.company || job.company_name || 'Unknown company',
                location: job.location || job.company_location || 'Location not specified',
                url: job.url || job.application_url || null,
                listed_at: job.listed_at || job.created_at || null,
                description: job.description || null,
                requirements: job.requirements || null,
                responsibilities: job.responsibilities || null,
                job_type: job.job_type || null,
                workplace_type: job.workplace_type || null,
                seniority_level: job.seniority_level || null,
                salary_range: job.salary_range || null,
                benefits: job.benefits || null,
                listed_context: job.listed_context || null,
                source_context: job.source_context || null,
                company_description: job.company_description || null,
                company_website: job.company_website || null,
                company_location: job.company_location || null,
                source: job.source || 'students_compass',
                source_label: job.source_label || (job.source === 'linkedin' ? 'LinkedIn' : 'Students Compass'),
            };
        }

        function getJobKey(job, index) {
            return job.id || `${job.source || 'job'}-${job.url || job.title || 'listing'}-${index}`;
        }

        async function fetchSearchResults(keywords, location, limit) {
            const response = await fetch('/api/v1/jobs/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    keywords,
                    location,
                    limit,
                    remote: false,
                }),
            });

            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                return { students_compass: [], linkedin: [] };
            }

            if (!response.ok) {
                throw new Error(await readErrorDetail(response, 'Search failed'));
            }

            const payload = await response.json();
            return {
                students_compass: Array.isArray(payload?.students_compass) ? payload.students_compass.map(normalizeJob) : [],
                linkedin: Array.isArray(payload?.linkedin) ? payload.linkedin.map(normalizeJob) : [],
            };
        }

        async function fetchBoardJobs() {
            try {
                const response = await fetch('/api/v1/jobs/board?limit=50', {
                    credentials: 'include',
                });

                if (response.status === 401 || response.status === 403) {
                    window.location.href = '/login';
                    return { students_compass: [], linkedin: [] };
                }

                if (!response.ok) {
                    throw new Error(await readErrorDetail(response, 'Failed to load Students Compass jobs'));
                }

                const jobs = await response.json();
                return {
                    students_compass: Array.isArray(jobs) ? jobs.map(normalizeJob) : [],
                    linkedin: [],
                };
            } catch (error) {
                searchStatus.textContent = error?.message || 'Failed to load Students Compass jobs.';
                return { students_compass: [], linkedin: [] };
            }
        }

        function renderEmptyJobs(messageTitle, messageBody) {
            activeJobKey = null;
            currentJobResults = { students_compass: [], linkedin: [] };
            renderedJobMap = new Map();
            jobBoardLayout.classList.remove('with-detail');
            jobsCount.textContent = 'No results';
            heroResultsCount.textContent = '0';
            jobsList.innerHTML = `
                <div class="empty-state">
                    <h3>${escapeHtml(messageTitle)}</h3>
                    <p>${escapeHtml(messageBody)}</p>
                </div>
            `;
            jobDetailPanel.innerHTML = `
                <div class="empty-state">
                    <h3>No job selected</h3>
                    <p>${escapeHtml(messageBody)}</p>
                </div>
            `;
        }

        function buildMetaPills(job) {
            return [
                job.location ? `<span>${escapeHtml(job.location)}</span>` : '',
                job.workplace_type ? `<span>${escapeHtml(job.workplace_type)}</span>` : '',
                job.job_type ? `<span>${escapeHtml(job.job_type)}</span>` : '',
                job.seniority_level ? `<span>${escapeHtml(job.seniority_level)}</span>` : '',
                job.salary_range ? `<span>${escapeHtml(job.salary_range)}</span>` : '',
            ].filter(Boolean).join('');
        }

        function isEasyApplyJob(job) {
            return job.source === 'students_compass';
        }

        function renderCardApplyAction(job, jobKey) {
            if (isEasyApplyJob(job)) {
                const applied = job.id && appliedJobPostingIds.has(job.id);
                return `
                    <button class="primary-link" type="button" data-easy-apply="${escapeHtml(jobKey)}" ${applied ? 'disabled' : ''}>
                        ${applied ? 'Applied' : 'Quick Apply'}
                    </button>
                `;
            }

            if (job.url) {
                return `
                    <a class="primary-link" href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer">
                        Apply
                    </a>
                `;
            }

            return '<span class="secondary-link" aria-disabled="true">Apply link unavailable</span>';
        }

        async function submitQuickApply(job, resumeId) {
            if (!job?.id || !job?.company_id) {
                throw new Error('This job cannot be applied to right now.');
            }

            const response = await fetch('/api/v1/applications', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    company_id: job.company_id,
                    job_posting_id: job.id,
                    resume_id: resumeId,
                    job_title: job.title,
                    application_url: job.url,
                    status: 'applied',
                    notes: 'Applied via Students Compass Quick Apply.',
                }),
            });

            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                return null;
            }

            if (!response.ok) {
                throw new Error(await readErrorDetail(response, 'Quick Apply failed.'));
            }

            return response.json();
        }

        function renderJobDetail(job) {
            if (!job) {
                jobDetailPanel.innerHTML = `
                    <div class="empty-state">
                        <h3>Select a job</h3>
                        <p>Job details will appear here once you choose a listing from the left side.</p>
                    </div>
                `;
                return;
            }

            const listedContext = job.listed_context || (job.listed_at ? `Posted ${formatDate(job.listed_at)}` : '');
            const sourceContext = job.source_context || (job.source === 'linkedin' ? 'External listing from LinkedIn.' : 'Published on Students Compass.');
            const aboutJob = job.description
                ? `<section class="job-detail-section"><h3>About the job</h3><p>${escapeHtml(job.description)}</p></section>`
                : '';
            const requirements = job.requirements
                ? `<section class="job-detail-section"><h3>Requirements</h3><p>${escapeHtml(job.requirements)}</p></section>`
                : '';
            const responsibilities = job.responsibilities
                ? `<section class="job-detail-section"><h3>Responsibilities</h3><p>${escapeHtml(job.responsibilities)}</p></section>`
                : '';
            const benefits = job.benefits
                ? `<section class="job-detail-section"><h3>Benefits</h3><p>${escapeHtml(job.benefits)}</p></section>`
                : '';
            const companyDescription = job.company_description
                ? `<section class="job-detail-section"><h3>About the company</h3><p>${escapeHtml(job.company_description)}</p></section>`
                : '';
            const companyWebsite = job.company_website
                ? `<a class="secondary-link" href="${escapeHtml(job.company_website)}" target="_blank" rel="noopener noreferrer">Company site</a>`
                : '';
            const applyAction = renderCardApplyAction(job, activeJobKey || getJobKey(job, 0));
            const closeButton = `
                <button class="job-detail-close" type="button" id="jobDetailCloseBtn" aria-label="Close job details">×</button>
            `;

            jobDetailPanel.innerHTML = `
                <div class="job-detail-header">
                    <div class="job-detail-company">
                        <div class="company-mark">${escapeHtml(getCompanyInitials(job.company))}</div>
                        <div class="job-detail-company-copy">
                            <p class="job-detail-company-name">${escapeHtml(job.company)}</p>
                            <span class="bookmark-pill">${escapeHtml(job.source_label)}</span>
                        </div>
                    </div>
                    ${closeButton}
                </div>
                <div class="job-detail-grid">
                    <div class="job-detail-section">
                        <h2 class="job-detail-title">${escapeHtml(job.title)}</h2>
                        <p class="job-detail-subtitle">${escapeHtml(job.company)} · ${escapeHtml(job.location)}</p>
                        ${listedContext ? `<p class="job-detail-subtitle">${escapeHtml(listedContext)}</p>` : ''}
                        ${sourceContext ? `<p class="job-detail-subtitle">${escapeHtml(sourceContext)}</p>` : ''}
                    </div>
                    <div class="job-meta">${buildMetaPills(job)}</div>
                    <div class="job-detail-actions">
                        ${applyAction}
                        ${companyWebsite}
                        <span class="secondary-link">${escapeHtml(lastSearchSource === 'cv' ? 'Based on your CV' : 'Manual search')}</span>
                    </div>
                    ${aboutJob}
                    ${requirements}
                    ${responsibilities}
                    ${benefits}
                    ${companyDescription}
                    ${job.source === 'linkedin' ? '<div class="job-detail-note">LinkedIn listings are shown as external opportunities. Full structured details depend on the public data available from that source.</div>' : ''}
                </div>
            `;
        }

        function renderJobResults(results, { emptyTitle, emptyBody } = {}) {
            currentJobResults = {
                students_compass: Array.isArray(results?.students_compass) ? results.students_compass : [],
                linkedin: Array.isArray(results?.linkedin) ? results.linkedin : [],
            };

            const internalJobs = currentJobResults.students_compass;
            const linkedinJobs = currentJobResults.linkedin;
            const combinedJobs = [...internalJobs, ...linkedinJobs];

            if (!combinedJobs.length) {
                renderEmptyJobs(
                    emptyTitle || 'No jobs found yet',
                    emptyBody || 'Try broader keywords, change the location, or use the AI CV search to discover better matches.',
                );
                return;
            }

            const detailOpen = Boolean(activeJobKey);
            heroResultsCount.textContent = String(combinedJobs.length);
            jobsCount.textContent = `${combinedJobs.length} jobs shown`;

            renderedJobMap = new Map();
            const selectedFallbackKey = detailOpen && combinedJobs.some((job, index) => getJobKey(job, index) === activeJobKey)
                ? activeJobKey
                : (detailOpen ? getJobKey(combinedJobs[0], 0) : null);
            activeJobKey = selectedFallbackKey;
            jobBoardLayout.classList.toggle('with-detail', Boolean(activeJobKey));

            const renderCards = (jobs, offset = 0) => jobs.map((job, index) => {
                const jobKey = getJobKey(job, index + offset);
                renderedJobMap.set(jobKey, job);
                const isActive = activeJobKey === jobKey;
                const listedAt = job.listed_at ? `Posted ${formatDate(job.listed_at)}` : job.listed_context || '';
                const snippet = job.description || job.requirements || job.company_description || 'Open the detail panel to review this opportunity.';
                return `
                    <article class="job-result-card ${isActive ? 'active' : ''}" data-job-key="${escapeHtml(jobKey)}">
                        <div class="job-result-head">
                            <div class="job-detail-company">
                                <div class="company-mark">${escapeHtml(getCompanyInitials(job.company))}</div>
                                <div class="job-result-main">
                                    <p class="job-result-company">${escapeHtml(job.company)}</p>
                                    <h3 class="job-result-title">${escapeHtml(job.title)}</h3>
                                </div>
                            </div>
                            <span class="bookmark-pill">${escapeHtml(job.source_label)}</span>
                        </div>
                        <div class="job-meta">${buildMetaPills(job)}</div>
                        ${listedAt ? `<p class="job-result-snippet">${escapeHtml(listedAt)}</p>` : ''}
                        <p class="job-result-snippet">${escapeHtml(snippet)}</p>
                        <div class="job-card-actions">
                            ${renderCardApplyAction(job, jobKey)}
                        </div>
                    </article>
                `;
            }).join('');

            const containerClass = activeJobKey ? 'job-results-list' : 'job-results-grid';

            const sections = [];
            if (internalJobs.length) {
                sections.push(`
                    <section class="result-group">
                        <div class="result-group-header">
                            <h3 class="result-group-title">Students Compass matches</h3>
                            <span class="result-group-meta">${internalJobs.length} ${internalJobs.length === 1 ? 'job' : 'jobs'}</span>
                        </div>
                        <div class="${containerClass}">
                            ${renderCards(internalJobs, 0)}
                        </div>
                    </section>
                `);
            }

            if (internalJobs.length && linkedinJobs.length) {
                sections.push('<div class="jobs-source-divider"><span>More from LinkedIn</span></div>');
            }

            if (linkedinJobs.length) {
                sections.push(`
                    <section class="result-group">
                        <div class="result-group-header">
                            <h3 class="result-group-title">LinkedIn results</h3>
                            <span class="result-group-meta">${linkedinJobs.length} ${linkedinJobs.length === 1 ? 'job' : 'jobs'}</span>
                        </div>
                        <div class="${containerClass}">
                            ${renderCards(linkedinJobs, internalJobs.length)}
                        </div>
                    </section>
                `);
            }

            jobsList.innerHTML = sections.join('');
            if (activeJobKey) {
                renderJobDetail(renderedJobMap.get(activeJobKey) || combinedJobs[0]);
            } else {
                renderJobDetail(null);
            }
        }

        async function performSearch(source = 'manual') {
            const rawKeywords = keywordsInput.value.trim();
            const location = locationInput.value.trim();
            const limit = parseInt(limitSelect.value, 10);

            if (!rawKeywords) {
                searchStatus.textContent = 'Enter at least one keyword to search.';
                return;
            }

            searchBtn.disabled = true;
            lastSearchSource = source;
            searchStatus.textContent = 'Searching Students Compass first, then LinkedIn...';
            switchTab('home');
            jobsList.innerHTML = `
                <div class="status-banner loading">
                    <div class="loading-spinner"></div>
                    <span>Finding fresh jobs for your selected keywords...</span>
                </div>
            `;
            jobDetailPanel.innerHTML = `
                <div class="status-banner loading">
                    <div class="loading-spinner"></div>
                    <span>Preparing the selected job details...</span>
                </div>
            `;

            try {
                const results = await fetchSearchResults(rawKeywords, location, limit);
                renderJobResults(results);
                searchStatus.textContent = totalSearchStatus(results);
            } catch (_) {
                renderEmptyJobs('Search failed', 'Something went wrong while fetching jobs. Please try again.');
                searchStatus.textContent = 'Search failed';
            } finally {
                searchBtn.disabled = false;
            }
        }

        function totalSearchStatus(results) {
            const internalJobs = Array.isArray(results?.students_compass) ? results.students_compass : [];
            const linkedinJobs = Array.isArray(results?.linkedin) ? results.linkedin : [];
            const totalJobs = internalJobs.length + linkedinJobs.length;
            if (!totalJobs) return 'No results yet.';
            if (internalJobs.length && linkedinJobs.length) {
                return `${internalJobs.length} Students Compass jobs first, followed by ${linkedinJobs.length} LinkedIn jobs.`;
            }
            if (internalJobs.length) {
                return `${internalJobs.length} Students Compass jobs found.`;
            }
            return `No Students Compass matches were found. Showing ${linkedinJobs.length} LinkedIn jobs.`;
        }

        async function loadInitialJobBoard() {
            jobsList.innerHTML = `
                <div class="status-banner loading">
                    <div class="loading-spinner"></div>
                    <span>Loading current Students Compass opportunities...</span>
                </div>
            `;
            jobDetailPanel.innerHTML = `
                <div class="status-banner loading">
                    <div class="loading-spinner"></div>
                    <span>Preparing job details...</span>
                </div>
            `;

            const results = await fetchBoardJobs();
            if (!results.students_compass.length) {
                renderEmptyJobs(
                    'No Students Compass jobs posted yet',
                    'As soon as companies publish new roles, they will appear here for students.',
                );
                searchStatus.textContent = 'No internal jobs available yet.';
                return;
            }

            renderJobResults(results, {
                emptyTitle: 'No Students Compass jobs posted yet',
                emptyBody: 'As soon as companies publish new roles, they will appear here for students.',
            });
            searchStatus.textContent = `${results.students_compass.length} Students Compass jobs available right now.`;
        }

        async function checkCVAvailability() {
            setCvSummary(`
                <div class="loading-spinner"></div>
                <span>Checking if your CV is available for AI analysis...</span>
            `, { loading: true, html: true });

            try {
                const response = await fetch('/api/v1/jobs/keywords', {
                    credentials: 'include',
                });

                if (response.status === 401 || response.status === 403) {
                    window.location.href = '/login';
                    return;
                }

                if (!response.ok) {
                    setCvSummary('Could not verify CV status. You can still use manual search.');
                    return;
                }

                const data = await response.json();

                if (!data.has_cv) {
                    setCvSummary('No CV uploaded yet. Upload your resume in <a href="/user-profile">Profile</a> to enable AI keyword search.', { html: true });
                    return;
                }

                setCvSummary('Your CV is ready. Click <strong>Open AI search</strong> to analyze it and run the search automatically.', { html: true });
            } catch (_) {
                setCvSummary('Could not verify CV status. You can still use manual search.');
            }
        }

        async function loadAutoKeywords() {
            useCvBtn.disabled = true;
            searchBtn.disabled = true;
            setCvSummary(`
                <div class="loading-spinner"></div>
                <span>Starting AI CV analysis...</span>
            `, { loading: true, html: true });

            try {
                const startResponse = await fetch('/api/v1/jobs/keywords/analyze', {
                    method: 'POST',
                    credentials: 'include',
                });

                if (startResponse.status === 401 || startResponse.status === 403) {
                    window.location.href = '/login';
                    return;
                }

                if (!startResponse.ok) {
                    const detail = await readErrorDetail(startResponse, 'Failed to start CV analysis');
                    throw new Error(detail);
                }

                const { job_id: jobId } = await startResponse.json();
                let attempts = 0;
                const maxAttempts = 20;

                while (attempts < maxAttempts) {
                    await new Promise((resolve) => setTimeout(resolve, 3000));

                    const statusResponse = await fetch(`/api/v1/jobs/keywords/${jobId}`, {
                        credentials: 'include',
                    });

                    if (!statusResponse.ok) {
                        const detail = await readErrorDetail(statusResponse, 'Failed to check analysis status');
                        throw new Error(detail);
                    }

                    const jobData = await statusResponse.json();

                    if (jobData.status === 'completed') {
                        keywordsInput.value = jobData.keywords || '';
                        setCvSummary(`AI extracted these keywords: <strong>${escapeHtml(jobData.keywords || '')}</strong>`, { html: true });
                        if (keywordsInput.value.trim()) {
                            closeCvModal();
                            await performSearch('cv');
                        }
                        return;
                    }

                    if (jobData.status === 'failed') {
                        throw new Error(jobData.error_message || 'AI analysis failed');
                    }

                    attempts += 1;
                    setCvSummary(`
                        <div class="loading-spinner"></div>
                        <span>Analyzing your CV... ${attempts * 3}s</span>
                    `, { loading: true, html: true });
                }

                throw new Error('Analysis timed out');
            } catch (error) {
                setCvSummary(userFriendlyAutoModeError(error?.message || ''));
            } finally {
                useCvBtn.disabled = false;
                searchBtn.disabled = false;
            }
        }

        function renderApplicationSummary(applications) {
            const counts = applications.reduce((acc, application) => {
                const status = application.status || 'applied';
                acc.total += 1;
                acc[status] = (acc[status] || 0) + 1;
                return acc;
            }, { total: 0, applied: 0, in_review: 0, interview: 0, offer: 0 });

            heroApplicationsCount.textContent = String(counts.total);
            heroInterviewCount.textContent = String(counts.interview || 0);

            applicationsSummary.innerHTML = `
                <div class="summary-card">
                    <span class="summary-label">Total tracked</span>
                    <span class="summary-value">${counts.total}</span>
                    <div class="summary-note">All jobs you already applied to.</div>
                </div>
                <div class="summary-card">
                    <span class="summary-label">Applied</span>
                    <span class="summary-value">${counts.applied || 0}</span>
                    <div class="summary-note">Initial submissions logged.</div>
                </div>
                <div class="summary-card">
                    <span class="summary-label">In review</span>
                    <span class="summary-value">${counts.in_review || 0}</span>
                    <div class="summary-note">Companies still evaluating you.</div>
                </div>
                <div class="summary-card">
                    <span class="summary-label">Interviews</span>
                    <span class="summary-value">${counts.interview || 0}</span>
                    <div class="summary-note">Active conversations in progress.</div>
                </div>
            `;
        }

        function renderApplications(applications) {
            appliedJobPostingIds = new Set(
                applications
                    .map((application) => application.job_posting_id)
                    .filter(Boolean)
            );
            renderApplicationSummary(applications);

            if (!applications.length) {
                applicationsList.innerHTML = `
                    <div class="empty-state">
                        <h3>No applications tracked yet</h3>
                        <p>Your applied jobs will appear here once they are stored in Student Compass.</p>
                    </div>
                `;
                return;
            }

            applicationsList.innerHTML = `
                <div class="applications-grid">
                    ${applications.map((application) => {
                        const companyName = escapeHtml(application.company_name || 'Company');
                        const companyLocation = application.company_location ? `<span>${escapeHtml(application.company_location)}</span>` : '';
                        const applicationUrl = application.application_url
                            ? `<a class="secondary-link" href="${escapeHtml(application.application_url)}" target="_blank" rel="noopener noreferrer">Application link</a>`
                            : '';
                        const notes = application.notes
                            ? `<p class="application-notes">${escapeHtml(application.notes)}</p>`
                            : '';

                        return `
                            <article class="application-card">
                                <div class="application-card-top">
                                    <div class="company-mark">${escapeHtml(getCompanyInitials(application.company_name))}</div>
                                    <span class="status-pill ${escapeHtml(application.status)}">${escapeHtml(formatStatus(application.status))}</span>
                                </div>
                                <div>
                                    <p class="application-company">${companyName}</p>
                                    <h3 class="application-title">${escapeHtml(application.job_title || 'Untitled role')}</h3>
                                </div>
                                <div class="application-meta">
                                    ${companyLocation}
                                    <span>Applied ${escapeHtml(formatDate(application.application_date))}</span>
                                </div>
                                ${notes}
                                <div class="application-actions">
                                    ${applicationUrl}
                                </div>
                            </article>
                        `;
                    }).join('')}
                </div>
            `;
        }

        async function loadApplications() {
            applicationsList.innerHTML = `
                <div class="status-banner loading">
                    <div class="loading-spinner"></div>
                    <span>Loading your tracked jobs...</span>
                </div>
            `;

            try {
                const response = await fetch('/api/v1/applications', {
                    credentials: 'include',
                });

                if (response.status === 401 || response.status === 403) {
                    window.location.href = '/login';
                    return;
                }

                if (!response.ok) {
                    throw new Error(await readErrorDetail(response, 'Failed to load applications'));
                }

                const applications = await response.json();
                renderApplications(applications);
            } catch (error) {
                applicationsSummary.innerHTML = `
                    <div class="summary-card">
                        <span class="summary-label">Error</span>
                        <span class="summary-value">!</span>
                        <div class="summary-note">${escapeHtml(error?.message || 'Failed to load applications.')}</div>
                    </div>
                `;
                applicationsList.innerHTML = `
                    <div class="empty-state">
                        <h3>Could not load My Jobs</h3>
                        <p>${escapeHtml(error?.message || 'Please try again in a moment.')}</p>
                    </div>
                `;
            }
        }

        tabButtons.forEach((button) => {
            button.addEventListener('click', () => {
                switchTab(button.dataset.tab);
            });
        });

        searchBtn.addEventListener('click', () => performSearch('manual'));
        openCvModalBtn.addEventListener('click', openCvModal);
        closeCvModalBtn.addEventListener('click', closeCvModal);
        closeCvSecondaryBtn.addEventListener('click', closeCvModal);
        useCvBtn.addEventListener('click', loadAutoKeywords);
        manualFocusBtn.addEventListener('click', () => {
            closeCvModal();
            switchTab('home');
            keywordsInput.focus();
        });
        refreshApplicationsBtn.addEventListener('click', loadApplications);

        jobsList.addEventListener('click', (event) => {
            if (event.target.closest('a.primary-link, a.secondary-link')) {
                return;
            }

            const easyApplyButton = event.target.closest('[data-easy-apply]');
            if (easyApplyButton) {
                return;
            }

            const card = event.target.closest('[data-job-key]');
            if (!card) return;

            const jobKey = card.getAttribute('data-job-key');
            if (!jobKey || !renderedJobMap.has(jobKey)) return;

            activeJobKey = jobKey;
            renderJobResults(currentJobResults);
        });

        jobsList.addEventListener('click', async (event) => {
            const easyApplyButton = event.target.closest('[data-easy-apply]');
            if (!easyApplyButton) {
                return;
            }

            event.stopPropagation();
            const jobKey = easyApplyButton.getAttribute('data-easy-apply');
            if (!jobKey || !renderedJobMap.has(jobKey)) {
                return;
            }

            const job = renderedJobMap.get(jobKey);
            if (!job || !isEasyApplyJob(job)) {
                return;
            }

            await openApplyResumeModal(jobKey);
        });

        jobDetailPanel.addEventListener('click', (event) => {
            const easyApplyButton = event.target.closest('[data-easy-apply]');
            if (easyApplyButton) {
                const jobKey = easyApplyButton.getAttribute('data-easy-apply');
                if (!jobKey || !renderedJobMap.has(jobKey)) {
                    return;
                }

                const job = renderedJobMap.get(jobKey);
                if (!job || !isEasyApplyJob(job)) {
                    return;
                }

                (async () => {
                    await openApplyResumeModal(jobKey);
                })();
                return;
            }

            const closeButton = event.target.closest('#jobDetailCloseBtn');
            if (!closeButton) {
                return;
            }

            activeJobKey = null;
            renderJobResults(currentJobResults);
        });

        cvModal.addEventListener('click', (event) => {
            if (event.target === cvModal) {
                closeCvModal();
            }
        });

        applyResumeModal.addEventListener('click', (event) => {
            if (event.target === applyResumeModal) {
                closeApplyResumeModal();
            }
        });

        applyResumeOptions.addEventListener('change', (event) => {
            if (event.target.matches('input[name="approvedResumeChoice"]')) {
                refreshApprovedResumeSelectionUI();
            }
        });

        applyResumeOptions.addEventListener('click', (event) => {
            const card = event.target.closest('.resume-choice-card');
            if (!card) {
                return;
            }
            const input = card.querySelector('input[name="approvedResumeChoice"]');
            if (input) {
                input.checked = true;
                refreshApprovedResumeSelectionUI();
            }
        });

        closeApplyResumeModalBtn.addEventListener('click', closeApplyResumeModal);
        cancelApplyResumeBtn.addEventListener('click', closeApplyResumeModal);
        confirmApplyResumeBtn.addEventListener('click', async () => {
            const resumeId = getSelectedApprovedResumeId();
            if (!resumeId || !pendingApplyJobKey || !renderedJobMap.has(pendingApplyJobKey)) {
                return;
            }

            const job = renderedJobMap.get(pendingApplyJobKey);
            if (!job || !isEasyApplyJob(job)) {
                return;
            }

            confirmApplyResumeBtn.disabled = true;
            setApplyResumeStatus(`
                <div class="loading-spinner"></div>
                <span>Submitting your application with the selected approved CV...</span>
            `, { loading: true, html: true });

            try {
                await submitQuickApply(job, resumeId);
                if (job.id) {
                    appliedJobPostingIds.add(job.id);
                }
                closeApplyResumeModal();
                searchStatus.textContent = `Application saved for ${job.title}.`;
                await loadApplications();
                renderJobResults(currentJobResults);
            } catch (error) {
                setApplyResumeStatus(error?.message || 'Quick Apply failed.');
                refreshApprovedResumeSelectionUI();
                searchStatus.textContent = error?.message || 'Quick Apply failed.';
            }
        });

        [keywordsInput, locationInput].forEach((input) => {
            input.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') {
                    performSearch('manual');
                }
            });
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && cvModal.classList.contains('active')) {
                closeCvModal();
            }
            if (event.key === 'Escape' && applyResumeModal.classList.contains('active')) {
                closeApplyResumeModal();
            }
        });

        window.addEventListener('load', async () => {
            setGreeting();
            await Promise.all([checkCVAvailability(), loadApplications(), loadInitialJobBoard()]);
        });

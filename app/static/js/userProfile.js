let currentProfileData = null;

        function updateUserIdentity(profileData = {}) {
            const fullName = [profileData.first_name, profileData.last_name].filter(Boolean).join(' ').trim();
            document.getElementById('userName').textContent = fullName || profileData.nickname || 'User';
            document.getElementById('userEmail').textContent = profileData.email || '-';
        }

        function populateProfileForm(profileData = {}) {
            currentProfileData = profileData;
            document.getElementById('profile-first-name').value = profileData.first_name || '';
            document.getElementById('profile-last-name').value = profileData.last_name || '';
            document.getElementById('profile-nickname').value = profileData.nickname || '';
            document.getElementById('profile-email').value = profileData.email || '';
            document.getElementById('profile-phone').value = profileData.phone || '';
            document.getElementById('profile-address').value = profileData.address || '';
            document.getElementById('profile-sex').value = profileData.sex || '';
            document.getElementById('profile-age').value = profileData.age ?? '';
            updateUserIdentity(profileData);
        }

        async function loadEditableProfile() {
            const response = await fetch('/api/v1/profile', {
                credentials: 'include',
                cache: 'no-store',
            });

            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error('Could not load user profile');
            }

            const data = await response.json();
            populateProfileForm(data);
            const loading = document.getElementById('loading');
            const content = document.getElementById('content');
            loading.style.display = 'none';
            content.style.display = 'block';
        }

        async function saveEditableProfile(event) {
            event.preventDefault();
            const saveButton = document.getElementById('profileSaveButton');
            const saveStatus = document.getElementById('profileSaveStatus');
            saveButton.disabled = true;
            saveStatus.textContent = 'Saving your details...';

            const payload = {
                first_name: document.getElementById('profile-first-name').value.trim() || null,
                last_name: document.getElementById('profile-last-name').value.trim() || null,
                nickname: document.getElementById('profile-nickname').value.trim() || null,
                email: document.getElementById('profile-email').value.trim() || currentProfileData?.email || null,
                phone: document.getElementById('profile-phone').value.trim() || null,
                address: document.getElementById('profile-address').value.trim() || null,
                sex: document.getElementById('profile-sex').value.trim() || null,
                age: document.getElementById('profile-age').value ? Number(document.getElementById('profile-age').value) : null,
            };

            try {
                const response = await fetch('/api/v1/profile', {
                    method: 'PATCH',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload),
                });

                if (response.status === 401 || response.status === 403) {
                    window.location.href = '/login';
                    return;
                }

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data?.detail || 'Could not save your profile');
                }

                populateProfileForm(data);
                saveStatus.textContent = 'Profile details saved.';
            } catch (error) {
                saveStatus.textContent = error?.message || 'Could not save your profile.';
            } finally {
                saveButton.disabled = false;
            }
        }

        async function loadProfile() {
            try {
                // Get questionnaire data
                const response = await fetch('/api/v1/questionnaire/profile', {
                    method: 'GET',
                    credentials: 'include',
                    cache: 'no-store',
                });

                if (!response.ok) {
                    if (response.status === 401 || response.status === 403) {
                        window.location.href = '/login';
                        return;
                    }
                    if (response.status === 404) {
                        showNoData();
                        return;
                    }
                    throw new Error('Error loading profile');
                }

                const data = await response.json();
                displayProfile(data);
            } catch (error) {
                console.error('Error:', error);
                showNoData();
            }
        }

        function displayProfile(data) {
            const loading = document.getElementById('loading');
            const content = document.getElementById('content');
            const noData = document.getElementById('noData');

            // Hide loading
            loading.style.display = 'none';
            noData.style.display = 'none';
            content.style.display = 'block';

            // Display user info
            const userName = data.user_name || 'User';
            const userEmail = data.user_email || '-';
            const completionDate = data.created_at ? new Date(data.created_at).toLocaleDateString('en-US') : '-';

            if (!currentProfileData) {
                document.getElementById('userName').textContent = userName;
                document.getElementById('userEmail').textContent = userEmail;
            }
            document.getElementById('completionDate').textContent = completionDate;

            // Display results if available
            if (data.results && data.results.length > 0) {
                displayResults(data.results);
            }

        }

        function displayResults(results) {
            const container = document.getElementById('resultsContainer');
            const grid = document.getElementById('resultsGrid');
            
            // Find max score to normalize
            const maxScore = Math.max(...results.map(r => r.score));
            
            grid.innerHTML = results.slice(0, 3).map(result => {
                // Normalize score to 0-100 for progress bar
                const percentage = maxScore > 0 ? (result.score / maxScore) * 100 : 0;
                // Calculate affinity rating out of 10
                const affinityRating = maxScore > 0 ? ((result.score / maxScore) * 10).toFixed(1) : '0.0';
                
                return `
                    <div class="result-card profile-card fade-in">
                        <h4 style="margin: 0 0 1rem 0; font-weight: 600; color: var(--text-color);">${result.career}</h4>
                        <div class="progress-bar">
                            <div class="progress" style="width: ${percentage}%"></div>
                        </div>
                        <p style="color: var(--gray); font-size: 0.9rem; margin: 0;">Affinity: <span style="font-weight: 600; color: var(--text-color);">${affinityRating}/10</span></p>
                    </div>
                `;
            }).join('');

            container.style.display = 'block';
        }

        function showNoData() {
            const loading = document.getElementById('loading');
            const content = document.getElementById('content');
            const noData = document.getElementById('noData');

            loading.style.display = 'none';
            content.style.display = 'block';
            noData.style.display = 'block';
        }

        function renderRequestList(containerId, countId, items, emptyMessage, options = {}) {
            const container = document.getElementById(containerId);
            const count = document.getElementById(countId);
            count.textContent = String(items.length);

            if (!items.length) {
                container.innerHTML = `<p class="network-empty">${emptyMessage}</p>`;
                return;
            }

            container.innerHTML = items.map((item) => {
                const person = options.direction === 'incoming' ? item.sender : item.receiver;
                const actions = options.direction === 'incoming'
                    ? `
                        <button class="network-action network-action--primary" data-network-action="accept" data-request-id="${item.id}">Accept</button>
                        <button class="network-action" data-network-action="reject" data-request-id="${item.id}">Ignore</button>
                    `
                    : `<button class="network-action" data-network-action="cancel" data-request-id="${item.id}">Cancel</button>`;

                return `
                    <article class="network-item">
                        <div class="network-item__identity">
                            <div class="network-avatar">${initialsFromName(person.display_name)}</div>
                            <div>
                                <h5>${escapeHtml(person.display_name)}</h5>
                                <p>${options.direction === 'incoming' ? 'Wants to connect with you' : 'Waiting for a reply'}</p>
                            </div>
                        </div>
                        <div class="network-item__actions">
                            ${actions}
                        </div>
                    </article>
                `;
            }).join('');
        }

        function renderFriendsList(items) {
            const container = document.getElementById('friendsList');
            const count = document.getElementById('friendsCount');
            count.textContent = String(items.length);

            if (!items.length) {
                container.innerHTML = '<p class="network-empty">Join communities and start connecting with other students.</p>';
                return;
            }

            container.innerHTML = items.map((item) => `
                <article class="network-item">
                    <div class="network-item__identity">
                        <div class="network-avatar">${initialsFromName(item.friend.display_name)}</div>
                        <div>
                            <h5>${escapeHtml(item.friend.display_name)}</h5>
                            <p>Connected ${formatDate(item.created_at)}</p>
                        </div>
                    </div>
                    <div class="network-item__actions">
                        <button class="network-action" data-network-action="remove-friend" data-user-id="${item.friend.id}">Remove</button>
                    </div>
                </article>
            `).join('');
        }

        function escapeHtml(value) {
            const div = document.createElement('div');
            div.textContent = value ?? '';
            return div.innerHTML;
        }

        function initialsFromName(name) {
            return (name || 'SC')
                .split(' ')
                .filter(Boolean)
                .map((part) => part[0])
                .join('')
                .toUpperCase()
                .slice(0, 2);
        }

        async function loadFriendNetwork(statusMessage = '') {
            const networkStatus = document.getElementById('networkStatus');
            networkStatus.textContent = statusMessage || 'Loading your network...';

            try {
                const [incomingRes, outgoingRes, friendsRes] = await Promise.all([
                    fetch('/api/v1/friends/requests/incoming', {
                        credentials: 'include',
                        cache: 'no-store',
                    }),
                    fetch('/api/v1/friends/requests/outgoing', {
                        credentials: 'include',
                        cache: 'no-store',
                    }),
                    fetch('/api/v1/friends', {
                        credentials: 'include',
                        cache: 'no-store',
                    }),
                ]);

                const responses = [incomingRes, outgoingRes, friendsRes];
                if (responses.some((response) => response.status === 401 || response.status === 403)) {
                    window.location.href = '/login';
                    return;
                }
                if (responses.some((response) => !response.ok)) {
                    throw new Error('Could not load your network');
                }

                const [incoming, outgoing, friends] = await Promise.all([
                    incomingRes.json(),
                    outgoingRes.json(),
                    friendsRes.json(),
                ]);

                renderRequestList('incomingRequests', 'incomingCount', incoming, 'No incoming requests right now.', {
                    direction: 'incoming',
                });
                renderRequestList('outgoingRequests', 'outgoingCount', outgoing, 'You have not sent any requests yet.', {
                    direction: 'outgoing',
                });
                renderFriendsList(friends);
                networkStatus.textContent = statusMessage;
            } catch (error) {
                console.error('Error loading friend network:', error);
                networkStatus.textContent = error?.message || 'Could not load your network.';
            }
        }

        async function handleNetworkAction(action, requestId, userId) {
            const networkStatus = document.getElementById('networkStatus');
            networkStatus.textContent = 'Updating your network...';

            let url = '';
            let method = 'POST';
            let successMessage = 'Network updated.';

            if (action === 'accept') {
                url = `/api/v1/friends/requests/${requestId}/accept`;
                successMessage = 'Friend request accepted.';
            } else if (action === 'reject') {
                url = `/api/v1/friends/requests/${requestId}/reject`;
                successMessage = 'Friend request ignored.';
            } else if (action === 'cancel') {
                url = `/api/v1/friends/requests/${requestId}/cancel`;
                successMessage = 'Friend request cancelled.';
            } else if (action === 'remove-friend') {
                url = `/api/v1/friends/${userId}`;
                method = 'DELETE';
                successMessage = 'Friend removed from your network.';
            } else {
                return;
            }

            try {
                const response = await fetch(url, {
                    method,
                    credentials: 'include',
                });

                if (response.status === 401 || response.status === 403) {
                    window.location.href = '/login';
                    return;
                }

                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    throw new Error(data?.detail || 'Could not update your network');
                }

                await loadFriendNetwork(successMessage);
            } catch (error) {
                networkStatus.textContent = error?.message || 'Could not update your network.';
            }
        }

        // Load profile on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadEditableProfile().catch((error) => {
                console.error('Error loading editable profile:', error);
                showNoData();
            });
            loadProfile();
            loadFriendNetwork();
            setupCVUpload();
            loadResumes();
            const profileForm = document.getElementById('profileForm');
            if (profileForm) {
                profileForm.addEventListener('submit', saveEditableProfile);
            }
            const refreshNetworkButton = document.getElementById('refreshNetworkButton');
            if (refreshNetworkButton) {
                refreshNetworkButton.addEventListener('click', loadFriendNetwork);
            }
            const networkCard = document.querySelector('.network-card');
            if (networkCard) {
                networkCard.addEventListener('click', async (event) => {
                    const actionButton = event.target.closest('[data-network-action]');
                    if (!actionButton) {
                        return;
                    }

                    actionButton.disabled = true;
                    try {
                        await handleNetworkAction(
                            actionButton.dataset.networkAction,
                            actionButton.dataset.requestId,
                            actionButton.dataset.userId,
                        );
                    } finally {
                        if (document.body.contains(actionButton)) {
                            actionButton.disabled = false;
                        }
                    }
                });
            }
            const refreshBtn = document.getElementById('refreshCvList');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', loadResumes);
            }
        });

        // Fetch and render resumes list
        async function loadResumes() {
            const emptyState = document.getElementById('cvListEmpty');
            const tableWrapper = document.getElementById('cvTableWrapper');
            const tbody = document.getElementById('cvTableBody');
            emptyState.textContent = 'Loading...';
            emptyState.style.color = 'var(--gray)';
            tableWrapper.style.display = 'none';
            tbody.innerHTML = '';
            try {
                const res = await fetch('/api/v1/profile/cv', {
                    credentials: 'include',
                    cache: 'no-store',
                });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = '/login';
                    return;
                }
                if (!res.ok) throw new Error('Failed to load CVs');
                const data = await res.json();
                if (!data || data.length === 0) {
                    emptyState.textContent = 'No CV uploaded yet.';
                    emptyState.style.display = 'block';
                    return;
                }
                emptyState.style.display = 'none';
                tableWrapper.style.display = 'block';
                tbody.innerHTML = data.map(item => `
                    <tr style="border-bottom: 1px solid var(--light-gray);">
                        <td style="padding: 0.6rem 0; font-weight: 600; color: var(--text-color);">
                            <a href="${item.view_url}" target="_blank" style="color: var(--primary-color); text-decoration: none;">${item.original_filename}</a>
                        </td>
                        <td style="padding: 0.6rem 0; color: var(--gray);">${formatDate(item.created_at)}</td>
                        <td style="padding: 0.6rem 0;">
                            <button data-resume-id="${item.id}" class="delete-cv-btn" style="background: none; border: none; color: #EF4444; font-weight: 600; cursor: pointer;">Delete</button>
                        </td>
                    </tr>
                `).join('');
                attachDeleteHandlers();
            } catch (err) {
                emptyState.textContent = 'Error loading CV list';
                emptyState.style.color = '#EF4444';
                emptyState.style.display = 'block';
            }
        }

        function formatDate(dateStr) {
            if (!dateStr) return '-';
            const d = new Date(dateStr);
            return d.toLocaleDateString();
        }

        function attachDeleteHandlers() {
            const buttons = document.querySelectorAll('.delete-cv-btn');
            buttons.forEach(btn => {
                btn.addEventListener('click', async () => {
                    const resumeId = btn.getAttribute('data-resume-id');
                    btn.textContent = 'Deleting...';
                    btn.disabled = true;
                    try {
                        const res = await fetch(`/api/v1/profile/cv/${resumeId}`, {
                            method: 'DELETE',
                            credentials: 'include'
                        });
                        if (res.status === 401 || res.status === 403) {
                            window.location.href = '/login';
                            return;
                        }
                        if (!res.ok) throw new Error('Delete failed');
                        await loadResumes();
                    } catch (err) {
                        btn.textContent = 'Delete';
                        btn.disabled = false;
                        alert('Could not delete CV');
                    }
                });
            });
        }

        // CV Upload functionality
        function setupCVUpload() {
            const uploadArea = document.getElementById('uploadArea');
            const cvFile = document.getElementById('cvFile');
            const uploadBtn = document.getElementById('uploadBtn');
            const filePreview = document.getElementById('filePreview');
            const removeFileBtn = document.getElementById('removeFile');
            const uploadStatus = document.getElementById('uploadStatus');
            let selectedFile = null;

            // Click to upload
            uploadArea.addEventListener('click', () => cvFile.click());

            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.style.backgroundColor = '#DDD6FE';
                uploadArea.style.borderColor = '#0F766E';
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.style.backgroundColor = '#EDE9FE';
                uploadArea.style.borderColor = '#0F766E';
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.style.backgroundColor = '#F0F4FF';
                uploadArea.style.borderColor = 'var(--primary-color)';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    handleFileSelect(files[0]);
                }
            });

            // File input change
            cvFile.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelect(e.target.files[0]);
                }
            });

            // Handle file selection
            function handleFileSelect(file) {
                const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword'];
                const maxSize = 5 * 1024 * 1024; // 5MB

                if (!validTypes.includes(file.type)) {
                    uploadStatus.textContent = '❌ Only PDF and DOCX files are allowed';
                    uploadStatus.style.color = '#EF4444';
                    return;
                }

                if (file.size > maxSize) {
                    uploadStatus.textContent = '❌ File size must be less than 5MB';
                    uploadStatus.style.color = '#EF4444';
                    return;
                }

                selectedFile = file;
                const fileName = file.name;
                const fileSize = (file.size / 1024).toFixed(2) + ' KB';

                document.getElementById('fileName').textContent = fileName;
                document.getElementById('fileSize').textContent = fileSize;
                filePreview.style.display = 'block';
                uploadBtn.disabled = false;
                uploadStatus.textContent = '';
            }

            // Remove file
            removeFileBtn.addEventListener('click', () => {
                selectedFile = null;
                cvFile.value = '';
                filePreview.style.display = 'none';
                uploadBtn.disabled = true;
                uploadStatus.textContent = '';
            });

            // Upload file
            uploadBtn.addEventListener('click', async () => {
                if (!selectedFile) return;

                uploadBtn.disabled = true;
                uploadStatus.textContent = '⏳ Uploading...';
                uploadStatus.style.color = '#999999';

                const formData = new FormData();
                formData.append('cv', selectedFile);

                try {
                    const response = await fetch('/api/v1/profile/cv/upload', {
                        method: 'POST',
                        credentials: 'include',
                        body: formData,
                        timeout: 30000
                    });

                    if (response.ok) {
                        uploadStatus.textContent = '✅ CV uploaded successfully!';
                        uploadStatus.style.color = '#22C55E';
                        await loadResumes();
                        setTimeout(() => {
                            selectedFile = null;
                            cvFile.value = '';
                            filePreview.style.display = 'none';
                            uploadBtn.disabled = true;
                            uploadStatus.textContent = '';
                        }, 2000);
                    } else {
                        console.error('Upload response:', response.status);
                        if (response.status === 401 || response.status === 403) {
                            window.location.href = '/login';
                            return;
                        }
                        uploadStatus.textContent = '❌ Upload failed. Please try again.';
                        uploadStatus.style.color = '#EF4444';
                        uploadBtn.disabled = false;
                    }
                } catch (error) {
                    console.error('Upload error:', error);
                    uploadStatus.textContent = '❌ Error uploading file';
                    uploadStatus.style.color = '#EF4444';
                    uploadBtn.disabled = false;
                }
            });
        }

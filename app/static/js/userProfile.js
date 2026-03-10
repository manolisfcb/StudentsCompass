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

        // Load profile on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadEditableProfile().catch((error) => {
                console.error('Error loading editable profile:', error);
                showNoData();
            });
            loadProfile();
            setupCVUpload();
            loadResumes();
            const profileForm = document.getElementById('profileForm');
            if (profileForm) {
                profileForm.addEventListener('submit', saveEditableProfile);
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

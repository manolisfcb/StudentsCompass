document.addEventListener('DOMContentLoaded', async () => {
    const welcomeMessage = document.getElementById('welcome-message');

    const setResourceLink = (elementId, targetUrl) => {
        const link = document.getElementById(elementId);
        if (!link) {
            return;
        }

        link.href = typeof targetUrl === 'string' && targetUrl.trim() ? targetUrl : '/resources';
    };

    try {
        const dashboardResponse = await fetch('/api/v1/students_dashboard', {
            credentials: 'include',
        });

        if (!dashboardResponse.ok) {
            if (dashboardResponse.status === 401 || dashboardResponse.status === 403) {
                window.location.href = '/login';
            } else {
                console.error('Failed to load dashboard data:', dashboardResponse.status);
            }
            return;
        }

        const data = await dashboardResponse.json();

        if (data.user) {
            welcomeMessage.textContent = `Welcome Back, ${data.user.nickname || data.user.email || 'Student'}!`;
        }

        document.getElementById('overall-progress').textContent = `${data.stats.overall_progress}%`;
        document.getElementById('total-applications').textContent = data.stats.total_applications;
        document.getElementById('interviews-scheduled').textContent = data.stats.interviews_scheduled;
        document.getElementById('offers-received').textContent = data.stats.offers_received;

        document.getElementById('resume-progress').textContent = `${data.progress.resume}%`;
        document.getElementById('resume-progress-bar').style.width = `${data.progress.resume}%`;

        document.getElementById('linkedin-progress').textContent = `${data.progress.linkedin}%`;
        document.getElementById('linkedin-progress-bar').style.width = `${data.progress.linkedin}%`;

        document.getElementById('interview-progress').textContent = `${data.progress.interview_prep}%`;
        document.getElementById('interview-progress-bar').style.width = `${data.progress.interview_prep}%`;

        const navigation = data.resource_navigation || {};
        setResourceLink('resume-progress-link', navigation.resume);
        setResourceLink('linkedin-progress-link', navigation.linkedin);
        setResourceLink('interview-progress-link', navigation.interview_prep);

        document.getElementById('status-applied').textContent = `${data.application_breakdown.applied} roles`;
        document.getElementById('status-review').textContent = `${data.application_breakdown.in_review} apps`;
        document.getElementById('status-interviews').textContent = `${data.application_breakdown.interviews} scheduled`;
        document.getElementById('status-offers').textContent = data.application_breakdown.offers;
    } catch (error) {
        console.error('Error loading dashboard:', error);
        window.location.href = '/login';
    }
});

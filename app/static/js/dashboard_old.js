document.addEventListener('DOMContentLoaded', async () => {
    document.querySelectorAll('[data-progress-value]').forEach((progressBar) => {
        progressBar.style.width = `${progressBar.dataset.progressValue}%`;
    });

    const token = localStorage.getItem('bearer_token');
    const welcomeMessage = document.getElementById('welcome-message');

    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        const response = await fetch('/api/v1/users/me', {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.ok) {
            const user = await response.json();
            welcomeMessage.textContent = `Welcome Back, ${user.nickname || user.email}!`;
            return;
        }
    } catch (_) {}

    localStorage.removeItem('bearer_token');
    window.location.href = '/login';
});

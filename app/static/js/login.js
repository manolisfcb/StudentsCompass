const loginAuthContainer = document.getElementById('auth-container');
const loginTypeRadios = document.querySelectorAll('input[name="login-type"]');

function setLoginAuthMode(mode) {
    loginAuthContainer?.classList.toggle('company-mode', mode === 'company');
}

loginTypeRadios.forEach((radio) => {
    radio.addEventListener('change', (event) => {
        if (event.target.checked) {
            setLoginAuthMode(event.target.value);
        }
    });
});

setLoginAuthMode(document.querySelector('input[name="login-type"]:checked')?.value || 'student');

document.getElementById('login-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);
    const errorMessage = document.getElementById('error-message');
    const loginType = document.querySelector('input[name="login-type"]:checked')?.value || 'student';
    const isStudent = loginType === 'student';
    const loginEndpoint = isStudent ? '/auth/jwt/login' : '/api/v1/auth/company/login';
    const dashboardUrl = isStudent ? '/dashboard' : '/company-dashboard';

    errorMessage.textContent = '';
    errorMessage.classList.remove('is-visible');

    try {
        const response = await fetch(loginEndpoint, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        });

        if (response.ok) {
            try {
                localStorage.removeItem('bearer_token');
                localStorage.removeItem('company_token');
                localStorage.removeItem('account_type');
            } catch (storageError) {
                console.warn('Storage cleanup skipped:', storageError);
            }

            window.location.assign(dashboardUrl);
            return;
        }

        let message = 'Login failed. Please check your credentials.';
        try {
            const errorData = await response.json();
            message = errorData.detail || message;
        } catch (_) {}
        errorMessage.textContent = message;
        errorMessage.classList.add('is-visible');
    } catch (error) {
        console.error('Login error:', error);
        errorMessage.textContent = 'An unexpected error occurred. Please try again.';
        errorMessage.classList.add('is-visible');
    }
});

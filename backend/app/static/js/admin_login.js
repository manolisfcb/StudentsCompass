async function handleAdminLogin(event) {
    event.preventDefault();

    const btn = document.getElementById('loginBtn');
    const errBox = document.getElementById('loginError');
    const email = document.getElementById('adminEmail').value;
    const password = document.getElementById('adminPassword').value;

    errBox.classList.remove('visible');
    btn.disabled = true;
    btn.textContent = 'Signing in…';

    try {
        const loginRes = await fetch('/auth/jwt/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ username: email, password }),
            credentials: 'include',
        });

        if (!loginRes.ok) {
            throw new Error('Invalid credentials');
        }

        const checkRes = await fetch('/api/v1/admin/stats', {
            credentials: 'include',
        });

        if (!checkRes.ok) {
            throw new Error('Not an admin account');
        }

        window.location.href = '/admin';
    } catch (error) {
        errBox.textContent = error.message === 'Not an admin account'
            ? 'This account does not have admin privileges.'
            : 'Invalid email or password.';
        errBox.classList.add('visible');
        btn.disabled = false;
        btn.textContent = 'Sign In';
    }
}

document.getElementById('adminLoginForm')?.addEventListener('submit', handleAdminLogin);

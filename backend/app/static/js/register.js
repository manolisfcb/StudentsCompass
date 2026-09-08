const registerAuthContainer = document.getElementById('auth-container');
const accountTypeStudentRadio = document.getElementById('reg-type-student');
const accountTypeCompanyRadio = document.getElementById('reg-type-company');
const studentForm = document.getElementById('student-form');
const companyForm = document.getElementById('company-form');

function setRegisterAuthMode(mode) {
    const isCompany = mode === 'company';
    registerAuthContainer?.classList.toggle('company-mode', isCompany);
    studentForm?.classList.toggle('registration-form-hidden', isCompany);
    companyForm?.classList.toggle('registration-form-hidden', !isCompany);
}

accountTypeStudentRadio?.addEventListener('change', (event) => {
    if (event.target.checked) {
        setRegisterAuthMode('student');
    }
});

accountTypeCompanyRadio?.addEventListener('change', (event) => {
    if (event.target.checked) {
        setRegisterAuthMode('company');
    }
});

setRegisterAuthMode(document.querySelector('input[name="account-type"]:checked')?.value || 'student');

function resetRegisterMessages() {
    const errorMessage = document.getElementById('error-message');
    const successMessage = document.getElementById('success-message');

    errorMessage.textContent = '';
    successMessage.textContent = '';
    errorMessage.classList.remove('is-visible');
    successMessage.classList.remove('is-visible');

    return { errorMessage, successMessage };
}

document.getElementById('student-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();

    const email = document.getElementById('student_email').value;
    const password = document.getElementById('student_password').value;
    const firstName = document.getElementById('student_first_name').value;
    const lastName = document.getElementById('student_last_name').value;
    const nickname = document.getElementById('student_nickname').value;
    const confirmPassword = document.getElementById('student_confirm_password').value;
    const { errorMessage, successMessage } = resetRegisterMessages();

    if (password !== confirmPassword) {
        errorMessage.textContent = 'Passwords do not match.';
        errorMessage.classList.add('is-visible');
        return;
    }

    if (password.length < 8) {
        errorMessage.textContent = 'Password must be at least 8 characters long.';
        errorMessage.classList.add('is-visible');
        return;
    }

    try {
        const response = await fetch('/api/v1/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email,
                password,
                first_name: firstName,
                last_name: lastName,
                nickname,
            }),
        });

        if (response.ok) {
            successMessage.textContent = 'Student account created successfully! Redirecting to login...';
            successMessage.classList.add('is-visible');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            return;
        }

        const errorData = await response.json();
        errorMessage.textContent = errorData.detail || 'Registration failed. Please try again.';
        errorMessage.classList.add('is-visible');
    } catch (error) {
        errorMessage.textContent = 'An unexpected error occurred. Please try again.';
        errorMessage.classList.add('is-visible');
    }
});

document.getElementById('company-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();

    const companyName = document.getElementById('company_name').value;
    const industry = document.getElementById('company_industry').value;
    const contactPerson = document.getElementById('company_contact_person').value;
    const email = document.getElementById('company_email').value;
    const phone = document.getElementById('company_phone').value;
    const website = document.getElementById('company_website').value;
    const location = document.getElementById('company_location').value;
    const description = document.getElementById('company_description').value;
    const password = document.getElementById('company_password').value;
    const confirmPassword = document.getElementById('company_confirm_password').value;
    const { errorMessage, successMessage } = resetRegisterMessages();

    if (password !== confirmPassword) {
        errorMessage.textContent = 'Passwords do not match.';
        errorMessage.classList.add('is-visible');
        return;
    }

    if (password.length < 8) {
        errorMessage.textContent = 'Password must be at least 8 characters long.';
        errorMessage.classList.add('is-visible');
        return;
    }

    try {
        const response = await fetch('/api/v1/auth/company/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email,
                password,
                company_name: companyName,
                industry,
                contact_person: contactPerson,
                phone,
                website,
                location,
                description,
            }),
        });

        if (response.ok) {
            successMessage.textContent = 'Company account created successfully! Redirecting to login...';
            successMessage.classList.add('is-visible');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            return;
        }

        const errorData = await response.json();
        errorMessage.textContent = errorData.detail || 'Registration failed. Please try again.';
        errorMessage.classList.add('is-visible');
    } catch (error) {
        errorMessage.textContent = 'An unexpected error occurred. Please try again.';
        errorMessage.classList.add('is-visible');
    }
});

function clearLegacyTokens() {
    try {
        localStorage.removeItem('bearer_token');
        localStorage.removeItem('company_token');
        localStorage.removeItem('account_type');
    } catch (_) {}
}

function closeMenu(menu) {
    menu.classList.remove('active');
}

function bindMenu(toggleSelector, menuSelector) {
    const toggle = document.querySelector(toggleSelector);
    const menu = document.querySelector(menuSelector);

    if (!toggle || !menu) {
        return;
    }

    toggle.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        menu.classList.toggle('active');
    });

    menu.querySelectorAll('[data-mobile-menu-close]').forEach((link) => {
        link.addEventListener('click', () => closeMenu(menu));
    });

    document.addEventListener('click', (event) => {
        if (!menu.contains(event.target) && !toggle.contains(event.target)) {
            closeMenu(menu);
        }
    });
}

function createLogoutModal() {
    const modal = document.createElement('div');
    modal.className = 'logout-modal';
    modal.innerHTML = `
        <div class="logout-modal-content">
            <div class="logout-modal-header">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#FB7185" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
            </div>
            <h2>See you later!</h2>
            <p>Are you sure you want to log out?</p>
            <div class="logout-modal-buttons">
                <button class="logout-btn-cancel" type="button">Cancel</button>
                <button class="logout-btn-confirm" type="button">Log Out</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    requestAnimationFrame(() => {
        modal.classList.add('active');
    });

    return modal;
}

function bindLogout(linkSelector, endpoints, options = {}) {
    const link = document.querySelector(linkSelector);
    if (!link) {
        return;
    }

    const redirectTo = options.redirectTo || '/login';

    link.addEventListener('click', (event) => {
        event.preventDefault();

        const modal = createLogoutModal();
        const cancelBtn = modal.querySelector('.logout-btn-cancel');
        const confirmBtn = modal.querySelector('.logout-btn-confirm');

        const closeModal = () => {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        };

        cancelBtn.addEventListener('click', closeModal);

        confirmBtn.addEventListener('click', async () => {
            modal.classList.add('logging-out');

            try {
                await Promise.allSettled(
                    endpoints.map((url) =>
                        fetch(url, {
                            method: 'POST',
                            credentials: 'include',
                        })
                    )
                );
            } catch (error) {
                console.error('Logout error:', error);
            } finally {
                clearLegacyTokens();

                if (options.fadeOutBody) {
                    document.body.classList.add('page-is-exiting');
                    setTimeout(() => {
                        window.location.href = redirectTo;
                    }, 300);
                    return;
                }

                window.location.href = redirectTo;
            }
        });

        modal.addEventListener('click', (modalEvent) => {
            if (modalEvent.target === modal) {
                closeModal();
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    bindMenu('#mobile-menu-toggle', '#mobile-menu');
    bindMenu('#company-mobile-menu-toggle', '#company-mobile-menu');
    bindMenu('.marketing-nav .mobile-menu-toggle', '#mobile-menu');

    bindLogout('#logout-link', ['/auth/jwt/logout', '/api/v1/auth/company/logout'], {
        fadeOutBody: true,
    });
    bindLogout('#company-logout-link', ['/api/v1/auth/company/logout', '/auth/jwt/logout']);
});

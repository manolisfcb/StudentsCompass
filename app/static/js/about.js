const aboutRefData = [
    {
        title: '49% — Lack of Relevant Experience in Entry-Level Hiring',
        body: '<p><strong>Express Employment Professionals / Harris Poll (Canada, 2025)</strong></p><p>Survey of 504 hiring decision-makers across Canada. 45% of companies say candidates don\\'t have relevant experience; 54% say it\\'s difficult to find the right candidates.</p><p>"Lack of relevant experience" cited as a top hiring barrier for entry-level positions.</p>',
        url: 'https://www.expresspros.ca/newsroom/news-releases/news-releases/2025/02/canadian-companies-say-worsening-skills-gap-and-navigating-ai-top-challenges-in-2025',
    },
    {
        title: '$30,680 — Average Cost of Employee Turnover in Canada',
        body: '<p><strong>Express Employment Professionals — Canadian Hiring Outlook (2026)</strong></p><p>Average cost of employee turnover per employee in Canada, including recruiting, training, and lost productivity. Hiring outlook dampened due to skills gaps and technological shifts.</p><p><strong>Robert Half Canada (2025)</strong></p><p>33% of Canadian professionals plan to search for a new job in 2026, signaling significant workforce rotation and compounding turnover costs for employers.</p>',
        url: 'https://www.expresspros.ca/newsroom/news-releases/news-releases/2025/12/canadian-hiring-outlook-dampens-in-first-half-of-2026',
        url2: 'https://press.roberthalf.ca/2025-12-10-Survey-One-third-of-Canadian-professionals-plan-to-search-for-a-new-job-in-2026',
    },
    {
        title: '82% — Resumes Misrepresent Candidate Skills',
        body: '<p><strong>Express Employment Professionals / Harris Poll (Canada, 2025)</strong></p><p>82% of hiring managers report that resumes sometimes or often misrepresent candidate skills. AI-generated content is making exaggeration even easier to produce at scale.</p><p>Data sourced from the Express Job Insights Canada survey program.</p>',
        url: 'https://www.expresspros.com/jobinsights-canada',
    },
];

document.addEventListener('DOMContentLoaded', () => {
    const backdrop = document.getElementById('refModalBackdrop');
    const title = document.getElementById('refModalTitle');
    const body = document.getElementById('refModalBody');
    const link = document.getElementById('refModalLink');
    const closeButtons = [document.getElementById('refModalCloseBtn'), document.getElementById('refModalDismissBtn')];
    let previousFocus = null;

    function closeRefModal() {
        backdrop.classList.remove('active');
        backdrop.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        if (previousFocus) {
            previousFocus.focus();
        }
    }

    function openRefModal(index) {
        const item = aboutRefData[index];
        if (!item) {
            return;
        }

        previousFocus = document.activeElement;
        title.textContent = item.title;

        let bodyHtml = item.body;
        if (item.url2) {
            bodyHtml += `<p class="ref-modal__extra-link"><a href="${item.url2}" target="_blank" rel="noopener noreferrer" class="ref-modal__inline-link">View additional source (Robert Half) ↗</a></p>`;
        }
        body.innerHTML = bodyHtml;
        link.href = item.url;

        backdrop.setAttribute('aria-hidden', 'false');
        backdrop.classList.add('active');
        document.body.style.overflow = 'hidden';
        closeButtons[0]?.focus();
    }

    document.querySelectorAll('[data-ref-index]').forEach((card) => {
        const open = () => openRefModal(Number(card.dataset.refIndex));

        card.addEventListener('click', open);
        card.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                open();
            }
        });
    });

    closeButtons.forEach((button) => {
        button?.addEventListener('click', closeRefModal);
    });

    backdrop?.addEventListener('click', (event) => {
        if (event.target === backdrop) {
            closeRefModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && backdrop?.classList.contains('active')) {
            closeRefModal();
        }
    });

    backdrop?.addEventListener('keydown', (event) => {
        if (event.key !== 'Tab') {
            return;
        }

        const modal = backdrop.querySelector('.ref-modal');
        const focusable = modal?.querySelectorAll('button, [href], [tabindex]:not([tabindex="-1"])');
        if (!focusable || !focusable.length) {
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
});

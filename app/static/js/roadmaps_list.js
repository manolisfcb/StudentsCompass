function escapeRoadmapHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function applyRoadmapProgress(root = document) {
    root.querySelectorAll('.roadmap-progress-fill[data-progress]').forEach((element) => {
        element.style.width = `${Number(element.dataset.progress || 0)}%`;
    });
}

function bindRoadmapCardClicks() {
    document.querySelectorAll('.roadmap-clickable').forEach((card) => {
        if (card.dataset.bound === '1') {
            return;
        }

        card.dataset.bound = '1';
        const href = card.dataset.href;
        if (!href) {
            return;
        }

        card.addEventListener('click', (event) => {
            if (event.target.closest('a, button, input, select, textarea, label')) {
                return;
            }
            window.location.href = href;
        });

        card.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                window.location.href = href;
            }
        });
    });
}

function renderSavedRoadmaps(items) {
    const container = document.getElementById('my-roadmaps-container');
    if (!container) {
        return;
    }

    if (!Array.isArray(items) || items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h4>No saved roadmaps yet</h4>
                <p>Save a roadmap from below to keep it in your workspace.</p>
            </div>
        `;
        bindRoadmapCardClicks();
        return;
    }

    const cards = items.map((item) => {
        const roadmap = item.roadmap || {};
        const slug = escapeRoadmapHtml(roadmap.slug || '');
        const title = escapeRoadmapHtml(roadmap.title || '');
        const difficulty = escapeRoadmapHtml(roadmap.difficulty || '');
        const minWeeks = Number(roadmap.duration_weeks_min || 0);
        const maxWeeks = Number(roadmap.duration_weeks_max || 0);
        const progress = Number(roadmap.overall_progress_percent || 0);
        const completed = Number(roadmap.completed_tasks || 0);
        const total = Number(roadmap.total_tasks || 0);

        return `
            <article class="saved-card roadmap-clickable" data-href="/roadmaps/${slug}" tabindex="0" role="link">
                <div class="saved-card-top">
                    <h4>${title}</h4>
                    <span class="progress-chip">${progress}%</span>
                </div>
                <p>${minWeeks}-${maxWeeks} weeks • ${difficulty}</p>
                <div class="progress-track"><span class="roadmap-progress-fill" data-progress="${progress}"></span></div>
                <small>${completed}/${total} tasks completed</small>
                <a href="/roadmaps/${slug}" class="card-link">Continue roadmap</a>
            </article>
        `;
    }).join('');

    container.innerHTML = `<div class="saved-grid">${cards}</div>`;
    bindRoadmapCardClicks();
    applyRoadmapProgress(container);
}

async function refreshSavedRoadmaps() {
    try {
        const response = await fetch('/api/v1/me/roadmaps', {
            headers: { Accept: 'application/json' },
        });
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        renderSavedRoadmaps(data);
    } catch (_) {
        // Keep server-rendered fallback.
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindRoadmapCardClicks();
    applyRoadmapProgress();
    refreshSavedRoadmaps();
});

window.addEventListener('pageshow', () => {
    refreshSavedRoadmaps();
});

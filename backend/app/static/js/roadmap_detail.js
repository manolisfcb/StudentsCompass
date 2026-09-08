const detailItems = JSON.parse(document.getElementById('roadmap-detail-items')?.textContent || '{}');
const roadmapDetailMeta = JSON.parse(document.getElementById('roadmap-detail-meta')?.textContent || '{}');
const firstItemId = roadmapDetailMeta.firstItemId ?? null;
const roadmapSlug = roadmapDetailMeta.roadmapSlug;

const detailsKindEl = document.getElementById('details-kind');
const detailsTitleEl = document.getElementById('details-title');
const detailsStageEl = document.getElementById('details-stage');
const detailsDescriptionEl = document.getElementById('details-description');
const detailsResourceEl = document.getElementById('details-resource');
const criteriaBlockEl = document.getElementById('criteria-block');
const criteriaListEl = document.getElementById('criteria-list');
const rubricBlockEl = document.getElementById('rubric-block');
const rubricListEl = document.getElementById('rubric-list');

const submissionFormEl = document.getElementById('submission-form');
const submissionRepoEl = document.getElementById('submission-repo');
const submissionLiveEl = document.getElementById('submission-live');
const submissionNotesEl = document.getElementById('submission-notes');
const submissionStatusEl = document.getElementById('submission-status');
const submissionButtonEl = document.getElementById('submission-button');
const submissionFeedbackEl = document.getElementById('submission-feedback');

const saveToggleBtn = document.getElementById('save-toggle-btn');
const saveCounterValue = document.getElementById('save-counter-value');

let activeProjectId = null;

function setRoadmapProgress(element, value) {
    if (!element) {
        return;
    }

    element.dataset.progress = value;
    element.style.width = `${value}%`;
}

function renderDetails(itemId) {
    const item = detailItems[itemId];
    if (!item) {
        return;
    }

    detailsKindEl.textContent = item.kind === 'project' ? 'Project details' : 'Task details';
    detailsTitleEl.textContent = item.title;
    detailsStageEl.textContent = item.stage_title ? `Stage: ${item.stage_title}` : '';
    detailsDescriptionEl.textContent = item.description || '';

    detailsResourceEl.innerHTML = '';
    if (item.resource_url) {
        const link = document.createElement('a');
        link.href = item.resource_url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = item.resource_title || 'Open resource';
        detailsResourceEl.appendChild(link);
    }

    criteriaListEl.innerHTML = '';
    rubricListEl.innerHTML = '';

    if (item.kind === 'project') {
        criteriaBlockEl.classList.remove('hidden');
        rubricBlockEl.classList.remove('hidden');
        submissionFormEl.classList.remove('hidden');

        (item.acceptance_criteria || []).forEach((line) => {
            const li = document.createElement('li');
            li.textContent = line;
            criteriaListEl.appendChild(li);
        });

        const rubric = item.rubric || {};
        Object.keys(rubric).forEach((key) => {
            const li = document.createElement('li');
            li.textContent = `${key.replace('_', ' ')}: ${rubric[key]}`;
            rubricListEl.appendChild(li);
        });

        activeProjectId = itemId;
        submissionRepoEl.value = item.submission?.repo_url || '';
        submissionLiveEl.value = item.submission?.live_url || '';
        submissionNotesEl.value = item.submission?.notes || '';
        submissionStatusEl.value = item.submission?.status || 'draft';
        submissionFeedbackEl.textContent = '';
        return;
    }

    criteriaBlockEl.classList.add('hidden');
    rubricBlockEl.classList.add('hidden');
    submissionFormEl.classList.add('hidden');
    activeProjectId = null;
}

async function patchTaskProgress(taskId, status) {
    const response = await fetch(`/api/v1/tasks/${taskId}/progress`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
    });

    if (!response.ok) {
        throw new Error('Failed to update task status');
    }

    const payload = await response.json();
    document.getElementById('overall-progress-label').textContent = `${payload.roadmap_progress_percent}%`;
    setRoadmapProgress(document.getElementById('overall-progress-bar'), payload.roadmap_progress_percent);
    document.getElementById('overall-progress-count').textContent = `${payload.completed_tasks}/${payload.total_tasks} tasks completed`;

    const stageLabel = document.getElementById(`stage-progress-label-${payload.stage_id}`);
    const stageBar = document.getElementById(`stage-progress-bar-${payload.stage_id}`);
    if (stageLabel) {
        stageLabel.textContent = `${payload.stage_progress_percent}%`;
    }
    setRoadmapProgress(stageBar, payload.stage_progress_percent);
}

document.querySelectorAll('.task-status').forEach((select) => {
    select.addEventListener('change', async (event) => {
        const taskId = event.target.dataset.taskId;
        const status = event.target.value;
        const checkbox = document.querySelector(`.task-checkbox[data-task-id="${taskId}"]`);
        if (checkbox) {
            checkbox.checked = status === 'completed';
        }

        try {
            await patchTaskProgress(taskId, status);
        } catch (_) {
            event.target.value = checkbox && checkbox.checked ? 'completed' : 'not_started';
            alert('Could not update progress. Please try again.');
        }
    });
});

document.querySelectorAll('.task-checkbox').forEach((checkbox) => {
    checkbox.addEventListener('change', async (event) => {
        const taskId = event.target.dataset.taskId;
        const status = event.target.checked ? 'completed' : 'not_started';
        const select = document.querySelector(`.task-status[data-task-id="${taskId}"]`);
        if (select) {
            select.value = status;
        }

        try {
            await patchTaskProgress(taskId, status);
        } catch (_) {
            event.target.checked = !event.target.checked;
            if (select) {
                select.value = event.target.checked ? 'completed' : 'not_started';
            }
            alert('Could not update progress. Please try again.');
        }
    });
});

document.querySelectorAll('[data-item-id]').forEach((button) => {
    button.addEventListener('click', () => renderDetails(button.dataset.itemId));
});

document.querySelectorAll('[data-stage-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
        button.closest('.stage-card')?.classList.toggle('collapsed');
    });
});

saveToggleBtn.addEventListener('click', async () => {
    const saved = saveToggleBtn.dataset.saved === '1';
    const method = saved ? 'DELETE' : 'POST';
    const response = await fetch(`/api/v1/roadmaps/${roadmapSlug}/save`, { method });

    if (!response.ok) {
        alert('Could not update saved state.');
        return;
    }

    const payload = await response.json();
    saveToggleBtn.dataset.saved = payload.saved ? '1' : '0';
    saveToggleBtn.textContent = payload.saved ? 'Unsave roadmap' : 'Save roadmap';
    saveCounterValue.textContent = payload.popularity;
});

submissionFormEl.addEventListener('submit', (event) => {
    event.preventDefault();
});

submissionButtonEl.addEventListener('click', async () => {
    if (!activeProjectId) {
        return;
    }

    submissionFeedbackEl.textContent = 'Saving...';
    const body = {
        repo_url: submissionRepoEl.value || null,
        live_url: submissionLiveEl.value || null,
        notes: submissionNotesEl.value || null,
        status: submissionStatusEl.value,
    };

    const response = await fetch(`/api/v1/projects/${activeProjectId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        submissionFeedbackEl.textContent = 'Save failed. Try again.';
        return;
    }

    const payload = await response.json();
    detailItems[activeProjectId].submission = payload;
    submissionFeedbackEl.textContent = 'Submission saved.';
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.roadmap-progress-fill[data-progress]').forEach((element) => {
        setRoadmapProgress(element, Number(element.dataset.progress || 0));
    });

    if (firstItemId) {
        renderDetails(firstItemId);
    }
});

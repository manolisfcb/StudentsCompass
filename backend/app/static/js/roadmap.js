function filterRoadmaps(category, button) {
    const cards = document.querySelectorAll('.roadmap-card');
    const buttons = document.querySelectorAll('[data-roadmap-filter]');

    buttons.forEach((item) => item.classList.remove('active'));
    button?.classList.add('active');

    cards.forEach((card) => {
        if (category === 'all') {
            card.style.display = 'block';
            return;
        }

        const cardCategory = card.getAttribute('data-category');
        card.style.display = cardCategory === category ? 'block' : 'none';
    });
}

document.querySelectorAll('[data-roadmap-filter]').forEach((button) => {
    button.addEventListener('click', () => {
        filterRoadmaps(button.dataset.roadmapFilter, button);
    });
});

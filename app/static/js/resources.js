(function () {
  const grid = document.getElementById('resources-grid');
  const cards = Array.from(document.querySelectorAll('.resource-card'));
  const chips = Array.from(document.querySelectorAll('.filter-chip'));
  const searchInput = document.getElementById('resource-search');
  const sortSelect = document.getElementById('resource-sort');
  const emptyState = document.getElementById('resources-empty');

  let activeCategory = 'all';

  function getFilteredCards() {
    const q = (searchInput?.value || '').trim().toLowerCase();
    let list = cards.filter((card) => {
      const category = (card.dataset.category || '').toLowerCase();
      if (activeCategory !== 'all' && category !== activeCategory) return false;

      if (!q) return true;
      const haystack = `${card.dataset.title || ''} ${card.dataset.description || ''} ${card.dataset.tags || ''}`.toLowerCase();
      return haystack.includes(q);
    });

    const sort = sortSelect?.value || 'recent';
    if (sort === 'name') {
      list.sort((a, b) => (a.dataset.title || '').localeCompare(b.dataset.title || ''));
    } else if (sort === 'duration') {
      list.sort((a, b) => Number(a.dataset.duration || 999999) - Number(b.dataset.duration || 999999));
    } else {
      list.sort((a, b) => new Date(b.dataset.createdAt || 0) - new Date(a.dataset.createdAt || 0));
    }

    return list;
  }

  function render() {
    if (!grid) return;
    const filtered = getFilteredCards();

    cards.forEach((card) => {
      card.style.display = 'none';
      grid.appendChild(card);
    });

    filtered.forEach((card) => {
      card.style.display = '';
      grid.appendChild(card);
    });

    if (emptyState) emptyState.style.display = filtered.length ? 'none' : 'block';
  }

  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      activeCategory = chip.dataset.category || 'all';
      chips.forEach((btn) => btn.classList.remove('active'));
      chip.classList.add('active');
      render();
    });
  });

  searchInput?.addEventListener('input', render);
  sortSelect?.addEventListener('change', render);

  render();
})();

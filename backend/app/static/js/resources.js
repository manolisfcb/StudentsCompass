(function () {
  const mandatoryGrid = document.getElementById('mandatory-grid');
  const complementaryGrid = document.getElementById('complementary-grid');
  const mandatorySection = document.getElementById('mandatory-section');
  const complementarySection = document.getElementById('complementary-section');
  const cards = Array.from(document.querySelectorAll('.resource-card'));
  const chips = Array.from(document.querySelectorAll('.filter-chip'));
  const searchInput = document.getElementById('resource-search');
  const sortSelect = document.getElementById('resource-sort');
  const emptyState = document.getElementById('resources-empty');

  let activeCategory = 'all';

  function getFilteredCards() {
    const q = (searchInput?.value || '').trim().toLowerCase();
    const list = cards.filter((card) => {
      const category = (card.dataset.category || '').toLowerCase();
      if (activeCategory !== 'all' && category !== activeCategory) return false;

      if (!q) return true;
      const haystack = `${card.dataset.title || ''} ${card.dataset.description || ''} ${card.dataset.tags || ''}`.toLowerCase();
      return haystack.includes(q);
    });

    return list;
  }

  function sortCards(list) {
    const sorted = [...list];
    const sort = sortSelect?.value || 'recent';
    if (sort === 'name') {
      sorted.sort((a, b) => (a.dataset.title || '').localeCompare(b.dataset.title || ''));
    } else if (sort === 'duration') {
      sorted.sort((a, b) => Number(a.dataset.duration || 999999) - Number(b.dataset.duration || 999999));
    } else {
      sorted.sort((a, b) => new Date(b.dataset.createdAt || 0) - new Date(a.dataset.createdAt || 0));
    }
    return sorted;
  }

  function render() {
    if (!mandatoryGrid || !complementaryGrid) return;
    const filtered = getFilteredCards();
    const mandatoryCards = sortCards(filtered.filter((card) => card.dataset.mandatory === '1'));
    const complementaryCards = sortCards(filtered.filter((card) => card.dataset.mandatory !== '1'));

    cards.forEach((card) => {
      card.style.display = 'none';
      if (card.dataset.mandatory === '1') {
        mandatoryGrid.appendChild(card);
      } else {
        complementaryGrid.appendChild(card);
      }
    });

    mandatoryCards.forEach((card) => {
      card.style.display = '';
      mandatoryGrid.appendChild(card);
    });

    complementaryCards.forEach((card) => {
      card.style.display = '';
      complementaryGrid.appendChild(card);
    });

    if (mandatorySection) mandatorySection.style.display = mandatoryCards.length ? '' : 'none';
    if (complementarySection) complementarySection.style.display = complementaryCards.length ? '' : 'none';
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

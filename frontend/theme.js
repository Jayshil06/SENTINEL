// Project SENTINEL — Persistent Dark / Light Mode Engine
(function() {
  function applyTheme(theme) {
    const isLight = theme === 'light';
    document.documentElement.classList.toggle('light-theme', isLight);
    
    // Update button icons & text across the page
    const icon = document.getElementById('theme-toggle-icon');
    const text = document.getElementById('theme-toggle-text');
    if (icon) {
      icon.className = isLight ? 'fa-solid fa-moon text-xs text-indigo-400' : 'fa-solid fa-sun text-xs text-amber-400';
    }
    if (text) {
      text.textContent = isLight ? 'Dark' : 'Light';
    }

    // If Leaflet map is present on page, switch base tile layer
    if (typeof map !== 'undefined' && typeof darkTiles !== 'undefined' && typeof osmTiles !== 'undefined') {
      try {
        if (isLight) {
          if (map.hasLayer(darkTiles)) map.removeLayer(darkTiles);
          if (!map.hasLayer(osmTiles)) osmTiles.addTo(map);
        } else {
          if (map.hasLayer(osmTiles)) map.removeLayer(osmTiles);
          if (!map.hasLayer(darkTiles)) darkTiles.addTo(map);
        }
      } catch (e) {
        console.warn("Map layer switch error:", e);
      }
    }

    localStorage.setItem('sentinel_theme', theme);
  }

  // Read saved theme or default to dark
  const savedTheme = localStorage.getItem('sentinel_theme') || 'dark';
  applyTheme(savedTheme);

  // Setup click listener when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(localStorage.getItem('sentinel_theme') || 'dark');
    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const currentTheme = localStorage.getItem('sentinel_theme') || 'dark';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
      });
    }
  });

  // Export globally for programmatic calls
  window.toggleSentinelTheme = function() {
    const currentTheme = localStorage.getItem('sentinel_theme') || 'dark';
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  };
})();

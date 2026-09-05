// Project SENTINEL — Law Enforcement Session & Cookie Auth Guard
(function() {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  const sessionCookie = getCookie('sentinel_session');

  // If no sentinel_session cookie, redirect immediately to login
  if (!sessionCookie) {
    const currentPath = window.location.pathname;
    // Do not redirect if already on the login page
    if (currentPath !== '/login' && !currentPath.endsWith('login.html')) {
      const fullTarget = currentPath + window.location.search;
      window.location.replace('/login?redirect=' + encodeURIComponent(fullTarget));
      return;
    }
  }

  // Intercept all API fetch requests: if 401 Unauthorized is returned, clear session and redirect to /login
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    if (response.status === 401 && !window.location.pathname.startsWith('/login')) {
      console.warn('[SENTINEL Security] 401 Unauthorized API response intercepted. Redirecting to login portal...');
      document.cookie = "sentinel_session=; path=/; max-age=0; SameSite=Lax";
      localStorage.removeItem('sentinel_user');
      const target = window.location.pathname + window.location.search;
      window.location.replace('/login?redirect=' + encodeURIComponent(target));
    }
    return response;
  };
  document.addEventListener('DOMContentLoaded', () => {
    let user = null;
    try {
      user = JSON.parse(localStorage.getItem('sentinel_user'));
    } catch(e) {}

    const officerDisplays = document.querySelectorAll('.officer-name-display');
    const officerBadges = document.querySelectorAll('.officer-badge-display');
    
    const displayName = (user && user.name) ? user.name : (sessionCookie ? `Officer (${sessionCookie})` : 'Inspector ABC');
    const displayBadge = (user && user.badge) ? user.badge : (sessionCookie || 'GP-POL-001');

    officerDisplays.forEach(el => el.textContent = displayName);
    officerBadges.forEach(el => el.textContent = displayBadge);

    // Attach logout handlers to all logout buttons/links
    document.querySelectorAll('.logout-btn, a[href="/login"]').forEach(el => {
      el.addEventListener('click', (e) => {
        // Clear cookie
        document.cookie = "sentinel_session=; path=/; max-age=0; SameSite=Lax";
        // Clear storage
        localStorage.removeItem('sentinel_user');
      });
    });
  });
})();

/**
 * Pharmora Landing / Home Page Interactive Client Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  initLandingSession();
  initMobileDrawer();
  initSolutionsDropdown();
  initOverviewModal();
  initThemeToggle();
  initSmoothScroll();
});

/* 1. Check Active User Session on Landing Page */
async function initLandingSession() {
  try {
    const res = await fetch('/api/auth/me');
    if (res.ok) {
      const data = await res.json();
      if (data.user) {
        // User is logged in: update CTAs to point to Dashboard
        const navLogin = document.getElementById('nav-btn-login');
        const navGetStarted = document.getElementById('nav-btn-get-started');
        const heroGetStarted = document.getElementById('hero-get-started-cta');
        const drawerLogin = document.getElementById('drawer-btn-login');
        const drawerGetStarted = document.getElementById('drawer-btn-get-started');

        if (navLogin) {
          navLogin.innerText = "Dashboard";
          navLogin.href = "/dashboard";
        }
        if (navGetStarted) {
          navGetStarted.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Dashboard`;
          navGetStarted.href = "/dashboard";
        }
        if (heroGetStarted) {
          heroGetStarted.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Go to Dashboard`;
          heroGetStarted.href = "/dashboard";
        }
        if (drawerLogin) {
          drawerLogin.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Dashboard`;
          drawerLogin.href = "/dashboard";
        }
        if (drawerGetStarted) {
          drawerGetStarted.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Dashboard`;
          drawerGetStarted.href = "/dashboard";
        }
      }
    }
  } catch (err) {
    // Session check failure, keep default public CTAs
  }
}

/* 2. Mobile Drawer Navigation */
function initMobileDrawer() {
  const menuBtn = document.getElementById('mobile-menu-btn');
  const drawer = document.getElementById('mobile-drawer');
  const overlay = document.getElementById('mobile-drawer-overlay');
  const closeBtn = document.getElementById('drawer-close-btn');
  const drawerLinks = document.querySelectorAll('.drawer-link, .drawer-sublink');

  const openDrawer = () => {
    if (drawer) drawer.classList.add('open');
    if (overlay) overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  };

  const closeDrawer = () => {
    if (drawer) drawer.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = '';
  };

  if (menuBtn) menuBtn.addEventListener('click', openDrawer);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  if (overlay) overlay.addEventListener('click', closeDrawer);

  drawerLinks.forEach(link => {
    link.addEventListener('click', closeDrawer);
  });
}

/* 3. Solutions Dropdown Handling */
function initSolutionsDropdown() {
  const dropdownBtn = document.getElementById('solutions-dropdown-btn');
  const dropdownMenu = document.getElementById('solutions-dropdown-menu');

  if (dropdownBtn && dropdownMenu) {
    dropdownBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const expanded = dropdownBtn.getAttribute('aria-expanded') === 'true';
      dropdownBtn.setAttribute('aria-expanded', !expanded);
      dropdownMenu.style.visibility = expanded ? 'hidden' : 'visible';
      dropdownMenu.style.opacity = expanded ? '0' : '1';
      dropdownMenu.style.pointerEvents = expanded ? 'none' : 'auto';
    });

    document.addEventListener('click', (e) => {
      if (!dropdownBtn.contains(e.target) && !dropdownMenu.contains(e.target)) {
        dropdownBtn.setAttribute('aria-expanded', 'false');
        dropdownMenu.style.visibility = 'hidden';
        dropdownMenu.style.opacity = '0';
        dropdownMenu.style.pointerEvents = 'none';
      }
    });
  }
}

/* 4. Watch Overview Modal */
function initOverviewModal() {
  const modal = document.getElementById('overview-modal');
  const openBtn = document.getElementById('btn-open-overview-modal');
  const closeBtn = document.getElementById('btn-close-overview-modal');
  const closeBtnSecondary = document.getElementById('btn-close-modal-secondary');

  const openModal = () => {
    if (modal) {
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  };

  const closeModal = () => {
    if (modal) {
      modal.style.display = 'none';
      document.body.style.overflow = '';
    }
  };

  if (openBtn) openBtn.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (closeBtnSecondary) closeBtnSecondary.addEventListener('click', closeModal);

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.style.display === 'flex') {
      closeModal();
    }
  });
}

/* 5. Theme Mode Toggle */
function initThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  if (!toggleBtn) return;

  const savedTheme = localStorage.getItem('pharmora_landing_theme');
  if (savedTheme === 'light') {
    document.body.classList.add('light-theme');
    toggleBtn.innerHTML = `<i class="fa-regular fa-sun" style="color:#F59E0B;"></i>`;
  }

  toggleBtn.addEventListener('click', () => {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    localStorage.setItem('pharmora_landing_theme', isLight ? 'light' : 'dark');
    toggleBtn.innerHTML = isLight 
      ? `<i class="fa-regular fa-sun" style="color:#F59E0B;"></i>` 
      : `<i class="fa-regular fa-moon"></i>`;
  });
}

/* 6. Smooth Scrolling with Sticky Header Offset */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#' || targetId === '#top') {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }

      const targetElem = document.querySelector(targetId);
      if (targetElem) {
        e.preventDefault();
        const headerHeight = 70;
        const targetPos = targetElem.getBoundingClientRect().top + window.pageYOffset - headerHeight;
        window.scrollTo({ top: targetPos, behavior: 'smooth' });
      }
    });
  });
}

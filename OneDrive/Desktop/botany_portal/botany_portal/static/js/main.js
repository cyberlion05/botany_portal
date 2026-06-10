// ── Scroll-reveal ─────────────────────────────────────────────────────────
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  });
}, { threshold: 0.08 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));

// ── Falling leaves in .hero ───────────────────────────────────────────────
const LEAF = '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M17 8C8 10 5.9 16.2 3.8 21.6c-.3.8.9 1.3 1.3.5C7 18 9 16 13 15c-2 1-3.5 2.7-4.5 5 5-1 9-5 9-12V8z"/></svg>';
document.querySelectorAll('.hero').forEach(hero => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  for (let i = 0; i < 9; i++) {
    const s = document.createElement('span');
    s.className = 'leaf-fall';
    s.innerHTML = LEAF;
    s.style.left = Math.random() * 100 + '%';
    s.style.animationDuration = (7 + Math.random() * 7) + 's';
    s.style.animationDelay = (-Math.random() * 10) + 's';
    s.style.transform = `scale(${0.6 + Math.random()})`;
    hero.appendChild(s);
  }
});

// ── Sidebar (authenticated layout) ───────────────────────────────────────
(function () {
  const btn       = document.getElementById('hamburgerBtn');
  const closeBtn  = document.getElementById('sidebarClose');
  const sidebar   = document.getElementById('sidebar');
  const overlay   = document.getElementById('sidebarOverlay');
  if (!btn || !sidebar) return;

  function openSidebar() {
    sidebar.classList.add('open');
    overlay.classList.add('show');
    btn.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    document.body.classList.add('sb-locked');
  }

  function closeSidebar() {
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
    btn.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('sb-locked');
  }

  btn.addEventListener('click', () =>
    sidebar.classList.contains('open') ? closeSidebar() : openSidebar()
  );
  overlay.addEventListener('click', closeSidebar);
  if (closeBtn) closeBtn.addEventListener('click', closeSidebar);

  // Close when a sidebar link is tapped on mobile
  sidebar.querySelectorAll('.sb-link').forEach(a =>
    a.addEventListener('click', () => { if (window.innerWidth < 769) closeSidebar(); })
  );

  // Reset on resize to desktop
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 769) {
      closeSidebar();
    }
  });
})();

// ── Public top-nav hamburger ──────────────────────────────────────────────
(function () {
  const btn   = document.getElementById('navHamburger');
  const links = document.getElementById('navLinks');
  if (!btn || !links) return;

  function openNav()  { links.classList.add('open');  btn.classList.add('is-open');  }
  function closeNav_() { links.classList.remove('open'); btn.classList.remove('is-open'); }

  btn.addEventListener('click', () =>
    links.classList.contains('open') ? closeNav_() : openNav()
  );

  // Close when clicking outside
  document.addEventListener('click', e => {
    if (!btn.contains(e.target) && !links.contains(e.target)) closeNav_();
  });

  // Expose for inline onclick usage
  window.closeNav = closeNav_;
})();

// Highlights the current section's link in the sticky nav while scrolling.
(() => {
  const links = document.querySelectorAll('.site-nav a[href^="#"]');
  const sections = [...links].map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  if (!sections.length) return;

  const setActive = id => {
    links.forEach(a => a.classList.toggle('active', a.getAttribute('href') === `#${id}`));
    const active = document.querySelector('.site-nav a.active');
    if (active) active.scrollIntoView({ inline: 'nearest', block: 'nearest' });
  };

  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(e => e.isIntersecting);
    if (visible.length) setActive(visible[0].target.id);
  }, { rootMargin: '-45% 0px -50% 0px' });

  sections.forEach(section => observer.observe(section));
})();

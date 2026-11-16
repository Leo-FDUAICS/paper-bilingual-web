(() => {
  const rail = document.querySelector('.section-rail');
  if (!rail) return;

  const links = [...rail.querySelectorAll('a[href^="#"]')];
  const headings = links.map(link => document.getElementById(link.hash.slice(1)));
  let pending = false;

  function update() {
    pending = false;
    const readingLine = Math.min(160, window.innerHeight * 0.22);
    let current = 0;
    for (let i = 0; i < headings.length; i++) {
      if (headings[i].getBoundingClientRect().top <= readingLine) current = i;
      else break;
    }
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
      current = links.length - 1;
    }
    links.forEach((link, i) => {
      if (i === current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });

    const active = links[current];
    if (active.offsetTop < rail.scrollTop) rail.scrollTop = active.offsetTop;
    else if (active.offsetTop + active.offsetHeight > rail.scrollTop + rail.clientHeight) {
      rail.scrollTop = active.offsetTop + active.offsetHeight - rail.clientHeight;
    }
  }

  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(update);
  }

  window.addEventListener('scroll', schedule, {passive: true});
  window.addEventListener('resize', schedule);
  window.addEventListener('hashchange', schedule);
  document.addEventListener('load', schedule, true);
  if (document.fonts) document.fonts.ready.then(schedule);
  schedule();
})();

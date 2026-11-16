(() => {
  const blocks = [...document.querySelectorAll('main > .pair[id]')];
  if (!blocks.length) return;
  const rail = document.querySelector('.section-rail');
  const links = rail ? [...rail.querySelectorAll('a[href^="#"]')] : [];
  const headings = links.map(link => document.getElementById(link.hash.slice(1)));
  const positionKey = `paper-bilingual-web:position:${location.pathname}:${document.title}`;
  const initialHash = location.hash;
  const reloading = performance.getEntriesByType('navigation')[0]?.type === 'reload';
  const canResume = () => !location.hash || (reloading && location.hash === initialHash);
  let pending = false;
  let saveTimer;
  let ready = false;
  let interrupted = false;

  function readPosition() {
    try {
      const saved = JSON.parse(localStorage.getItem(positionKey));
      return saved && typeof saved.block === 'string' && Number.isFinite(saved.fraction)
        ? saved : null;
    } catch {
      return null;
    }
  }

  const saved = readPosition();
  if (saved && canResume() && 'scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
  }

  function savePosition() {
    if (!ready) return;
    let current = blocks[0];
    for (const block of blocks) {
      if (block.getBoundingClientRect().top <= 0) current = block;
      else break;
    }
    const rect = current.getBoundingClientRect();
    try {
      localStorage.setItem(positionKey, JSON.stringify({
        block: current.id,
        fraction: rect.height ? -rect.top / rect.height : 0,
        atStart: window.scrollY < 1,
      }));
    } catch {
      // Reading and chapter navigation still work when storage is unavailable.
    }
  }

  function saveSoon() {
    if (!ready) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(savePosition, 250);
  }

  function interruptRestore() {
    interrupted = true;
  }

  function interruptFromKey(event) {
    if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) {
      interruptRestore();
    }
  }

  function restorePosition() {
    const target = saved && blocks.find(block => block.id === saved.block);
    if (target && canResume() && !interrupted) {
      const rect = target.getBoundingClientRect();
      const top = saved.atStart ? 0 : window.scrollY + rect.top + saved.fraction * rect.height;
      const root = document.documentElement;
      const previous = root.style.scrollBehavior;
      root.style.scrollBehavior = 'auto';
      window.scrollTo({top: Math.max(0, top), behavior: 'auto'});
      root.style.scrollBehavior = previous;
    }
    ready = true;
    window.removeEventListener('wheel', interruptRestore);
    window.removeEventListener('pointerdown', interruptRestore);
    window.removeEventListener('keydown', interruptFromKey);
    schedule();
  }

  function update() {
    pending = false;
    if (!links.length) return;
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

  window.addEventListener('scroll', () => {schedule(); saveSoon();}, {passive: true});
  window.addEventListener('resize', () => {schedule(); saveSoon();});
  window.addEventListener('hashchange', schedule);
  window.addEventListener('pagehide', savePosition);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') savePosition();
  });
  window.addEventListener('wheel', interruptRestore, {passive: true});
  window.addEventListener('pointerdown', interruptRestore, {passive: true});
  window.addEventListener('keydown', interruptFromKey);
  document.addEventListener('load', schedule, true);
  const fontsReady = document.fonts ? document.fonts.ready : Promise.resolve();
  fontsReady.then(() => requestAnimationFrame(restorePosition));
  schedule();
})();

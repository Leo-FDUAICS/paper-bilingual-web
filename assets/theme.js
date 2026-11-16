(() => {
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  const storageKey = 'paper-bilingual-web:theme';
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const valid = value => value === 'dark' || value === 'light';
  const query = new URLSearchParams(location.search).get('theme');
  let stored;
  try { stored = localStorage.getItem(storageKey); } catch {}
  let preference = valid(query) ? query : valid(stored) ? stored : null;
  let activeTransition;

  function apply(theme) {
    root.dataset.theme = theme;
    const button = document.querySelector('.theme-toggle');
    if (!button) return;
    button.setAttribute('aria-pressed', String(theme === 'dark'));
    button.title = theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式';
  }

  apply(preference || (system.matches ? 'dark' : 'light'));

  function change(theme) {
    if (reducedMotion.matches) {
      apply(theme);
      return;
    }
    if (typeof document.startViewTransition !== 'function') {
      root.classList.add('theme-color-fade');
      apply(theme);
      return;
    }
    if (activeTransition) activeTransition.skipTransition();
    const transition = document.startViewTransition(() => apply(theme));
    activeTransition = transition;
    transition.ready.catch(() => {});
    transition.finished.catch(() => {}).finally(() => {
      if (activeTransition === transition) activeTransition = null;
    });
  }

  function connectButton() {
    const button = document.querySelector('.theme-toggle');
    button.addEventListener('click', () => {
      preference = (preference || root.dataset.theme) === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(storageKey, preference); } catch {}
      if (new URLSearchParams(location.search).has('theme')) {
        const address = new URL(location.href);
        address.searchParams.delete('theme');
        history.replaceState(history.state, '', address);
      }
      change(preference);
    });
    apply(root.dataset.theme);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connectButton, {once: true});
  } else {
    connectButton();
  }
  system.addEventListener('change', () => {
    if (!preference) change(system.matches ? 'dark' : 'light');
  });
})();

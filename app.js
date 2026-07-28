/* ------------------------------------------------------------------------
 * Products page.
 *
 * To add a project, add an entry to PROJECTS below — the array order is the
 * order on the page. Every field except `name` and `links` is optional.
 *
 *   accent   hex colour for the icon tile, tagline, badge and buttons
 *   status   small pill in the card's top-right corner
 *   featured tints the whole card with the accent colour
 *   links    buttons, in order; the first one is the highlighted button
 *            icon: 'github' | 'chrome' | 'firefox' | 'download' (optional)
 * ---------------------------------------------------------------------- */
const PROJECTS = [
  {
    name: 'FilmTable',
    tagline: 'A TV Time replacement that lives in your browser',
    description:
      'Track the shows and movies you watch, without an account. Your library stays in local storage, backups are plain JSON files you own, and it installs as a PWA on Android and iPhone.',
    category: 'Web app',
    tags: ['PWA', 'Local-first', 'React', 'TypeScript', 'MIT'],
    icon: '🎬',
    accent: '#f2789f',
    status: 'Live',
    featured: true,
    links: [
      { label: 'Open app', url: 'https://film-table.vercel.app' },
      { label: 'GitHub', url: 'https://github.com/mrWD/film-table', icon: 'github' },
    ],
  },
  {
    name: 'GamesTable',
    tagline: 'Games you play — or would rather watch as a longplay',
    description:
      'Seven statuses across play and watch tracks, a searchable library backed by RAWG and Steam data, and recommendations scored on your platforms, genres and Metacritic. No accounts, works offline.',
    category: 'Web app',
    tags: ['PWA', 'Local-first', 'React', 'TypeScript', 'MIT'],
    icon: '🎮',
    accent: '#7c9cff',
    status: 'Live',
    links: [
      { label: 'Open app', url: 'https://games-table-bay.vercel.app' },
      { label: 'GitHub', url: 'https://github.com/mrWD/games-table', icon: 'github' },
    ],
  },
  {
    name: 'AI Screen Translator',
    tagline: 'Hold a key, read your screen in your language',
    description:
      'A menu-bar app for macOS, Windows and Linux. Hold the hotkey to overlay a translation on top of whatever is on screen, release to go back. 25 languages, offline and private by default — built for gamers learning a language.',
    category: 'Desktop app',
    tags: ['macOS', 'Windows', 'Linux', 'Python', 'OCR', 'MIT'],
    icon: '🔤',
    accent: '#67e8c3',
    status: 'Open source',
    links: [
      { label: 'Learn more', url: 'ai-screen-translator/' },
      { label: 'GitHub', url: 'https://github.com/mrWD/ai-screen-translator', icon: 'github' },
    ],
  },
  {
    name: 'AI Prompt Suggester',
    tagline: 'Better prompts, suggested where you already chat',
    description:
      'A lightbulb button inside 10+ AI chats — Claude, ChatGPT, Gemini, Perplexity, Copilot, Le Chat, Grok, DeepSeek, Qwen and LMArena — that rewrites what you typed into a sharper prompt, with examples.',
    category: 'Extension',
    tags: ['Chrome', 'Firefox', 'Open source'],
    icon: '💡',
    accent: '#ffc46b',
    status: 'Live',
    links: [
      {
        label: 'Chrome',
        url: 'https://chromewebstore.google.com/detail/ai-prompt-suggester/ffacabgddhepblahneohlpgmepogoohl',
        icon: 'chrome',
      },
      {
        label: 'Firefox',
        url: 'https://addons.mozilla.org/en-US/firefox/addon/ai-prompt-suggester/',
        icon: 'firefox',
      },
      { label: 'GitHub', url: 'https://github.com/mrWD/ai-prompt-suggester-extension', icon: 'github' },
    ],
  },
  {
    name: 'Double Subtitles',
    tagline: 'Two subtitle tracks at once, for language learners',
    description:
      'Shows your native and target language subtitles side by side on Netflix, Prime Video and Disney+. Styling and position are adjustable, and words you save go straight to Anki or Quizlet. No data collected.',
    category: 'Extension',
    tags: ['Chrome', 'Netflix', 'Prime Video', 'Disney+', 'Anki'],
    icon: '📺',
    accent: '#a78bfa',
    status: 'Live',
    links: [
      {
        label: 'Chrome',
        url: 'https://chromewebstore.google.com/detail/cpnlpffdpcpoabpahdgfnecgngapjibn',
        icon: 'chrome',
      },
      { label: 'GitHub', url: 'https://github.com/mrWD/double-subtitles', icon: 'github' },
    ],
  },
];

const ICONS = {
  arrow: '<path d="M5 12h13M13 6l6 6-6 6"/>',
  github:
    '<path class="solid" d="M12 1.7a10.3 10.3 0 0 0-3.26 20.07c.52.1.7-.22.7-.5v-1.9c-2.86.62-3.47-1.2-3.47-1.2-.47-1.2-1.15-1.52-1.15-1.52-.94-.64.07-.63.07-.63 1.04.07 1.58 1.07 1.58 1.07.92 1.58 2.42 1.13 3.01.86.1-.67.36-1.13.65-1.39-2.28-.26-4.68-1.14-4.68-5.08 0-1.12.4-2.04 1.06-2.76-.11-.26-.46-1.3.1-2.72 0 0 .86-.28 2.83 1.05a9.8 9.8 0 0 1 5.16 0c1.97-1.33 2.83-1.05 2.83-1.05.56 1.42.21 2.46.1 2.72.66.72 1.06 1.64 1.06 2.76 0 3.95-2.4 4.82-4.7 5.07.37.32.7.94.7 1.9v2.82c0 .28.18.6.71.5A10.3 10.3 0 0 0 12 1.7Z"/>',
  chrome:
    '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.4"/><path d="M21 8.2H12M8.6 13.7 4.1 6M15.4 13.7l-4.5 7.8"/>',
  firefox: '<circle cx="12" cy="12" r="9"/><path d="M12 3c3 2 4.5 4.4 4.5 7.2 0 2.6-2 4.5-4.5 4.5S7.5 12.8 7.5 10"/>',
  download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M4.5 19.5h15"/>',
};

const $ = (sel) => document.querySelector(sel);

/** Deterministic accent for a project that doesn't name one. */
function accentFor(project) {
  if (project.accent) return project.accent;

  let hash = 0;
  for (const ch of project.name) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${hash} 72% 68%)`;
}

/* -------------------------------------------------------------- rendering */

const state = { category: 'All', query: '' };

function icon(name) {
  return `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

function buildCard(project) {
  const node = $('#card-template').content.firstElementChild.cloneNode(true);
  node.style.setProperty('--card-accent', accentFor(project));
  if (project.featured) node.classList.add('featured');

  node.querySelector('.card-icon').textContent = project.icon || '◆';
  node.querySelector('.card-title').textContent = project.name;

  const badge = node.querySelector('.badge');
  if (project.status) {
    badge.textContent = project.status;
    badge.hidden = false;
  }

  const tagline = node.querySelector('.card-tagline');
  tagline.textContent = project.tagline || '';
  tagline.hidden = !project.tagline;

  const desc = node.querySelector('.card-desc');
  desc.textContent = project.description || '';
  desc.hidden = !project.description;

  const tags = node.querySelector('.tags');
  for (const tag of project.tags || []) {
    const li = document.createElement('li');
    li.textContent = tag;
    tags.append(li);
  }

  const links = node.querySelector('.card-links');
  (project.links || []).forEach((link, index) => {
    const primary = index === 0; // links are listed in priority order
    const a = document.createElement('a');
    a.className = `btn${primary ? ' primary' : ''}`;
    a.href = link.url;
    if (/^https?:/.test(link.url)) {
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
    }
    a.innerHTML = `${link.icon ? icon(link.icon) : ''}<span></span>${primary ? icon('arrow') : ''}`;
    a.querySelector('span').textContent = link.label;
    a.setAttribute('aria-label', `${link.label} — ${project.name}`);
    links.append(a);
  });

  return node;
}

function matchesFilter(project) {
  if (state.category !== 'All' && (project.category || 'Other') !== state.category) return false;
  if (!state.query) return true;

  const haystack = [project.name, project.tagline, project.description, project.category, ...(project.tags || [])]
    .join(' ')
    .toLowerCase();
  return state.query.split(/\s+/).every((word) => haystack.includes(word));
}

function renderFilters() {
  const categories = ['All', ...new Set(PROJECTS.map((p) => p.category || 'Other'))];
  const box = $('#filters');
  box.replaceChildren();

  for (const cat of categories) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.textContent = cat;
    btn.setAttribute('aria-pressed', String(cat === state.category));
    btn.addEventListener('click', () => {
      state.category = cat;
      renderFilters();
      renderGrid();
    });
    box.append(btn);
  }
}

function renderGrid() {
  const grid = $('#grid');
  const visible = PROJECTS.filter(matchesFilter);

  grid.replaceChildren(...visible.map(buildCard));
  $('#empty').hidden = visible.length > 0;
}

/* ---------------------------------------------------------------- startup */

function initTheme() {
  const saved = localStorage.getItem('products-page:theme');
  const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
  document.documentElement.dataset.theme = saved || (prefersLight ? 'light' : 'dark');

  $('#theme-toggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('products-page:theme', next);
  });
}

function initSearch() {
  const input = $('#search');
  let timer;

  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      state.query = input.value.trim().toLowerCase();
      renderGrid();
    }, 120);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== input) {
      e.preventDefault();
      input.focus();
    }
    if (e.key === 'Escape' && document.activeElement === input) {
      input.value = '';
      state.query = '';
      renderGrid();
      input.blur();
    }
  });
}

initTheme();
initSearch();
renderFilters();
renderGrid();
$('#status').textContent = `${PROJECTS.length} project${PROJECTS.length === 1 ? '' : 's'}`;

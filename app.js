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
    name: 'Science Timeline',
    tagline: 'The history of science on one line you can zoom to a single day',
    description:
      'Discoveries, inventions and Nobel prizes from the seventh millennium BC to this week, on a timeline that zooms continuously from millennia down to days. Vague dates stay vague — "around 300 BC" is a century-wide interval, not an invented 1 January. Wikidata supplies the history, Crossref the current week from twenty leading journals.',
    category: 'Web app',
    tags: ['Open data', 'Canvas', 'TypeScript', 'Wikidata', 'Crossref'],
    icon: '🔭',
    accent: '#4c8dff',
    status: 'Live',
    featured: true,
    links: [
      { label: 'Learn more', url: 'products/science-timeline/' },
      { label: 'Open the timeline', url: 'https://mrwd.github.io/science-timeline/' },
      { label: 'GitHub', url: 'https://github.com/mrWD/science-timeline', icon: 'github' },
    ],
  },
  {
    name: 'Lingary',
    tagline: 'An AI language tutor you talk to, out loud',
    description:
      'Live voice or text conversations with a tutor that works out your CEFR level by talking to you, then builds practice out of the mistakes you actually made — missions, a spaced-repetition deck and five drill modes, in 61 languages. Bring your own OpenAI or Gemini key and pay the provider directly, or download the models and run the whole loop on the phone with no key and no connection.',
    category: 'iOS app',
    tags: ['SwiftUI', 'SwiftData', 'BYOK', 'On-device AI', 'Offline'],
    icon: '🗣️',
    accent: '#ff8f6b',
    status: 'Beta',
    links: [
      { label: 'Learn more', url: 'products/lingary/' },
    ],
  },
  {
    name: 'Languages of the World',
    tagline: '7,992 languages and 13,706 dialects, on one map',
    description:
      'An interactive atlas built on Glottolog, Wikidata, WALS and ASJP: families, speaker counts, endangerment status, and four separate measures of how any two languages relate — family tree, grammar, vocabulary and distance. Search works across 84,000 alternative names in 15 interface languages.',
    category: 'Web app',
    tags: ['Open data', 'Leaflet', 'Vanilla JS', 'Glottolog', 'WALS'],
    icon: '🌍',
    accent: '#5ec8d8',
    status: 'Live',
    featured: true,
    links: [
      { label: 'Learn more', url: 'products/langs-db/' },
      { label: 'Open the atlas', url: 'https://mrwd.github.io/langs-db/' },
      { label: 'GitHub', url: 'https://github.com/mrWD/langs-db', icon: 'github' },
    ],
  },
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
    links: [
      { label: 'Learn more', url: 'products/film-table/' },
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
      { label: 'Learn more', url: 'products/games-table/' },
      { label: 'Open app', url: 'https://games-table-bay.vercel.app' },
      { label: 'GitHub', url: 'https://github.com/mrWD/games-table', icon: 'github' },
    ],
  },
  {
    name: 'AI Job Search',
    tagline: 'A job hunt that runs while you do something else',
    description:
      'Reads your CV, walks company career pages, ATS platforms and job boards, and scores every posting against you with a reason — then says what to change in the CV for that particular role and generates a tailored one. Runs on your own computer; the thinking is done by Claude Code, Cursor, or a local model through Ollama, so with a local model nothing leaves the machine.',
    category: 'Desktop app',
    tags: ['macOS', 'Windows', 'Linux', 'Python', 'Local-first', 'MIT'],
    icon: '🎯',
    accent: '#6aa9ff',
    status: 'Open source',
    links: [
      { label: 'Learn more', url: 'products/ai-job-search/' },
      { label: 'Download', url: 'https://github.com/mrWD/ai-job-search/releases/latest' },
      { label: 'GitHub', url: 'https://github.com/mrWD/ai-job-search', icon: 'github' },
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
      { label: 'Learn more', url: 'products/ai-screen-translator/' },
      { label: 'GitHub', url: 'https://github.com/mrWD/ai-screen-translator', icon: 'github' },
    ],
  },
  {
    name: 'AI Prompt Suggester',
    statsKey: 'ai-prompt-suggester', // matches a key in stats.json
    tagline: 'Better prompts, suggested where you already chat',
    description:
      'A lightbulb button inside 10+ AI chats — Claude, ChatGPT, Gemini, Perplexity, Copilot, Le Chat, Grok, DeepSeek, Qwen and LMArena — that rewrites what you typed into a sharper prompt, with examples.',
    category: 'Extension',
    tags: ['Chrome', 'Firefox', 'Open source'],
    icon: '💡',
    accent: '#ffc46b',
    status: 'Live',
    links: [
      { label: 'Learn more', url: 'products/ai-prompt-suggester/' },
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
    statsKey: 'double-subtitles', // matches a key in stats.json
    tagline: 'Two subtitle tracks at once, for language learners',
    description:
      'Shows your native and target language subtitles side by side on Netflix, Prime Video and Disney+. Styling and position are adjustable, and words you save go straight to Anki or Quizlet. No data collected.',
    category: 'Extension',
    tags: ['Chrome', 'Netflix', 'Prime Video', 'Disney+', 'Anki'],
    icon: '📺',
    accent: '#a78bfa',
    status: 'Live',
    links: [
      { label: 'Learn more', url: 'products/double-subtitles/' },
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

/* ------------------------------------------------------------------ stats */

/* stats.json is refreshed once a day by .github/workflows/stats.yml. A count
 * only earns a place on the card once it's big enough to mean something —
 * "9 users" says less than saying nothing. */
const USERS_THRESHOLD = 1000;

let STATS = {};

function formatUsers(n) {
  // One decimal below 10, none above: 1.2k, 10k, 1.5M. 9999 lands on 10k.
  const scale = (value, suffix) =>
    `${value >= 10 ? Math.round(value) : Math.round(value * 10) / 10}${suffix}`;
  return n >= 1_000_000 ? scale(n / 1_000_000, 'M') : scale(n / 1000, 'k');
}

/** The store number for a project, or null if it's absent or too small. */
function usersFor(project) {
  const count = project.statsKey && STATS[project.statsKey]?.users;
  return typeof count === 'number' && count >= USERS_THRESHOLD ? count : null;
}

async function loadStats() {
  try {
    const res = await fetch('stats.json', { cache: 'no-cache' });
    if (!res.ok) return;
    STATS = (await res.json()).products || {};
    if (Object.keys(STATS).length) renderGrid(); // repaint with the badges
  } catch {
    /* No stats, no badges. The page is complete without them. */
  }
}

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

  const users = usersFor(project);
  if (users) {
    const pill = document.createElement('span');
    pill.className = 'badge users';
    pill.textContent = `${formatUsers(users)} users`;
    pill.title = `${users.toLocaleString('en-US')} active users across the stores`;
    badge.after(pill);
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
loadStats(); // fills in the user badges once the numbers arrive

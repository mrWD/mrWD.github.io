/* ------------------------------------------------------------------------
 * Products page — data comes from a published Google Sheet.
 *
 * 1. Create a sheet, first row = column headers (see README for the list).
 * 2. Share → "Anyone with the link" → Viewer.
 * 3. Paste the spreadsheet id below (the long chunk between /d/ and /edit).
 *
 * Nothing else to do: adding a row in the sheet adds a card here.
 * ---------------------------------------------------------------------- */
const CONFIG = {
  sheetId: '',          // e.g. '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
  sheetName: 'Projects', // tab name inside the spreadsheet
  cacheMinutes: 10,      // serve the cached copy first, refresh in background
};

/* Fallback data — used until the sheet id is filled in, and as a safety net
 * if Google is unreachable. Keep it roughly in sync with the sheet. */
const FALLBACK = [
  {
    name: 'FilmTable',
    tagline: 'A TV Time replacement that lives in your browser',
    description:
      'Track the shows and movies you watch, without an account. Your library stays in local storage, backups are plain JSON files you own, and it installs as a PWA on Android and iPhone.',
    category: 'Web app',
    tags: 'PWA, Local-first, React, TypeScript, MIT',
    icon: '🎬',
    accent: '#f2789f',
    status: 'Live',
    featured: 'TRUE',
    order: '1',
    live: 'https://film-table.vercel.app',
    github: 'https://github.com/mrWD/film-table',
  },
  {
    name: 'GamesTable',
    tagline: 'Games you play — or would rather watch as a longplay',
    description:
      'Seven statuses across play and watch tracks, a searchable library backed by RAWG and Steam data, and recommendations scored on your platforms, genres and Metacritic. No accounts, works offline.',
    category: 'Web app',
    tags: 'PWA, Local-first, React, TypeScript, MIT',
    icon: '🎮',
    accent: '#7c9cff',
    status: 'Live',
    order: '2',
    live: 'https://games-table-bay.vercel.app',
    github: 'https://github.com/mrWD/games-table',
  },
  {
    name: 'AI Screen Translator',
    tagline: 'Hold a key, read your screen in your language',
    description:
      'A menu-bar app for macOS, Windows and Linux. Hold the hotkey to overlay a translation on top of whatever is on screen, release to go back. 25 languages, offline and private by default — built for gamers learning a language.',
    category: 'Desktop app',
    tags: 'macOS, Windows, Linux, Python, OCR, MIT',
    icon: '🔤',
    accent: '#67e8c3',
    status: 'Open source',
    order: '3',
    github: 'https://github.com/mrWD/ai-screen-translator',
  },
  {
    name: 'AI Prompt Suggester',
    tagline: 'Better prompts, suggested where you already chat',
    description:
      'A lightbulb button inside 10+ AI chats — Claude, ChatGPT, Gemini, Perplexity, Copilot, Le Chat, Grok, DeepSeek, Qwen and LMArena — that rewrites what you typed into a sharper prompt, with examples.',
    category: 'Extension',
    tags: 'Chrome, Firefox, Open source',
    icon: '💡',
    accent: '#ffc46b',
    status: 'Live',
    order: '4',
    chrome: 'https://chromewebstore.google.com/detail/ai-prompt-suggester/ffacabgddhepblahneohlpgmepogoohl',
    firefox: 'https://addons.mozilla.org/en-US/firefox/addon/ai-prompt-suggester/',
    github: 'https://github.com/mrWD/ai-prompt-suggester-extension',
  },
  {
    name: 'Double Subtitles',
    tagline: 'Two subtitle tracks at once, for language learners',
    description:
      'Shows your native and target language subtitles side by side on Netflix, Prime Video and Disney+. Styling and position are adjustable, and words you save go straight to Anki or Quizlet. No data collected.',
    category: 'Extension',
    tags: 'Chrome, Netflix, Prime Video, Disney+, Anki',
    icon: '📺',
    accent: '#a78bfa',
    status: 'Live',
    order: '5',
    chrome: 'https://chromewebstore.google.com/detail/cpnlpffdpcpoabpahdgfnecgngapjibn',
    github: 'https://github.com/mrWD/double-subtitles',
  },
];

/* Known link columns, in the order the buttons should appear. */
const LINK_FIELDS = [
  { key: 'live', label: 'Open app', primary: true },
  { key: 'chrome', label: 'Chrome', icon: 'chrome' },
  { key: 'firefox', label: 'Firefox', icon: 'firefox' },
  { key: 'appstore', label: 'App Store' },
  { key: 'download', label: 'Download', icon: 'download' },
  { key: 'github', label: 'GitHub', icon: 'github' },
  { key: 'article', label: 'Read more' },
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

/* ------------------------------------------------------------------ utils */

const $ = (sel) => document.querySelector(sel);

/** RFC-4180-ish CSV parser: handles quotes, escaped quotes and newlines. */
function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];

    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else quoted = false;
      } else field += c;
      continue;
    }

    if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (c !== '\r') field += c;
  }

  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows;
}

/** "Link — Live" → "link_live", so headers can be written however reads best. */
const normalizeKey = (h) =>
  h.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');

function csvToObjects(text) {
  const rows = parseCSV(text).filter((r) => r.some((c) => c.trim() !== ''));
  if (rows.length < 2) return [];

  const headers = rows[0].map(normalizeKey);
  return rows.slice(1).map((cells) => {
    const obj = {};
    headers.forEach((h, i) => {
      if (h) obj[h] = (cells[i] ?? '').trim();
    });
    return obj;
  });
}

const isTrue = (v) => ['true', 'yes', '1', 'y', 'x', '✓', 'да'].includes(String(v || '').trim().toLowerCase());

const splitList = (v) => String(v || '').split(',').map((s) => s.trim()).filter(Boolean);

/** Only allow links we are willing to render as an anchor. */
function safeUrl(raw) {
  const value = String(raw || '').trim();
  if (!value) return '';
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : '';
  } catch {
    return '';
  }
}

/** Deterministic accent when the sheet leaves the column empty. */
function accentFor(project) {
  const explicit = String(project.accent || '').trim();
  if (/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(explicit)) return explicit;

  let hash = 0;
  for (const ch of project.name || '') hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${hash} 72% 68%)`;
}

/** Extra links column: "Docs|https://…; Demo|https://…" */
function extraLinks(project) {
  return String(project.links || '')
    .split(';')
    .map((chunk) => {
      const [label, url] = chunk.split('|');
      return { label: (label || '').trim(), url: safeUrl(url) };
    })
    .filter((l) => l.label && l.url);
}

function normalizeProjects(rows) {
  return rows
    .filter((p) => p.name && !isTrue(p.hidden))
    .sort((a, b) => {
      const oa = Number(a.order) || 999;
      const ob = Number(b.order) || 999;
      return oa - ob || String(a.name).localeCompare(String(b.name));
    });
}

/* ------------------------------------------------------------------- data */

const CACHE_KEY = 'products-page:cache:v1';

function sheetUrl() {
  const override = new URLSearchParams(location.search).get('sheet');
  const id = (override || CONFIG.sheetId).trim();
  if (!id) return '';
  return `https://docs.google.com/spreadsheets/d/${encodeURIComponent(id)}/gviz/tq` +
         `?tqx=out:csv&sheet=${encodeURIComponent(CONFIG.sheetName)}`;
}

function readCache() {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
    if (!cached || !Array.isArray(cached.projects) || !cached.projects.length) return null;
    return cached;
  } catch {
    return null;
  }
}

function writeCache(projects) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ projects, at: Date.now() }));
  } catch { /* private mode / quota — caching is optional */ }
}

async function fetchSheet() {
  const url = sheetUrl();
  if (!url) throw new Error('no-sheet-id');

  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const projects = normalizeProjects(csvToObjects(await res.text()));
  if (!projects.length) throw new Error('empty-sheet');
  return projects;
}

/* -------------------------------------------------------------- rendering */

const state = { projects: [], category: 'All', query: '' };

function icon(name, cls = '') {
  return `<svg class="${cls}" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

function buildCard(project) {
  const node = $('#card-template').content.firstElementChild.cloneNode(true);
  node.style.setProperty('--card-accent', accentFor(project));
  if (isTrue(project.featured)) node.classList.add('featured');

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
  for (const tag of splitList(project.tags)) {
    const li = document.createElement('li');
    li.textContent = tag;
    tags.append(li);
  }

  const links = node.querySelector('.card-links');
  const buttons = [
    ...LINK_FIELDS
      .map((f) => ({ ...f, url: safeUrl(project[f.key]) }))
      .filter((f) => f.url),
    ...extraLinks(project),
  ];

  buttons.forEach((link, index) => {
    const a = document.createElement('a');
    a.className = `btn${link.primary || index === 0 ? ' primary' : ''}`;
    a.href = link.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.innerHTML = `${link.icon ? icon(link.icon) : ''}<span></span>${
      link.primary || index === 0 ? icon('arrow') : ''
    }`;
    a.querySelector('span').textContent = link.label;
    a.setAttribute('aria-label', `${link.label} — ${project.name}`);
    links.append(a);
  });

  return node;
}

function matchesFilter(project) {
  if (state.category !== 'All' && (project.category || 'Other') !== state.category) return false;
  if (!state.query) return true;

  const haystack = [project.name, project.tagline, project.description, project.category, project.tags]
    .join(' ')
    .toLowerCase();
  return state.query.split(/\s+/).every((word) => haystack.includes(word));
}

function renderFilters() {
  const categories = ['All', ...new Set(state.projects.map((p) => p.category || 'Other'))];
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
  const visible = state.projects.filter(matchesFilter);

  grid.replaceChildren(...visible.map(buildCard));
  grid.setAttribute('aria-busy', 'false');
  $('#empty').hidden = visible.length > 0;
}

function setStatus(message, isNotice = false) {
  const el = $('#status');
  el.textContent = message;
  el.style.color = isNotice ? 'var(--accent)' : '';
}

function render(projects, note) {
  state.projects = projects;
  renderFilters();
  renderGrid();
  setStatus(note || `${projects.length} project${projects.length === 1 ? '' : 's'}`);
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

async function load() {
  const cached = readCache();
  if (cached) render(cached.projects); // paint instantly, then revalidate

  const fresh = Date.now() - (cached?.at || 0) < CONFIG.cacheMinutes * 60_000;
  if (cached && fresh) return;

  try {
    const projects = await fetchSheet();
    writeCache(projects);
    render(projects);
  } catch (err) {
    if (cached) return; // stale cache still beats nothing

    const reason = err.message === 'no-sheet-id'
      ? 'Showing the built-in list — add your Google Sheet id in app.js to manage projects from the sheet.'
      : 'Could not reach the Google Sheet, showing the built-in list.';
    render(normalizeProjects(FALLBACK), reason);
    $('#footer-note').textContent = `Data source: fallback (${err.message}).`;
  }
}

initTheme();
initSearch();
load();

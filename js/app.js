/* ============================================================
   دیازفلیکس — منطق اصلی (SPA با hash routing، بدون بک‌اند)
   ============================================================ */
'use strict';

// ===== وضعیت برنامه =====
const state = {
  movies: [],
  query: '',
  route: { name: 'home', params: {} },
};

// ===== کلیدهای localStorage =====
const LS_PROGRESS = 'diazflix_progress';   // { [id]: درصد 0..100 }
const LS_RATINGS  = 'diazflix_ratings';    // { [id]: 1..5 }

// ===== ابزارها =====
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function loadJSON(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) || fallback; }
  catch { return fallback; }
}
function saveJSON(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// مسیر relative — برای کار زیر subpath گیت‌هاب پیجز
function rel(path) {
  return path; // همه مسیرها در HTML/JSON از قبل relative هستند
}

// ===== بارگذاری کاتالوگ =====
async function loadMovies() {
  const res = await fetch(rel('data/movies.json'), { cache: 'no-cache' });
  if (!res.ok) throw new Error('کاتالوگ فیلم‌ها یافت نشد');
  state.movies = await res.json();
}

// ===== روتینگ hash =====
function parseHash() {
  const hash = location.hash.replace(/^#\/?/, ''); // مثل: movie/sardar-1
  const parts = hash.split('/').filter(Boolean);
  if (parts.length === 0) return { name: 'home', params: {} };
  if (parts[0] === 'movie' && parts[1]) return { name: 'movie', params: { id: parts[1] } };
  if (parts[0] === 'about') return { name: 'about', params: {} };
  if (parts[0] === 'search') return { name: 'search', params: { q: decodeURIComponent(parts[1] || '') } };
  return { name: 'home', params: {} };
}

function navigate() {
  state.route = parseHash();
  render();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

// ===== فیلترها =====
function filterMovies(list, q) {
  if (!q) return list;
  const needle = q.trim().toLowerCase();
  return list.filter(m =>
    m.title.toLowerCase().includes(needle) ||
    m.genres.some(g => g.toLowerCase().includes(needle)) ||
    String(m.year).includes(needle)
  );
}

function allGenres(list) {
  const set = new Set();
  list.forEach(m => m.genres.forEach(g => set.add(g)));
  return [...set];
}

// ===== ساخت کارت پوستر =====
function posterCard(movie, opts = {}) {
  const progress = loadJSON(LS_PROGRESS, {})[movie.id] || 0;
  const showProgress = opts.showProgress && progress > 0;
  const showRemove = opts.showRemove;
  const delay = opts.delay || 0;

  return `
    <div class="poster-card" data-id="${escapeHTML(movie.id)}"
         style="animation-delay:${delay}ms" role="button" tabindex="0"
         aria-label="${escapeHTML(movie.title)}">
      ${showRemove ? `<button class="remove-btn" data-remove="${escapeHTML(movie.id)}"
                        title="حذف از ادامه تماشا" aria-label="حذف">✕</button>` : ''}
      <img class="poster-img" src="${escapeHTML(movie.poster)}"
           alt="پوستر ${escapeHTML(movie.title)}" loading="lazy">
      <div class="poster-play">▶</div>
      <div class="poster-overlay">
        <div class="poster-title">${escapeHTML(movie.title)}</div>
        <div class="poster-sub">
          <span class="rating-badge">★ ${movie.rating}</span>
          <span>${movie.year}</span>
        </div>
      </div>
      ${showProgress ? `<div class="progress-bar"><span style="width:${progress}%"></span></div>` : ''}
    </div>`;
}

// ===== ردیف افقی =====
function rowSection(title, movies, opts = {}) {
  if (!movies.length) return '';
  const cards = movies.map((m, i) =>
    posterCard(m, { ...opts, delay: i * 60 })
  ).join('');
  const id = 'row-' + Math.random().toString(36).slice(2, 8);
  return `
    <section class="row-section">
      <div class="row-header">
        <h2 class="row-title">${title}</h2>
      </div>
      <div class="row-scroller" data-scroller="${id}">
        <button class="row-nav prev" data-dir="prev" data-target="${id}" aria-label="قبلی">‹</button>
        <div class="row-track" id="${id}">${cards}</div>
        <button class="row-nav next" data-dir="next" data-target="${id}" aria-label="بعدی">›</button>
      </div>
    </section>`;
}

// ===== صفحه اصلی =====
function renderHome() {
  const movies = state.movies;
  if (!movies.length) {
    return `<div class="empty-state"><div class="big">🎬</div>
      <p>هنوز فیلمی اضافه نشده است.</p></div>`;
  }

  // hero = جدیدترین فیلم
  const featured = [...movies].sort((a, b) => (b.added_at || '').localeCompare(a.added_at || ''))[0];

  // ادامه تماشا
  const progress = loadJSON(LS_PROGRESS, {});
  const continueList = movies.filter(m => (progress[m.id] || 0) > 0 && (progress[m.id] || 0) < 98);

  // تازه‌ها
  const fresh = [...movies].sort((a, b) => (b.added_at || '').localeCompare(a.added_at || '')).slice(0, 10);

  // ردیف هر ژانر
  const genres = allGenres(movies).map(g => ({
    name: g,
    items: movies.filter(m => m.genres.includes(g)),
  }));

  const heroHTML = `
    <section class="hero">
      <div class="hero-backdrop" style="background-image:url('${escapeHTML(featured.poster)}')"></div>
      <div class="hero-content">
        <h1 class="hero-title">${escapeHTML(featured.title)}</h1>
        <div class="hero-meta">
          <span class="rating-badge">★ ${featured.rating}</span>
          <span>${featured.year}</span>
          <span>${featured.duration}</span>
          ${featured.genres.map(g => `<span class="genre-tag">${escapeHTML(g)}</span>`).join('')}
        </div>
        <p class="hero-desc">${escapeHTML(featured.description)}</p>
        <a class="btn btn-red" href="#/movie/${encodeURIComponent(featured.id)}">▶ پخش الآن</a>
        <a class="btn btn-ghost" href="#/about">درباره دیازفلیکس</a>
      </div>
    </section>`;

  const continueHTML = continueList.length ? rowSection(
    'ادامه تماشا', continueList, { showProgress: true, showRemove: true }
  ) : '';

  const freshHTML = rowSection('تازه‌ها', fresh, {});
  const genreHTML = genres.map(g => rowSection(g.name, g.items, {})).join('');

  return heroHTML + continueHTML + freshHTML + genreHTML;
}

// ===== صفحه جستجو =====
function renderSearch(q) {
  const results = filterMovies(state.movies, q);
  const head = `<div class="row-header"><h2 class="row-title">
    نتایج جستجو برای «<span class="accent">${escapeHTML(q)}</span>»</h2></div>`;
  if (!results.length) {
    return head + `<div class="empty-state"><div class="big">🔍</div>
      <p>چیزی پیدا نشد. یه فیلم دیگه امتحان کن.</p></div>`;
  }
  const cards = results.map((m, i) => posterCard(m, { delay: i * 50 })).join('');
  return head + `<div class="row-track" style="flex-wrap:wrap">${cards}</div>`;
}

// ===== صفحه فیلم =====
function renderMovie(id) {
  const movie = state.movies.find(m => m.id === id);
  if (!movie) {
    return `<div class="empty-state"><div class="big">🎬</div>
      <p>فیلم مورد نظر پیدا نشد.</p>
      <a class="btn btn-red" href="#/" style="margin-top:1rem">بازگشت به خانه</a></div>`;
  }

  const ratings = loadJSON(LS_RATINGS, {});
  const myRating = ratings[movie.id] || 0;
  const starsHTML = [1,2,3,4,5].map(n =>
    `<span class="star ${n <= myRating ? 'active' : ''}" data-star="${n}"
           data-movie="${escapeHTML(movie.id)}" role="button" tabindex="0"
           aria-label="${n} ستاره">★</span>`
  ).join('');

  return `
    <div class="movie-page">
      <div class="movie-backdrop" style="background-image:url('${escapeHTML(movie.poster)}')"></div>
      <div class="movie-hero">
        <img class="movie-poster-big" src="${escapeHTML(movie.poster)}"
             alt="پوستر ${escapeHTML(movie.title)}">
        <div class="movie-info">
          <h1>${escapeHTML(movie.title)}</h1>
          <div class="movie-meta">
            <span class="rating-badge">★ ${movie.rating}</span>
            <span>${movie.year}</span>
            <span>⏱ ${movie.duration}</span>
            ${movie.genres.map(g => `<span class="genre-tag">${escapeHTML(g)}</span>`).join('')}
          </div>
          <p class="movie-desc">${escapeHTML(movie.description)}</p>

          <div class="user-rating">
            <span class="label">امتیاز تو:</span>
            <div class="stars" id="userStars">${starsHTML}</div>
          </div>

          <button class="btn btn-red" id="playBtn">▶ پخش الآن</button>
          <a class="btn btn-ghost" href="#/">بازگشت</a>
        </div>
      </div>

      <div class="player-wrap" id="playerWrap" style="display:none">
        <iframe id="playerFrame" allowfullscreen
                allow="autoplay; fullscreen; encrypted-media"
                sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"></iframe>
        <div class="embed-fallback" id="embedFallback">
          <div style="font-size:3rem">📡</div>
          <p>پخش‌کننده تلگرام اینجا لود نشد.</p>
          <p style="color:var(--text-faint);font-size:.85rem">
            ممکن است پست حذف شده باشد یا کانال خصوصی باشد.</p>
          <a class="btn btn-gold" id="tgLink" href="#" target="_blank" rel="noopener">
            مشاهده در تلگرام ↗</a>
        </div>
      </div>
    </div>`;
}

// ===== صفحه about =====
function renderAbout() {
  return `
    <div class="row-header"><h2 class="row-title">درباره <span class="accent">دیازفلیکس</span></h2></div>

    <div class="about-card">
      <h2>🎬 دیازفلیکس چیه؟</h2>
      <p>دیازفلیکس یک سینمای آنلاین فارسی است که کاملاً <b>بدون سرور</b> کار می‌کند.
      کاتالوگ فیلم‌ها یک فایل ساده <code>data/movies.json</code> داخل ریپو است و
      پخش ویدیو مستقیم از <b>تلگرام</b> انجام می‌شود. یعنی نه هزینه‌ی هاست داری، نه بک‌اند.</p>
    </div>

    <div class="about-card">
      <h2>➕ چطور فیلم اضافه کنم؟ (راهنمای مدیر)</h2>
      <ol>
        <li>فیلم را در کانال تلگرام خودت آپلود کن.</li>
        <li>روی پیام آپلودشده کلیک کن و از منوی «Copy Link» لینک پست را بگیر
            (به شکل <code>https://t.me/your_channel/123</code>).</li>
        <li>پوستر فیلم را در پوشه <code>assets/posters/</code> بگذار (نرخ تصویر ۲:۳).</li>
        <li>فایل <code>data/movies.json</code> را باز کن و یک شیء جدید به آرایه اضافه کن:</li>
      </ol>
      <pre style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:1rem;overflow-x:auto;direction:ltr;text-align:left;color:#cbd5e1;font-size:.82rem">{
  "id": "my-movie-1",
  "title": "نام فیلم",
  "year": 1403,
  "genres": ["کمدی"],
  "rating": 8.0,
  "duration": "1:45",
  "description": "توضیح دو-سه خطی",
  "poster": "assets/posters/my-movie-1.jpg",
  "telegram_embed": "https://t.me/your_channel/123",
  "added_at": "2026-10-29"
}</pre>
      <ol start="5">
        <li>فایل را کامیت و پوش کن. تمام! فیلم روی سایت ظاهر می‌شود.</li>
      </ol>
    </div>

    <div class="about-card">
      <h2>⚠️ نکته‌ی مهم</h2>
      <p>این ریپو را <b>پیشنهاد می‌شود private نگه داری</b>، چون محتوای فیلم‌ها ممکن است
      حق پخش داشته باشد. GitHub Pages برای ریپوی private هم (در پلن‌های خاص) کار می‌کند،
      ولی اگر عمومی شد، مسئولیت محتوا با توست.</p>
    </div>

    <div class="about-card">
      <h2>🛠 ویژگی‌ها</h2>
      <ul>
        <li>جستجوی زنده در عنوان، ژانر و سال</li>
        <li>ردیف‌های جداگانه برای هر ژانر + بخش تازه‌ها</li>
        <li>ادامه‌ی تماشا با ذخیره‌ی پیشرفت در مرورگر (localStorage)</li>
        <li>امتیازدهی ستاره‌ای شخصی (در مرورگر ذخیره می‌شود)</li>
        <li>پخش داخلی با embed تلگرام + fallback دوستانه</li>
      </ul>
    </div>`;
}

// ===== رندر کلی =====
function render() {
  const app = $('#app');
  const r = state.route;

  let html = '';
  if (r.name === 'movie') html = renderMovie(r.params.id);
  else if (r.name === 'about') html = renderAbout();
  else if (r.name === 'search') html = renderSearch(r.params.q);
  else html = renderHome();

  app.innerHTML = html;

  // به‌روزرسانی لینک فعال ناوبری
  $$('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    a.classList.toggle('active',
      (href === '#/' && r.name === 'home') ||
      (href === '#/about' && r.name === 'about'));
  });

  bindDynamicEvents();
}

// ===== رویدادهای داینامیک =====
function bindDynamicEvents() {
  // کلیک روی کارت پوستر
  $$('.poster-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('[data-remove]')) return; // دکمه حذف جدا
      location.hash = '#/movie/' + encodeURIComponent(card.dataset.id);
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        location.hash = '#/movie/' + encodeURIComponent(card.dataset.id);
      }
    });
  });

  // دکمه حذف از ادامه تماشا
  $$('[data-remove]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = btn.dataset.remove;
      const progress = loadJSON(LS_PROGRESS, {});
      delete progress[id];
      saveJSON(LS_PROGRESS, progress);
      render();
    });
  });

  // ناوبری ردیف‌ها
  $$('.row-nav').forEach(btn => {
    btn.addEventListener('click', () => {
      const track = document.getElementById(btn.dataset.target);
      if (!track) return;
      const amount = track.clientWidth * 0.8;
      track.scrollBy({ left: btn.dataset.dir === 'next' ? -amount : amount, behavior: 'smooth' });
    });
  });

  // ستاره‌های امتیاز
  $$('.star').forEach(star => {
    star.addEventListener('click', () => {
      const movieId = star.dataset.movie;
      const val = parseInt(star.dataset.star);
      const ratings = loadJSON(LS_RATINGS, {});
      ratings[movieId] = val;
      saveJSON(LS_RATINGS, ratings);
      // به‌روزرسانی بصری
      $$('#userStars .star').forEach(s => {
        s.classList.toggle('active', parseInt(s.dataset.star) <= val);
      });
    });
  });

  // دکمه پخش
  const playBtn = $('#playBtn');
  if (playBtn) {
    playBtn.addEventListener('click', () => startPlayback());
  }
}

// ===== شروع پخش (embed تلگرام) =====
function startPlayback() {
  const r = state.route;
  const movie = state.movies.find(m => m.id === r.params.id);
  if (!movie) return;

  const wrap = $('#playerWrap');
  const frame = $('#playerFrame');
  const fallback = $('#embedFallback');
  const tgLink = $('#tgLink');

  wrap.style.display = 'block';

  // ساخت لینک embed تلگرام
  const embedUrl = toTelegramEmbed(movie.telegram_embed);
  frame.src = embedUrl;
  tgLink.href = movie.telegram_embed;

  // اگر embed لود نشد، fallback نشان بده (timeout محافظه‌کارانه)
  let loaded = false;
  frame.addEventListener('load', () => { loaded = true; fallback.classList.remove('show'); });
  setTimeout(() => {
    if (!loaded) fallback.classList.add('show');
  }, 6000);

  // ثبت شروع تماشا (اگر قبلاً پیشرفتی نبود، ۱٪ بگذار)
  const progress = loadJSON(LS_PROGRESS, {});
  if (!progress[movie.id]) {
    progress[movie.id] = 1;
    saveJSON(LS_PROGRESS, progress);
  }

  wrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// تبدیل لینک t.me به embed
function toTelegramEmbed(url) {
  // https://t.me/channel/123  →  https://t.me/channel/123?embed=1&mode=tme
  if (!url) return '';
  const base = url.split('?')[0];
  return base + '?embed=1&mode=tme';
}

// ===== جستجوی زنده =====
function bindSearch() {
  const input = $('#searchInput');
  if (!input) return;
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const q = input.value.trim();
      if (q) location.hash = '#/search/' + encodeURIComponent(q);
      else if (state.route.name === 'search') location.hash = '#/';
    }, 250);
  });
  // پر کردن مقدار جستجو در روت جستجو
  if (state.route.name === 'search') input.value = state.route.params.q || '';
}

// ===== راه‌اندازی =====
async function init() {
  try {
    await loadMovies();
  } catch (err) {
    $('#app').innerHTML = `<div class="empty-state"><div class="big">⚠️</div>
      <p>کاتالوگ فیلم‌ها لود نشد.</p>
      <p style="font-size:.8rem;color:var(--text-faint)">${escapeHTML(err.message)}</p></div>`;
    return;
  }
  window.addEventListener('hashchange', navigate);
  navigate();
  bindSearch();
}

document.addEventListener('DOMContentLoaded', init);

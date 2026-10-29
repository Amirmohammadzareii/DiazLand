#!/usr/bin/env node
/**
 * تست خودبازبینی دیازفلیکس — چک‌لیست منطق بدون بک‌اند.
 * اجرا: node test/selfcheck.js
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
let pass = 0, fail = 0;

function check(name, cond) {
  if (cond) { console.log(`✓ ${name}`); pass++; }
  else { console.log(`✗ ${name}`); fail++; }
}

// ===== ۱) فایل‌های ضروری =====
const required = [
  'index.html', 'css/style.css', 'js/app.js', 'data/movies.json', 'README.md'
];
required.forEach(f => check(`فایل موجود: ${f}`, fs.existsSync(path.join(ROOT, f))));

// ===== ۲) اعتبار movies.json =====
const movies = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/movies.json'), 'utf8'));
check('movies.json آرایه است', Array.isArray(movies));
check('حداقل ۸ فیلم', movies.length >= 8);

const requiredFields = ['id', 'title', 'year', 'genres', 'rating', 'duration', 'description', 'poster', 'telegram_embed', 'added_at'];
let allFields = true, allPosters = true, uniqueIds = new Set();
movies.forEach(m => {
  requiredFields.forEach(f => { if (!(f in m)) allFields = false; });
  if (!fs.existsSync(path.join(ROOT, m.poster))) allPosters = false;
  uniqueIds.add(m.id);
});
check('همه فیلم‌ها فیلدهای لازم را دارند', allFields);
check('همه پوسترها موجودند', allPosters);
check('idها یکتا هستند', uniqueIds.size === movies.length);
check('همه telegram_embed دارند', movies.every(m => m.telegram_embed && m.telegram_embed.startsWith('https://t.me/')));

// ===== ۳) مسیرهای relative (سازگار با GitHub Pages subpath) =====
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const js = fs.readFileSync(path.join(ROOT, 'js/app.js'), 'utf8');
const css = fs.readFileSync(path.join(ROOT, 'css/style.css'), 'utf8');

const absHtml = /(?:src|href)\s*=\s*["']\/(?!\/)/.test(html);
const absJs = /fetch\(\s*["']\/(?!\/)/.test(js);
const absCss = /url\(\s*["']?\/(?!\/)/.test(css);
check('HTML بدون مسیر absolute', !absHtml);
check('JS بدون fetch absolute', !absJs);
check('CSS بدون url absolute', !absCss);

// ===== ۴) hash routeها در JS =====
check('route خانه (#/)', /name:\s*'home'/.test(js));
check('route فیلم (movie/:id)', /parts\[0\]\s*===\s*'movie'/.test(js));
check('route about', /parts\[0\]\s*===\s*'about'/.test(js));
check('route جستجو', /parts\[0\]\s*===\s*'search'/.test(js));

// ===== ۵) localStorage =====
check('کلید پیشرفت تماشا', /diazflix_progress/.test(js));
check('کلید امتیاز کاربر', /diazflix_ratings/.test(js));

// ===== ۶) embed تلگرام + fallback =====
check('تبدیل لینک به embed', /embed=1/.test(js));
check('fallback برای embed', /embedFallback/.test(js));
check('دکمه مشاهده در تلگرام', /مشاهده در تلگرام/.test(js));

// ===== ۷) جستجوی زنده =====
check('جستجوی زنده با debounce', /setTimeout/.test(js) && /searchInput/.test(js));

// ===== ۸) بدون secret =====
const secretPattern = /(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|SECRET_KEY\s*=\s*["'][^"']+)/;
const filesToScan = ['index.html', 'js/app.js', 'css/style.css', 'data/movies.json', 'README.md'];
let hasSecret = false;
filesToScan.forEach(f => {
  const content = fs.readFileSync(path.join(ROOT, f), 'utf8');
  if (secretPattern.test(content)) hasSecret = true;
});
check('هیچ secret در کد نیست', !hasSecret);

// ===== ۹) README شامل راهنما =====
const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
check('README راهنمای افزودن فیلم دارد', /افزودن فیلم|اضافه.*فیلم/.test(readme));
check('README نکته private را دارد', /private|خصوصی/.test(readme));
check('README درباره GitHub Pages توضیح دارد', /Pages|پیجز/.test(readme));

// ===== نتیجه =====
console.log(`\n${fail === 0 ? '🎉' : '❌'} نتیجه: ${pass} پاس، ${fail} شکست`);
process.exit(fail === 0 ? 0 : 1);

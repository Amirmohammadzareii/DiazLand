# -*- coding: utf-8 -*-
"""
لایه پایگاه داده دیازلند — SQLite استاندارد (بدون ORM).
شامل: ساخت جداول، مهاجرت اولیه خودکار، و seed آیتم‌های فروشگاه.
"""

import os
import sqlite3
from datetime import datetime, timezone

# مسیر فایل دیتابیس (قابل تغییر از env برای تست)
DB_PATH = os.environ.get("DIAZLAND_DB", os.path.join(os.path.dirname(__file__), "diazland.db"))

# لیست آیتم‌های فروشگاه ملی (seed اولیه)
SHOP_ITEMS = [
    ("کارت سبز دائمی", "اقامت دائم در دیازلند بدون نیاز به تمدید. مزایا: هیچ‌کس نمی‌تونه اخراجت کنه.", 500, "🟢"),
    ("زمین در پایتخت", "یک قطعه زمین ۱۰۰ متری در قلب پایتخت دیازلند (منطقه ویژه اقتصادی).", 1200, "🏙️"),
    ("عفو عمومی", "تمام تخلفات گذشته‌ات بخشیده می‌شود. یک بار مصرف.", 300, "🕊️"),
    ("سُم دیزل", "نشان افتخاری شهروندی. فقط به افراد خاص اعطا می‌شود.", 800, "🐾"),
    ("مدال شهروند نمونه", "مدال طلایی شهروند ماه. برای پروفایل و استوری.", 200, "🏅"),
    ("بلیت لاتاری ملی", "شانس برنده شدن ۱۰٬۰۰۰ دیاز در قرعه‌کشی هفتگی.", 100, "🎟️"),
    ("خانه ساحلی", "ویلای ساحلی در جزیره دیزل. منظره دریا + اینترنت نامحدود.", 2500, "🏖️"),
    ("عنوان اشرافی", "لقب «دیازبیک» به نامت اضافه می‌شود. خیلی اشرافی.", 1500, "👑"),
]


def get_conn():
    """اتصال به دیتابیس با row factory دیکشنری."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """ساخت جداول در صورت نبودن + seed آیتم‌های فروشگاه."""
    conn = get_conn()
    cur = conn.cursor()

    # جدول کاربران
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            display_name  TEXT    NOT NULL,
            national_id   TEXT    UNIQUE NOT NULL,
            balance       INTEGER NOT NULL DEFAULT 0,
            is_admin      INTEGER NOT NULL DEFAULT 0,
            last_salary_at TEXT,
            created_at    TEXT    NOT NULL
        )
        """
    )

    # جدول قطعات زمین نقشه (فاز ۲) — گرید ۱۶×۱۶ = ۲۵۶ قطعه
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lands (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id     INTEGER,
            x            INTEGER NOT NULL,
            y            INTEGER NOT NULL,
            price        INTEGER NOT NULL,
            building     TEXT,
            message      TEXT,
            purchased_at TEXT,
            UNIQUE (x, y),
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
        """
    )

    # جدول آیتم‌های فروشگاه
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    UNIQUE NOT NULL,
            description TEXT    NOT NULL,
            price       INTEGER NOT NULL,
            emoji       TEXT    NOT NULL DEFAULT '🎁'
        )
        """
    )

    # جدول خریدها
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            item_id    INTEGER NOT NULL,
            price_paid INTEGER NOT NULL,
            created_at TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )
        """
    )

    # جدول متادیتا (شمارنده شماره ملی و ...)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    # seed آیتم‌ها (فقط اگر خالی باشد)
    cur.execute("SELECT COUNT(*) AS c FROM items")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO items (name, description, price, emoji) VALUES (?, ?, ?, ?)",
            SHOP_ITEMS,
        )

    # مقدار اولیه شمارنده شماره ملی
    cur.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('national_counter', '0')")

    # seed قطعات نقشه (فاز ۲)
    seed_lands(conn)

    conn.commit()
    conn.close()


def next_national_id(conn):
    """تولید شماره ملی خودکار به فرمت DZ-000123."""
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta WHERE key = 'national_counter'")
    row = cur.fetchone()
    counter = int(row["value"]) + 1
    cur.execute("UPDATE meta SET value = ? WHERE key = 'national_counter'", (str(counter),))
    return f"DZ-{counter:06d}"


# ---------- نقشه کشور (فاز ۲) ----------
GRID_SIZE = 16          # گرید ۱۶×۱۶
CENTER = (GRID_SIZE - 1) / 2  # مرکز = ۷.۵
# حداکثر فاصله از مرکز (گوشه‌ها)
MAX_DIST = (CENTER ** 2 + CENTER ** 2) ** 0.5


def land_price(x: int, y: int) -> int:
    """
    قیمت قطعه: مرکز گران‌ترین (≈۵۰۰۰ دیاز)، حاشیه ارزان‌ترین (≈۲۰۰ دیاز).
    فرمول تسک: price = round(200 * 1.18^distance) — که در آن distance
    از لبه حساب می‌شود (هرچه به مرکز نزدیک‌تر، distance بیشتر).
    """
    dist_from_center = ((x - CENTER) ** 2 + (y - CENTER) ** 2) ** 0.5
    # معکوس: نزدیک مرکز → عدد بزرگ‌تر
    effective = MAX_DIST - dist_from_center
    return int(round(200 * (1.18 ** effective)))


def seed_lands(conn):
    """ساخت ۲۵۶ قطعه خالی در صورت نبودن (مهاجرت اولیه نقشه)."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM lands")
    if cur.fetchone()["c"] > 0:
        return
    rows = []
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            rows.append((x, y, land_price(x, y)))
    cur.executemany("INSERT INTO lands (x, y, price) VALUES (?, ?, ?)", rows)


def now_iso():
    """زمان فعلی به فرمت ISO (UTC)."""
    return datetime.now(timezone.utc).isoformat()

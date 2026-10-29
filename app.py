# -*- coding: utf-8 -*-
"""
جمهوری دیازلند — اپ اصلی FastAPI.
تمام مسیرها (landing، ثبت‌نام، ورود، پاسپورت، حقوق، فروشگاه، لیدربورد، ادمین).
"""

import os
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import auth
import db

# ---------- تنظیمات ----------
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
SALARY_AMOUNT = 10
SALARY_COOLDOWN_HOURS = 24

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="جمهوری دیازلند", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# سرو فایل‌های استاتیک (پرچم SVG و ...)
_assets_dir = os.path.join(BASE_DIR, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

# init دیتابیس در استارتاپ
db.init_db()


# ---------- ابزارها ----------
def current_user(request: Request):
    """کاربر لاگین‌شده از روی کوکی session؛ در غیر این صورت None."""
    token = request.cookies.get(auth.SESSION_COOKIE)
    uid = auth.read_session(token)
    if uid is None:
        return None
    conn = db.get_conn()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return user


def require_user(request: Request):
    """کاربر لاگین‌شده — در غیر این صورت ریدایرکت به ورود."""
    user = current_user(request)
    return user


def render(request: Request, template: str, **ctx):
    """رندر قالب با context مشترک."""
    user = current_user(request)
    ctx.setdefault("user", user)
    ctx.setdefault("now", datetime.now(timezone.utc))
    return templates.TemplateResponse(request, template, ctx)


# ---------- صفحه اصلی ----------
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    conn = db.get_conn()
    citizen_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    top3 = conn.execute(
        """SELECT display_name, national_id, balance
           FROM users ORDER BY balance DESC, created_at ASC LIMIT 3"""
    ).fetchall()
    lands_owned = conn.execute("SELECT COUNT(*) AS c FROM lands WHERE owner_id IS NOT NULL").fetchone()["c"]
    conn.close()
    return render(
        request,
        "landing.html",
        citizen_count=citizen_count,
        top3=top3,
        lands_owned=lands_owned,
    )


# ---------- ثبت‌نام ----------
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if current_user(request):
        return RedirectResponse("/passport", status_code=302)
    return render(request, "register.html", error=None)


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
):
    username = username.strip().lower()
    display_name = display_name.strip()

    if not username or not password or not display_name:
        return render(request, "register.html", error="همه فیلدها الزامی است.")
    if len(password) < 4:
        return render(request, "register.html", error="رمز عبور باید حداقل ۴ کاراکتر باشد.")
    if not username.replace("_", "").isalnum():
        return render(request, "register.html", error="نام کاربری فقط حروف، عدد و _ مجاز است.")

    conn = db.get_conn()
    exists = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if exists:
        conn.close()
        return render(request, "register.html", error="این نام کاربری قبلاً گرفته شده است.")

    national_id = db.next_national_id(conn)
    is_admin = 1 if username == ADMIN_USERNAME.lower() else 0
    conn.execute(
        """INSERT INTO users (username, password_hash, display_name, national_id,
           balance, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (username, auth.hash_password(password), display_name, national_id, 50, is_admin, db.now_iso()),
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
    conn.close()

    resp = RedirectResponse("/passport", status_code=302)
    resp.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_session(uid),
        httponly=True,
        samesite="lax",
        max_age=auth.SESSION_MAX_AGE,
    )
    return resp


# ---------- ورود / خروج ----------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/passport", status_code=302)
    return render(request, "login.html", error=None)


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    conn = db.get_conn()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not auth.verify_password(password, user["password_hash"]):
        return render(request, "login.html", error="نام کاربری یا رمز عبور اشتباه است.")

    resp = RedirectResponse("/passport", status_code=302)
    resp.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_session(user["id"]),
        httponly=True,
        samesite="lax",
        max_age=auth.SESSION_MAX_AGE,
    )
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


# ---------- پاسپورت ----------
@app.get("/passport", response_class=HTMLResponse)
def passport(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db.get_conn()
    purchases = conn.execute(
        """SELECT p.price_paid, p.created_at, i.name, i.emoji
           FROM purchases p JOIN items i ON i.id = p.item_id
           WHERE p.user_id = ? ORDER BY p.created_at DESC""",
        (user["id"],),
    ).fetchall()
    my_lands = conn.execute(
        "SELECT * FROM lands WHERE owner_id = ? ORDER BY purchased_at DESC",
        (user["id"],),
    ).fetchall()
    conn.close()

    can_salary, next_salary = _salary_status(user)

    return render(
        request,
        "passport.html",
        purchases=purchases,
        my_lands=my_lands,
        can_salary=can_salary,
        next_salary=next_salary,
        passport_created=user["created_at"],
    )


def _salary_status(user):
    """آیا کاربر می‌تواند حقوق بگیرد؟ + زمان بعدی."""
    if not user["last_salary_at"]:
        return True, None
    try:
        last = datetime.fromisoformat(user["last_salary_at"])
    except ValueError:
        return True, None
    next_time = last + timedelta(hours=SALARY_COOLDOWN_HOURS)
    now = datetime.now(timezone.utc)
    if now >= next_time:
        return True, None
    return False, next_time


# ---------- حقوق روزانه ----------
@app.post("/salary")
def salary(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    can, _ = _salary_status(user)
    if not can:
        return RedirectResponse("/passport?msg=cooldown", status_code=302)

    conn = db.get_conn()
    conn.execute(
        "UPDATE users SET balance = balance + ?, last_salary_at = ? WHERE id = ?",
        (SALARY_AMOUNT, db.now_iso(), user["id"]),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/passport?msg=salary", status_code=302)


# ---------- فروشگاه ----------
@app.get("/shop", response_class=HTMLResponse)
def shop(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db.get_conn()
    items = conn.execute("SELECT * FROM items ORDER BY price ASC").fetchall()
    owned = {
        r["item_id"]
        for r in conn.execute(
            "SELECT item_id FROM purchases WHERE user_id = ?", (user["id"],)
        ).fetchall()
    }
    conn.close()
    return render(request, "shop.html", items=items, owned=owned)


@app.post("/buy/{item_id}")
def buy(request: Request, item_id: int):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db.get_conn()
    item = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return RedirectResponse("/shop?msg=notfound", status_code=302)

    fresh = conn.execute("SELECT balance FROM users WHERE id = ?", (user["id"],)).fetchone()
    if fresh["balance"] < item["price"]:
        conn.close()
        return RedirectResponse("/shop?msg=poor", status_code=302)

    conn.execute(
        "UPDATE users SET balance = balance - ? WHERE id = ?", (item["price"], user["id"])
    )
    conn.execute(
        "INSERT INTO purchases (user_id, item_id, price_paid, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], item_id, item["price"], db.now_iso()),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/passport?msg=bought", status_code=302)


# ---------- لیدربورد ----------
@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request):
    conn = db.get_conn()
    top = conn.execute(
        """SELECT display_name, username, national_id, balance
           FROM users ORDER BY balance DESC, created_at ASC LIMIT 10"""
    ).fetchall()
    conn.close()
    return render(request, "leaderboard.html", top=top)


# ---------- نقشه کشور (فاز ۲) ----------
def _user_color(username: str) -> str:
    """رنگ اختصاصی هر کاربر از هش نام کاربری (HSL پایدار)."""
    h = int(hashlib.md5((username or "?").encode("utf-8")).hexdigest()[:8], 16)
    hue = h % 360
    return f"hsl({hue}, 65%, 55%)"


@app.get("/map", response_class=HTMLResponse)
def map_page(request: Request):
    user = current_user(request)
    conn = db.get_conn()
    lands = conn.execute(
        """SELECT l.*, u.username AS owner_username, u.display_name AS owner_name
           FROM lands l LEFT JOIN users u ON u.id = l.owner_id"""
    ).fetchall()
    citizen_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    conn.close()

    # ساخت لیست قطعات برای رندر
    grid = []
    for l in lands:
        grid.append(
            {
                "x": l["x"],
                "y": l["y"],
                "price": l["price"],
                "owner_name": l["owner_name"],
                "owner_username": l["owner_username"],
                "color": _user_color(l["owner_username"]) if l["owner_username"] else None,
                "mine": bool(user and l["owner_id"] == user["id"]),
                "building": l["building"],
            }
        )

    return render(
        request,
        "map.html",
        grid=grid,
        grid_size=db.GRID_SIZE,
        citizen_count=citizen_count,
        user_color=_user_color(user["username"]) if user else None,
    )


@app.post("/map/buy")
def map_buy(request: Request, x: int = Form(...), y: int = Form(...)):
    """خرید یک قطعه خالی روی نقشه."""
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db.get_conn()
    land = conn.execute("SELECT * FROM lands WHERE x = ? AND y = ?", (x, y)).fetchone()
    if not land or land["owner_id"] is not None:
        conn.close()
        return RedirectResponse("/map?msg=taken", status_code=302)

    fresh = conn.execute("SELECT balance FROM users WHERE id = ?", (user["id"],)).fetchone()
    if fresh["balance"] < land["price"]:
        conn.close()
        return RedirectResponse("/map?msg=poor", status_code=302)

    conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (land["price"], user["id"]))
    conn.execute(
        "UPDATE lands SET owner_id = ?, purchased_at = ? WHERE x = ? AND y = ?",
        (user["id"], db.now_iso(), x, y),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(f"/map?msg=bought&x={x}&y={y}", status_code=302)


@app.get("/land/{x}/{y}", response_class=HTMLResponse)
def land_detail(request: Request, x: int, y: int):
    """صفحه اختصاصی یک قطعه زمین."""
    user = current_user(request)
    conn = db.get_conn()
    land = conn.execute(
        """SELECT l.*, u.username AS owner_username, u.display_name AS owner_name
           FROM lands l LEFT JOIN users u ON u.id = l.owner_id
           WHERE l.x = ? AND l.y = ?""",
        (x, y),
    ).fetchone()
    conn.close()

    if not land:
        return RedirectResponse("/map", status_code=302)

    is_mine = bool(user and land["owner_id"] == user["id"])
    return render(request, "land.html", land=land, is_mine=is_mine, x=x, y=y)


@app.post("/land/{x}/{y}/update")
def land_update(
    request: Request,
    x: int,
    y: int,
    building: str = Form(""),
    message: str = Form(""),
):
    """ویرایش بنا و پیام ملک — فقط توسط صاحب ملک."""
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = db.get_conn()
    land = conn.execute("SELECT * FROM lands WHERE x = ? AND y = ?", (x, y)).fetchone()
    if not land or land["owner_id"] != user["id"]:
        conn.close()
        return RedirectResponse("/map", status_code=302)

    building = building.strip()[:40]
    message = message.strip()[:100]  # حداکثر ۱۰۰ حرف طبق تسک
    conn.execute(
        "UPDATE lands SET building = ?, message = ? WHERE x = ? AND y = ?",
        (building or None, message or None, x, y),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(f"/land/{x}/{y}?msg=saved", status_code=302)


# ---------- شمارنده زنده شهروندان (API) ----------
@app.get("/api/stats")
def api_stats():
    """آمار زنده برای لندینگ (شمارنده شهروندان)."""
    conn = db.get_conn()
    citizens = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    lands_owned = conn.execute("SELECT COUNT(*) AS c FROM lands WHERE owner_id IS NOT NULL").fetchone()["c"]
    conn.close()
    return {"citizens": citizens, "lands_owned": lands_owned}


# ---------- پنل ادمین ----------
@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    user = require_user(request)
    if not user or not user["is_admin"]:
        return RedirectResponse("/", status_code=302)

    conn = db.get_conn()
    users = conn.execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return render(request, "admin.html", users=users)


@app.post("/admin/set-balance")
def admin_set_balance(request: Request, user_id: int = Form(...), balance: int = Form(...)):
    user = require_user(request)
    if not user or not user["is_admin"]:
        return RedirectResponse("/", status_code=302)

    conn = db.get_conn()
    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (balance, user_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin?msg=updated", status_code=302)


# ---------- سلامت ----------
@app.get("/health")
def health():
    return {"status": "ok", "country": "DiazLand"}

# -*- coding: utf-8 -*-
"""
اسکریپت smoke test فاز ۲ دیازلند — تست نقشه تعاملی و خرید قطعه.
جریان: ثبت‌نام → بررسی نقشه → شارژ موجودی (از طریق پنل ادمین) → خرید قطعه → ویرایش ملک.

اجرا (سرور باید بالا باشد):
    python smoke_test_map.py
"""

import os
import re
import sys
import uuid

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def main():
    uname = "mapper_" + uuid.uuid4().hex[:8]
    password = "testpass123"
    admin_user = "admin_" + uuid.uuid4().hex[:6]

    with httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=15) as c:
        # 1) ثبت‌نام کاربر عادی
        r = c.post("/register", data={"username": uname, "password": password, "display_name": "زمین‌خوار"})
        assert r.status_code == 200, f"register failed: {r.status_code}"
        print(f"✓ ثبت‌نام: {uname}")

        # 2) صفحه نقشه
        r = c.get("/map")
        assert r.status_code == 200 and "نقشه کشور" in r.text, "map failed"
        assert "LANDS" in r.text, "map data missing"
        print("✓ نقشه کشور لود شد")

        # 3) API آمار
        r = c.get("/api/stats")
        assert r.status_code == 200 and "citizens" in r.json(), "stats failed"
        print(f"✓ آمار زنده: {r.json()}")

        # 4) خرید با موجودی ناکافی (50 < 200) → باید رد شود
        r = c.post("/map/buy", data={"x": 0, "y": 0})
        assert "poor" in str(r.url), "poor path failed"
        print("✓ خرید با موجودی ناکافی رد شد")

        # 5) ساخت/ورود ادمین و شارژ موجودی کاربر از طریق پنل ادمین
        c.get("/logout")
        # ادمین با نام کاربری ثابت (ADMIN_USERNAME=admin) — اگر هست لاگین، وگرنه ثبت‌نام
        r = c.post("/login", data={"username": "admin", "password": "adminpass"})
        if "پنل مدیریت" not in r.text:
            r = c.post("/register", data={"username": "admin", "password": "adminpass", "display_name": "مدیر"})
        r = c.get("/admin")
        assert "پنل مدیریت" in r.text, "admin panel failed"
        # همه (username, uid) را استخراج کن
        pairs = re.findall(r'<td class="px-4 py-3 text-gray-400">([^<]+)</td>.*?name="user_id" value="(\d+)"', r.text, re.S)
        target_uid = None
        for un, uid in pairs:
            if un.strip() == uname:
                target_uid = uid
                break
        assert target_uid, f"user {uname} not found in admin (pairs={pairs})"
        c.post("/admin/set-balance", data={"user_id": target_uid, "balance": 5000})
        print(f"✓ ادمین موجودی {uname} (uid={target_uid}) را ۵۰۰۰ کرد")
        c.get("/logout")

        # 6) ورود مجدد و خرید موفق
        c.post("/login", data={"username": uname, "password": password})
        r = c.post("/map/buy", data={"x": 0, "y": 0})
        assert "bought" in str(r.url), f"buy failed: {r.url}"
        print("✓ خرید قطعه (0,0) موفق")

        # 7) خرید تکراری باید رد شود
        r = c.post("/map/buy", data={"x": 0, "y": 0})
        assert "taken" in str(r.url), "duplicate buy not blocked"
        print("✓ خرید تکراری همان قطعه رد شد")

        # 8) بررسی صفحه ملک
        r = c.get("/land/0/0")
        assert r.status_code == 200 and "زمین‌خوار" in r.text, "land page failed"
        print("✓ صفحه ملک لود شد")

        # 9) ویرایش ملک
        r = c.post("/land/0/0/update", data={"building": "قصر", "message": "اینجا قصر من است"})
        assert "saved" in str(r.url), "update failed"
        r = c.get("/land/0/0")
        assert "قصر" in r.text and "اینجا قصر من است" in r.text, "update not persisted"
        print("✓ ویرایش ملک (بنا + پیام) ذخیره شد")

        # 10) پاسپورت باید ملک را نشان دهد
        r = c.get("/passport")
        assert "ملک‌های من" in r.text and "قطعه (0, 0)" in r.text, "passport lands missing"
        print("✓ ملک در پاسپورت نمایش داده شد")

    print("\n🎉 همه تست‌های فاز ۲ پاس شدند!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\n❌ تست شکست خورد: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\n❌ اتصال به {BASE_URL} ممکن نشد — سرور را اجرا کنید.")
        sys.exit(1)

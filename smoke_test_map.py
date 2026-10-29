# -*- coding: utf-8 -*-
"""
اسکریپت smoke test فاز ۲ (نسخه نهایی) — لندینگ ۶ صحنه‌ای + نقشه + ملک.
جریان: لندینگ (۶ صحنه) → آمار زنده → ثبت‌نام → نقشه → خرید → صفحه ملک → ویرایش → پاسپورت.

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

    with httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=15) as c:
        # ===== لندینگ: ۶ صحنه =====
        r = c.get("/")
        assert r.status_code == 200, f"landing failed: {r.status_code}"
        scenes = re.findall(r'id="scene-([a-z\-]+)"', r.text)
        assert len(scenes) >= 5, f"landing scenes < 5 (found {len(scenes)}: {scenes})"
        assert "hero" in scenes, "hero scene missing"
        assert "جمهوری دیازلند" in r.text, "title missing"
        print(f"✓ لندینگ با {len(scenes)} صحنه: {scenes}")

        # ===== آمار زنده =====
        r = c.get("/api/stats")
        assert r.status_code == 200 and "citizens" in r.json(), "stats failed"
        print(f"✓ آمار زنده: {r.json()}")

        # ===== ثبت‌نام =====
        r = c.post("/register", data={"username": uname, "password": password, "display_name": "زمین‌خوار"})
        assert r.status_code == 200, f"register failed: {r.status_code}"
        print(f"✓ ثبت‌نام: {uname}")

        # ===== نقشه =====
        r = c.get("/map")
        assert r.status_code == 200 and "نقشه کشور" in r.text, "map failed"
        assert "LANDS" in r.text, "map data missing"
        print("✓ نقشه کشور لود شد")

        # ===== خرید با موجودی ناکافی =====
        r = c.post("/map/buy", data={"x": 0, "y": 0})
        assert "poor" in str(r.url), "poor path failed"
        print("✓ خرید با موجودی ناکافی رد شد")

        # ===== شارژ از پنل ادمین =====
        c.get("/logout")
        r = c.post("/login", data={"username": "admin", "password": "adminpass"})
        if "پنل مدیریت" not in r.text:
            r = c.post("/register", data={"username": "admin", "password": "adminpass", "display_name": "مدیر"})
        r = c.get("/admin")
        assert "پنل مدیریت" in r.text, "admin panel failed"
        pairs = re.findall(r'<td class="px-4 py-3 text-gray-400">([^<]+)</td>.*?name="user_id" value="(\d+)"', r.text, re.S)
        target_uid = next((uid for un, uid in pairs if un.strip() == uname), None)
        assert target_uid, f"user {uname} not found"
        c.post("/admin/set-balance", data={"user_id": target_uid, "balance": 6000})
        print(f"✓ ادمین موجودی {uname} را ۶۰۰۰ کرد")
        c.get("/logout")

        # ===== خرید موفق قطعه مرکزی (گران‌ترین) =====
        c.post("/login", data={"username": uname, "password": password})
        r = c.post("/map/buy", data={"x": 7, "y": 7})
        assert "bought" in str(r.url), f"buy central failed: {r.url}"
        print("✓ خرید قطعه مرکزی (7,7) موفق")

        # ===== خرید تکراری رد شود =====
        r = c.post("/map/buy", data={"x": 7, "y": 7})
        assert "taken" in str(r.url), "duplicate buy not blocked"
        print("✓ خرید تکراری رد شد")

        # ===== صفحه ملک =====
        r = c.get("/land/7/7")
        assert r.status_code == 200 and "زمین‌خوار" in r.text, "land page failed"
        print("✓ صفحه ملک لود شد")

        # ===== ویرایش ملک =====
        r = c.post("/land/7/7/update", data={"building": "قصر", "message": "پایتخت مال منه"})
        assert "saved" in str(r.url), "update failed"
        r = c.get("/land/7/7")
        assert "قصر" in r.text and "پایتخت مال منه" in r.text, "update not persisted"
        print("✓ ویرایش ملک (بنا + پیام) ذخیره شد")

        # ===== پاسپورت: ملک من =====
        r = c.get("/passport")
        assert "ملک‌های من" in r.text and "قطعه (7, 7)" in r.text, "passport lands missing"
        print("✓ ملک در پاسپورت نمایش داده شد")

        # ===== لیدربورد =====
        r = c.get("/leaderboard")
        assert r.status_code == 200 and "لیدربورد" in r.text, "leaderboard failed"
        print("✓ لیدربورد لود شد")

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

# -*- coding: utf-8 -*-
"""
اسکریپت smoke test دیازلند — تست کامل جریان اصلی با httpx.
جریان: ثبت‌نام → ورود → دریافت حقوق → خرید از فروشگاه.

اجرا (سرور باید بالا باشد):
    python smoke_test.py
یا با آدرس دلخواه:
    BASE_URL=http://localhost:8000 python smoke_test.py
"""

import os
import sys
import uuid

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def main():
    ok = True
    # نام کاربری یکتا برای هر اجرا
    uname = "smoke_" + uuid.uuid4().hex[:8]
    password = "testpass123"
    display = "شهروند آزمایشی"

    with httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=15) as c:
        # 1) صفحه اصلی
        r = c.get("/")
        assert r.status_code == 200, f"landing failed: {r.status_code}"
        assert "دیازلند" in r.text, "landing missing title"
        print("✓ صفحه اصلی لود شد")

        # 2) ثبت‌نام (خودکار لاگین می‌شود)
        r = c.post(
            "/register",
            data={"username": uname, "password": password, "display_name": display},
        )
        assert r.status_code == 200, f"register failed: {r.status_code}"
        assert "پاسپورت" in r.text, "register did not redirect to passport"
        print(f"✓ ثبت‌نام موفق: {uname}")

        # 3) بررسی پاسپورت و شماره ملی
        assert "DZ-" in r.text, "national id not shown"
        print("✓ پاسپورت و شماره ملی نمایش داده شد")

        # 4) دریافت حقوق روزانه
        r = c.post("/salary")
        assert r.status_code == 200, f"salary failed: {r.status_code}"
        assert "حقوق" in r.text or "دیاز" in r.text, "salary not applied"
        print("✓ حقوق روزانه دریافت شد")

        # 5) فروشگاه
        r = c.get("/shop")
        assert r.status_code == 200, f"shop failed: {r.status_code}"
        assert "فروشگاه" in r.text, "shop page missing"
        print("✓ فروشگاه لود شد")

        # 6) خرید ارزان‌ترین آیتم (بلیت لاتاری = 100 دیاز؛ موجودی اولیه 50 + 10 = 60)
        #    پس باید با موجودی ناکافی رد شود — تست مسیر خطا
        r = c.post("/buy/6")
        assert r.status_code == 200, f"buy failed: {r.status_code}"
        print("✓ مسیر خرید تست شد (موجودی ناکافی → پیام خطا)")

        # 7) لیدربورد
        r = c.get("/leaderboard")
        assert r.status_code == 200, f"leaderboard failed: {r.status_code}"
        assert "لیدربورد" in r.text, "leaderboard missing"
        print("✓ لیدربورد لود شد")

        # 8) خروج
        r = c.get("/logout")
        assert r.status_code == 200, f"logout failed: {r.status_code}"
        print("✓ خروج انجام شد")

        # 9) ورود مجدد
        r = c.post("/login", data={"username": uname, "password": password})
        assert r.status_code == 200 and "پاسپورت" in r.text, "re-login failed"
        print("✓ ورود مجدد موفق")

    print("\n🎉 همه تست‌ها پاس شدند!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\n❌ تست شکست خورد: {e}")
        sys.exit(1)
    except httpx.ConnectError:
        print(f"\n❌ اتصال به {BASE_URL} ممکن نشد — سرور را اجرا کنید: uvicorn app:app --port 8000")
        sys.exit(1)

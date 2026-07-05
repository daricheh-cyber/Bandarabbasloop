import os
import csv
import re
import json
import gspread
from serpapi import GoogleSearch
from datetime import datetime
from google.oauth2.service_account import Credentials

# دسته‌بندی کسب‌وکارها به ترتیب اولویت
CATEGORIES = [
    "واردکنندگان و فروشگاه های منطقه آزاد بندرعباس",
    "نمایندگی های خودرو و موتور بندرعباس",
    "هتل ها و مجتمع های تجاری بندرعباس",
    "آموزشگاه ها و کلینیک های بندرعباس",
    "شرکت های حمل و نقل و لجستیک بندرعباس",
    "رستوران ها و فست فود بندرعباس",
    "فروشگاه های لوازم خانگی و الکترونیک بندرعباس",
    "بانک ها و موسسات مالی بندرعباس",
    "پزشکان و کلینیک های تخصصی بندرعباس",
    "فروشگاه های پوشاک و مد بندرعباس",
    "آرایشگاه های زنانه و سالن های زیبایی بندرعباس",
    "فروشگاه های لوازم آرایشی و بهداشتی بندرعباس",
]

CSV_FILE = "leads.csv"
HEADERS = ["نام کسب‌وکار", "صنف", "شماره موبایل", "شماره ثابت", "منبع", "تاریخ"]
SHEET_ID = "1eQEEc-lroJh1R45hdYC5rAgFg4UcHdq5fhTbdSkkT7Y"

MOBILE_RE = re.compile(r'\b(09[0-9]{9})\b')
PHONE_RE  = re.compile(r'\b(0[1-8][0-9]{9})\b')


def get_sheet():
    """اتصال به گوگل شیت"""
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1

    # اضافه کردن هدر اگه شیت خالیه
    if sheet.row_count == 0 or sheet.cell(1, 1).value is None:
        sheet.append_row(HEADERS)

    return sheet


def load_existing(filepath):
    """بارگذاری داده‌های موجود از CSV"""
    if not os.path.exists(filepath):
        return [], set(), set()
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    seen_mobiles = {r["شماره موبایل"] for r in rows if r.get("شماره موبایل")}
    seen_cats    = {r["صنف"] for r in rows if r.get("صنف")}
    return rows, seen_mobiles, seen_cats


def search_category(category, api_key):
    """جستجوی یک دسته در گوگل و استخراج شماره‌ها"""
    leads = []
    queries = [
        f"{category} شماره تماس",
        f"{category} موبایل",
    ]
    for query in queries:
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "hl": "fa",
            "gl": "ir",
            "num": 10,
        }
        results = GoogleSearch(params).get_dict()
        for r in results.get("organic_results", []):
            text   = (r.get("title", "") + " " + r.get("snippet", ""))
            source = r.get("link", "")
            name   = r.get("title", "")[:60]

            mobiles = MOBILE_RE.findall(text)
            phones  = PHONE_RE.findall(text)

            if mobiles or phones:
                leads.append({
                    "نام کسب‌وکار": name,
                    "صنف": category.replace(" بندرعباس", ""),
                    "شماره موبایل": mobiles[0] if mobiles else "",
                    "شماره ثابت":   phones[0]  if phones  else "",
                    "منبع": source,
                    "تاریخ": datetime.now().strftime("%Y-%m-%d"),
                })
    return leads


def main():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY تنظیم نشده!")

    existing_rows, seen_mobiles, seen_cats = load_existing(CSV_FILE)

    # پیدا کردن دسته بعدی
    next_cat = None
    for cat in CATEGORIES:
        short = cat.replace(" بندرعباس", "")
        if short not in seen_cats:
            next_cat = cat
            break

    if not next_cat:
        print("✅ همه دسته‌ها پردازش شدند!")
        return

    print(f"🔍 جستجو: {next_cat}")
    new_leads = search_category(next_cat, api_key)

    # حذف تکراری‌ها
    unique = []
    for lead in new_leads:
        mob = lead["شماره موبایل"]
        if mob and mob in seen_mobiles:
            continue
        seen_mobiles.add(mob)
        unique.append(lead)

    # ذخیره در CSV محلی
    all_rows = existing_rows + unique
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(all_rows)

    # ذخیره در گوگل شیت
    if unique:
        sheet = get_sheet()
        for lead in unique:
            sheet.append_row([
                lead["نام کسب‌وکار"],
                lead["صنف"],
                lead["شماره موبایل"],
                lead["شماره ثابت"],
                lead["منبع"],
                lead["تاریخ"],
            ])
        print(f"✅ {len(unique)} مخاطب جدید در گوگل شیت ذخیره شد — مجموع: {len(all_rows)}")
    else:
        print(f"ℹ️ مخاطب جدیدی پیدا نشد — مجموع: {len(all_rows)}")


if __name__ == "__main__":
    main()

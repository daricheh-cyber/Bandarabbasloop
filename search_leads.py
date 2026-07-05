import os
import csv
import re
import json
import gspread
from serpapi import GoogleSearch
from datetime import datetime
from google.oauth2.service_account import Credentials

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
HEADERS = ["نام کسب\u200cوکار", "صنف", "شماره موبایل", "شماره ثابت", "منبع", "تاریخ"]
SHEET_ID = "1eQEEc-lroJh1R45hdYC5rAgFg4UcHdq5fhTbdSkkT7Y"
MOBILE_RE = re.compile(r'\b(09[0-9]{9})\b')
PHONE_RE  = re.compile(r'\b(0[1-8][0-9]{9})\b')


def get_sheet():
    raw = os.environ.get("GOOGLE_CREDENTIALS", "").strip()
    # استخراج JSON از متن
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError("GOOGLE_CREDENTIALS: JSON معتبر پیدا نشد")
    creds_json = json.loads(match.group(0))
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    if not sheet.row_values(1):
        sheet.append_row(HEADERS)
    return sheet


def load_existing(filepath):
    if not os.path.exists(filepath):
        return [], set(), set()
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    seen_mobiles = {r["شماره موبایل"] for r in rows if r.get("شماره موبایل")}
    seen_cats    = {r["صنف"] for r in rows if r.get("صنف")}
    return rows, seen_mobiles, seen_cats


def search_category(category, api_key):
    leads = []
    for query in [f"{category} شماره تماس", f"{category} موبایل"]:
        params = {"engine": "google", "q": query, "api_key": api_key, "hl": "fa", "gl": "ir", "num": 10}
        results = GoogleSearch(params).get_dict()
        for r in results.get("organic_results", []):
            text = r.get("title", "") + " " + r.get("snippet", "")
            mobiles = MOBILE_RE.findall(text)
            phones  = PHONE_RE.findall(text)
            if mobiles or phones:
                leads.append({
                    "نام کسب\u200cوکار": r.get("title", "")[:60],
                    "صنف": category.replace(" بندرعباس", ""),
                    "شماره موبایل": mobiles[0] if mobiles else "",
                    "شماره ثابت":   phones[0]  if phones  else "",
                    "منبع": r.get("link", ""),
                    "تاریخ": datetime.now().strftime("%Y-%m-%d"),
                })
    return leads


def main():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        raise ValueError("SERPAPI_KEY تنظیم نشده!")

    existing_rows, seen_mobiles, seen_cats = load_existing(CSV_FILE)

    next_cat = None
    for cat in CATEGORIES:
        if cat.replace(" بندرعباس", "") not in seen_cats:
            next_cat = cat
            break

    if not next_cat:
        print("همه دسته ها پردازش شدند!")
        return

    print(f"جستجو: {next_cat}")
    new_leads = search_category(next_cat, api_key)

    unique = []
    for lead in new_leads:
        mob = lead["شماره موبایل"]
        if mob and mob in seen_mobiles:
            continue
        seen_mobiles.add(mob)
        unique.append(lead)

    all_rows = existing_rows + unique
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(all_rows)

    if unique:
        sheet = get_sheet()
        for lead in unique:
            sheet.append_row([lead["نام کسب\u200cوکار"], lead["صنف"], lead["شماره موبایل"], lead["شماره ثابت"], lead["منبع"], lead["تاریخ"]])
        print(f"{len(unique)} مخاطب جدید در گوگل شیت - مجموع: {len(all_rows)}")
    else:
        print(f"مخاطب جدیدی پیدا نشد - مجموع: {len(all_rows)}")


if __name__ == "__main__":
    main()

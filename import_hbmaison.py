#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone HB-Maison importer.

Defaults (no args):
- Find HB-Maison.xlsm automatically under BASE_DIR (and common subfolders)
- Backup DB (JSON + SQLite file if applicable)
- Wipe Party/Item/Inventory/Transaction
- Import from 'Transactions' sheet (header row = 3rd visual row)
- Sync Party roles from history, prune orphan Parties
"""

"""
python import_hbmaison.py --no-wipe           # پاک نکنه
python import_hbmaison.py --no-backup         # بک‌آپ نگیره
python import_hbmaison.py --excel /path/file.xlsm
python import_hbmaison.py --settings mysite.settings
python import_hbmaison.py --limit 200 --strict
python import_hbmaison.py --app ledger --database default
"""


import os
import sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")  # اسم پروژه‌ات را جایگزین کن

import django
django.setup()


from ledger.models import OP_SELL, OP_BUY, OP_RCV, OP_PAY, OP_USE
import argparse
import shutil
from datetime import datetime
from typing import Optional, Tuple

import warnings
warnings.filterwarnings(
    "ignore",
    message="Data Validation extension is not supported and will be removed"
)


# ---------------- Django bootstrap ----------------
def _guess_settings(base_dir: str) -> Optional[str]:
    for name in os.listdir(base_dir):
        p = os.path.join(base_dir, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "settings.py")):
            return f"{name}.settings"
    return None

def django_setup(settings_module: Optional[str] = None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    if not settings_module:
        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
    if not settings_module:
        guess = _guess_settings(base_dir)
        if not guess:
            raise RuntimeError("Could not auto-detect settings. Pass --settings or set DJANGO_SETTINGS_MODULE.")
        settings_module = guess
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    import django
    django.setup()
    return settings_module

# ---------------- Helpers ----------------
COMMON_LOCATIONS = ["", "mysite", "media", "uploads", "media/uploads"]

def find_excel(default_name="HB-Maison.xlsm") -> Optional[str]:
    base = os.path.dirname(os.path.abspath(__file__))
    # abs path?
    if os.path.isabs(default_name) and os.path.exists(default_name):
        return default_name
    # base/
    cand = os.path.join(base, default_name)
    if os.path.exists(cand):
        return cand
    # common subdirs
    for rel in COMMON_LOCATIONS:
        cand = os.path.join(base, rel, default_name) if rel else os.path.join(base, default_name)
        if os.path.exists(cand):
            return cand
    return None

def ensure_backups_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    bdir = os.path.join(base, "backups")
    os.makedirs(bdir, exist_ok=True)
    return bdir

def backup_database(database_alias: str = "default"):
    from django.core import management
    from django.conf import settings
    bdir = ensure_backups_dir()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    # JSON dump
    json_path = os.path.join(bdir, f"dump-{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        management.call_command(
            "dumpdata",
            "--natural-foreign", "--natural-primary",
            "--indent", "2",
            stdout=f,
            database=database_alias
        )
    print(f"✅ JSON backup: {json_path}")

    # SQLite copy (if applicable)
    dbcfg = settings.DATABASES.get(database_alias, {})
    engine = dbcfg.get("ENGINE", "")
    if "sqlite" in engine:
        db_path = dbcfg.get("NAME")
        if db_path and os.path.exists(db_path):
            sqlite_copy = os.path.join(bdir, f"db-{ts}.sqlite3")
            shutil.copy2(db_path, sqlite_copy)
            print(f"✅ SQLite backup: {sqlite_copy}")

# --- Jalali -> Gregorian (no external deps) ---
def jalali_to_gregorian(j_y: int, j_m: int, j_d: int) -> Tuple[int, int, int]:
    jy = j_y - 979
    jm = j_m - 1
    jd = j_d - 1
    j_day_no = 365 * jy + jy // 33 * 8 + ((jy % 33) + 3) // 4
    for i in range(jm):
        j_day_no += 31 if i < 6 else 30
    j_day_no += jd
    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097
    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False
    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365
    md = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and g_day_no >= md[gm]:
        g_day_no -= md[gm]
        gm += 1
    gd = g_day_no + 1
    return gy, gm + 1, gd

def z2(n: int) -> str: return f"{int(n):02d}"

def norm_str(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = str(s)
    s = s.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")  # ی/ک عربی → فارسی
    s = s.replace("\u200c", "").replace("\xa0", " ")               # حذف ZWNJ/NBSP
    s = s.strip()
    low = s.lower()
    if low in ("nan", "none", "null"):
        return None
    return s or None

# مپ ورودی‌های مختلف به کدهای استاندارد مدل
OP_MAP = {
    "فروش"    : OP_SELL,
    "خرید"     : OP_BUY,
    "دریافت"    : OP_RCV,
    "پرداخت"   : OP_PAY,
    "استفاده خودم": OP_USE,
}

SKIP_PARTIES = {"کارت خوان 1", "کارت خوان 2"}

SETTLEMENT_MAP = {
    "نقدی": "CASH",
    "کارت خوان 1": "POS1",
    "کارت خوان 2": "POS2",
    "حساب بلو": "ACC3",
    "حساب 5802": "ACC2",
    "حساب 1901": "ACC1",

    # حالت‌های جایگزین
    "کارت‌خوان 1": "POS1",
    "کارت‌خوان 2": "POS2",
    "اعتباری": "CASH",
    "کارت هنگامه": "HEN1",
    "حساب 1090": "ACC1",
    "حساب هستی": "HEN2",
}

# --------------- Import core ---------------
def run_import(excel_path: str, app_label: str = "ledger", limit: Optional[int] = None, strict: bool = False):
    import pandas as pd
    from django.apps import apps
    from django.db import transaction as dbtx
    from ledger.services.stock import post_stock_tx

    def to_int0(x):
        # NaN/None/"" → 0 ؛ عدد اعشاری → floor/int
        if x is None:
            return 0
        try:
            if pd.isna(x):
                return 0
        except Exception:
            pass
        try:
            return int(float(x))
        except Exception:
            return 0

    Transaction = apps.get_model(app_label, "Transaction")
    Party = apps.get_model(app_label, "Party")
    Item = apps.get_model(app_label, "Item")

    HEADER_ROW = 2
    SHEET_NAME_CANDIDATES = ["transactions", "Transactions"]
    df = None
    for SHEET_NAME in SHEET_NAME_CANDIDATES:
        try:
            df = pd.read_excel(excel_path, sheet_name=SHEET_NAME, header=HEADER_ROW)
            break
        except Exception:
            pass
    if df is None:
        raise RuntimeError("Failed to read Excel: could not find sheet 'transactions' or 'Transactions'")

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
    df = df.rename(columns={
        "سال": "year", "ماه": "month", "روز": "day",
        "نوع عملیات": "op_type", "کالا": "item_name", "فروشنده / مشتری": "party_name",
        "تعداد": "qty", "قیمت واحد": "unit_price",
        "قیمت کل": "total_price", "تسویه": "payment_amount", "نحوه تسویه": "payment_method",
        "سود فروش": "profit",
    })

    for c in ["year", "month", "day"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ["qty", "unit_price", "total_price", "payment_amount", "profit"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["op_type", "item_name", "party_name", "payment_method"]:
        if c in df.columns: df[c] = df[c].apply(norm_str)

    # فیلتر ردیف‌های فاقد نوع عملیات
    if "op_type" not in df.columns:
        raise RuntimeError("Excel is missing 'op_type' (ستون «نوع عملیات»)")
    before = len(df)
    df = df[df["op_type"].notna() & (df["op_type"].str.strip() != "")]
    removed = before - len(df)
    if removed:
        print(f"⚠ {removed} rows dropped: missing op_type")

    # ⬇️ فیلتر: ردیف‌هایی که نوع عملیات ندارند حذف شوند
    if "op_type" not in df.columns:
        raise RuntimeError("Excel is missing 'op_type' (ستون «نوع عملیات»)")

    before = len(df)
    df = df[df["op_type"].notna() & (df["op_type"].str.strip() != "")]
    removed = before - len(df)
    if removed:
        print(f"⚠ {removed} rows dropped: missing op_type")

    shamsi, miladi, ok = [], [], []
    for _, row in df.iterrows():
        y = row.get("year"); m = row.get("month"); d = row.get("day")
        if y < 100: y += 1400
        if pd.isna(y) or pd.isna(m) or pd.isna(d):
            shamsi.append(None); miladi.append(None); ok.append(False); continue
        y, m, d = int(y), int(m), int(d)
        sh = f"{y}/{z2(m)}/{z2(d)}"
        try:
            gy, gm, gd = jalali_to_gregorian(y, m, d)
            gr = f"{gy}-{z2(gm)}-{z2(gd)}"
            shamsi.append(sh); miladi.append(gr); ok.append(True)
        except Exception:
            shamsi.append(sh); miladi.append(None); ok.append(False)
    df["date_shamsi"] = shamsi
    df["date_miladi"] = miladi
    df["date_ok"] = ok

    if limit: df = df.head(limit)

    party_cache, item_cache = {}, {}
    def get_or_create_party(name: Optional[str]):
        if not name: return None
        if name in party_cache: return party_cache[name]
        obj, _ = Party.objects.get_or_create(name=name, defaults={"is_customer": True, "is_supplier": False})

        if not (obj.is_customer or obj.is_supplier):
            obj.is_customer = True
            obj.is_supplier = False
            obj.save(update_fields=["is_customer", "is_supplier"])

        party_cache[name] = obj
        return obj

    def get_or_create_item(name: Optional[str], is_consignment):
        if not name: return None
        if name in item_cache: return item_cache[name]
        obj, _ = Item.objects.get_or_create(name=name, defaults={"unit": "عدد"})

        if obj.unit != "عدد":
            obj.unit = "عدد"
            obj.save(update_fields=["unit"])

        if obj.group != "formal":
            obj.group = "formal"
            obj.save(update_fields=["group"])

        if is_consignment:
            obj.is_consignment = True
            obj.commission_amount = 0
            obj.commission_percent = 0
            obj.save(update_fields=["is_consignment", "commission_amount", "commission_percent"])

        item_cache[name] = obj
        return obj

    created_tx = skipped = updated_sell_price = 0
    from datetime import date as _date

    @dbtx.atomic
    def do_import():
        nonlocal created_tx, skipped, updated_sell_price
        for _, r in df.iterrows():
            if not r.get("date_ok"): skipped += 1; continue
            if r.get("party_name") in SKIP_PARTIES: skipped +=1; continue

            op_type = OP_MAP.get(r.get("op_type"), None)
            if not op_type: skipped += 1; continue

            party = get_or_create_party(r.get("party_name")) if r.get("party_name") else None
            qty         = to_int0(r.get("qty"))
            unit_price  = to_int0(r.get("unit_price"))
            total_price = to_int0(r.get("total_price"))
            payment_amount = to_int0(r.get("payment_amount"))
            method = SETTLEMENT_MAP.get(r.get("payment_method") or "", "CASH")
            item_name = r.get("item_name")

            y, m, d = map(int, str(r.get("date_miladi")).split("-"))
            dm_date = _date(y, m, d)

            if op_type in (OP_SELL, OP_BUY, OP_USE):
                if not item_name:
                    item_name = "(سیستمی) قلم نامشخص"

                item = get_or_create_item(item_name, method == 'اعتباری')

                if not qty or qty <= 0:
                    continue
                if unit_price is None or unit_price < 0:
                    unit_price = to_int0(total_price // qty) if (total_price is not None and qty) else 0
                if total_price is None:
                    total_price = (unit_price or 0) * (qty or 0)

                post_stock_tx(
                    date_shamsi=r.get("date_shamsi"),
                    date_miladi=dm_date,
                    op_type=op_type,
                    item=item,
                    party=party,
                    qty=qty,
                    unit_price=unit_price,
                    total_price=total_price,
                    payment_method=None,
                )
                created_tx += 1

                if op_type == OP_SELL:
                    if item.sell_price != unit_price:
                        item.sell_price = unit_price
                        item.save(update_fields=["sell_price"])
                        updated_sell_price += 1

            if payment_amount > 0:
                description = item_name if op_type in (OP_RCV, OP_PAY) else None

                if op_type in (OP_SELL, OP_RCV, OP_USE):
                    op_type = OP_RCV
                elif op_type in (OP_BUY, OP_PAY):
                    op_type = OP_PAY
                else:
                    continue

                Transaction.objects.create(
                    date_shamsi=r.get("date_shamsi"),
                    date_miladi=dm_date,
                    op_type=op_type,
                    party=party,
                    item=None,
                    qty=None,
                    unit_price=None,
                    total_price=payment_amount,
                    payment_method=method,
                    description=description,
                )
                created_tx += 1

    do_import()
    print(f"📊 Import: created≈{created_tx}, skipped={skipped}")
    print(f"🧾 Updated Sell Price: {updated_sell_price}")

def sync_roles_and_prune(app_label: str = "ledger"):
    from django.db.models import Q, Count
    from django.apps import apps
    Party = apps.get_model(app_label, "Party")
    Transaction = apps.get_model(app_label, "Transaction")

    stats = (
        Transaction.objects.exclude(party__isnull=True)
        .values("party")
        .annotate(
            sale=Count("id", filter=Q(op_type="SELL")),
            recv=Count("id", filter=Q(op_type="RCV")),
            purch=Count("id", filter=Q(op_type="BUY")),
            pay=Count("id", filter=Q(op_type="PAY")),
            own=Count("id", filter=Q(op_type="USE")),
        )
    )
    updated = 0
    for r in stats:
        pid = r["party"]
        cust = (r["sale"] or 0) + (r["recv"] or 0) + (r["own"] or 0)
        supp = (r["purch"] or 0) + (r["pay"] or 0)
        # cust و supp همان شمارنده‌های مشتری/فروشنده شما هستند

        is_customer = cust > 0
        is_supplier = supp > 0

        if not is_customer and not is_supplier:
            is_customer = True

        p = Party.objects.get(id=pid)
        if p.is_customer != is_customer or p.is_supplier != is_supplier:
            p.is_customer = is_customer
            p.is_supplier = is_supplier
            p.save(update_fields=["is_customer", "is_supplier"])
            updated += 1

    pruned = Party.objects.filter(transactions__isnull=True).count()
    Party.objects.filter(transactions__isnull=True).delete()
    print(f"👥 Roles synced (updated={updated}); 🧽 orphan Parties pruned={pruned}")

# --------------- CLI ---------------
def main():
    parser = argparse.ArgumentParser(description="HB-Maison Excel importer (standalone).")
    parser.add_argument("--excel", help="Path to HB-Maison.xlsm (optional; auto-discover if omitted)")
    parser.add_argument("--settings", help="Django settings module, e.g. mysite.settings")
    parser.add_argument("--app", default="ledger", help="App label (default: ledger)")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows")
    parser.add_argument("--strict", action="store_true", help="Strict amount validation")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    parser.add_argument("--no-wipe", action="store_true", help="Do not wipe tables")
    parser.add_argument("--database", default="default", help="Database alias (default: default)")
    args = parser.parse_args()

    settings_module = django_setup(args.settings)
    print(f"⚙ Using settings: {settings_module}")

    # Excel auto-discovery if not provided
    excel = args.excel or find_excel("HB-Maison.xlsm")
    if not excel or not os.path.exists(excel):
        raise SystemExit("❌ Excel file not found. Put 'HB-Maison.xlsm' next to manage.py or pass --excel /full/path.xlsm")

    # Backup (default ON)
    if not args.no_backup:
        backup_database(args.database)
    else:
        print("⚠ Skipping backup (--no-backup).")

    # Wipe (default ON)
    from django.apps import apps
    from django.db import transaction as dbtx
    Party = apps.get_model(args.app, "Party")
    Item = apps.get_model(args.app, "Item")
    Inventory = apps.get_model(args.app, "Inventory")
    Transaction = apps.get_model(args.app, "Transaction")

    if not args.no_wipe:
        print("🧹 Wiping tables (Transaction, Inventory, Item, Party)...")
        with dbtx.atomic():
            Transaction.objects.all().delete()
            Inventory.objects.all().delete()
            Item.objects.all().delete()
            Party.objects.all().delete()
        print("✔ Tables wiped.")
    else:
        print("↷ Skip wiping (--no-wipe).")

    # Import
    run_import(excel_path=excel, app_label=args.app, limit=args.limit, strict=args.strict)

    # Post-process
    sync_roles_and_prune(app_label=args.app)

    Item = apps.get_model("ledger", "Item")
    Item.objects.exclude(unit="عدد").update(unit="عدد")
    print("🧾 Units normalized to 'عدد' for all items.")

    print("✅ DONE.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild inventory and COGS by FIFO replay for all items.

- Inventory valuation: FIFO
- Supports negative inventory and temporary COGS (is_cogs_temp=True)
- Sales before the first purchase are priced at sales price initially,
  but corrected to purchase price when purchases arrive.
"""

import os, sys, argparse
from typing import Optional
from collections import deque

def _guess_settings(base_dir: str) -> Optional[str]:
    for name in os.listdir(base_dir):
        p = os.path.join(base_dir, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "settings.py")):
            return f"{name}.settings"
    return None

def django_setup(settings_module=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    if not settings_module:
        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE") or _guess_settings(base_dir)
    if not settings_module:
        raise RuntimeError("Could not detect settings. Use --settings <pkg.settings>.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    import django; django.setup()
    return settings_module

def main():
    parser = argparse.ArgumentParser(description="Rebuild inventory & COGS by FIFO replay.")
    parser.add_argument("--settings", help="Django settings module, e.g. mysite.settings")
    parser.add_argument("--app", default="ledger", help="App label (default: ledger)")
    args = parser.parse_args()

    settings_module = django_setup(args.settings)
    print(f"⚙ Using settings: {settings_module} | Policy: FIFO")

    from django.apps import apps
    from django.db import transaction as dbtx

    Transaction = apps.get_model(args.app, "Transaction")
    Inventory   = apps.get_model(args.app, "Inventory")
    Item        = apps.get_model(args.app, "Item")
    from ledger.models import OP_BUY, OP_SELL, OP_USE

    print("♻ Resetting inventory snapshots and COGS...")
    Inventory.objects.update(qty=0, last_buy_cost=0)
    Transaction.objects.update(cogs=None, is_cogs_temp=False)

    item_ids = list(Item.objects.values_list("id", flat=True))
    print(f"📦 Items to rebuild: {len(item_ids)}")

    rebuilt_items = 0
    updated_count = 0

    @dbtx.atomic
    def rebuild_one(item_id: int):
        nonlocal updated_count, rebuilt_items

        inv, _ = Inventory.objects.select_for_update().get_or_create(
            item_id=item_id, defaults={"qty":0, "last_buy_cost":0}
        )

        qs = (Transaction.objects
              .filter(item_id=item_id)
              .order_by("date_miladi", "id")
              .all())

        is_consignment = False
        if qs:
            first_tx = qs[0]
            if first_tx.item and getattr(first_tx.item, "is_consignment", False):
                is_consignment = True

        item = Item.objects.only("is_consignment").get(pk=item_id)
        is_consignment = item.is_consignment

        # هر لایه: [qty, unit_price, tx_ref]
        # tx_ref فقط برای لایه‌های منفی (فروش‌های موقت) نگه داشته می‌شود
        layers = deque()
        changed_txs = []

        last_buy_price = None  # آخرین قیمت خرید دیده‌شده تا این لحظه

        for tx in qs:
            op = tx.op_type
            q  = int(tx.qty or 0)
            up = int(tx.unit_price or 0)

            # --- منطق ویژه برای کالاهای امانی ---
            if is_consignment:
                if op == OP_BUY:
                    inv.qty += q
                    tx.cogs = None
                    last_buy_price = up
                elif op == OP_SELL:
                    inv.qty -= q
                    # فروش امانی: COGS = (unit_price - کمیسیون) * qty
                    commission = 0
                    if tx.item.commission_amount:
                        commission = int(tx.item.commission_amount)
                    elif tx.item.commission_percent:
                        commission = int(up * tx.item.commission_percent / 100)

                    if up == 0:
                        last_buy_tx = (
                            Transaction.objects
                            .filter(item=tx.item, op_type=OP_BUY, date_miladi__lt=tx.date_miladi)
                            .order_by("-date_miladi", "-id")
                            .first()
                        )
                        if last_buy_tx:
                            tx.cogs = (last_buy_tx.unit_price) * q
                        else:
                            tx.cogs = 0  # یا هشدار چون ما قبل از خرید کالایی رو فروختیم
                    else:
                        tx.cogs = (up - commission) * q

                elif op == OP_USE:
                    inv.qty -= q

                    last_buy_tx = (
                        Transaction.objects
                        .filter(item=tx.item, op_type=OP_BUY, date_miladi__lt=tx.date_miladi)
                        .order_by("-date_miladi", "-id")
                        .first()
                    )
                    if last_buy_tx:
                        tx.cogs = (last_buy_tx.unit_price or 0) * q
                    else:
                        tx.cogs = 0  # یا هشدار چون ما قبل از خرید کالایی رو استفاده/هدیه دادیم

                else:
                    continue

                tx.is_cogs_temp = False
                changed_txs.append(tx)
                # ادامه نده، برو سراغ تراکنش بعدی
                continue

            if op == OP_BUY:
                buy_qty = q

                # ابتدا قدیمی‌ترین منفی‌ها را پوشش بده و COGS فروش‌هایشان را اصلاح کن
                while buy_qty > 0 and layers and layers[0][0] < 0:
                    neg_qty, neg_price, neg_tx = layers[0]
                    cover = min(buy_qty, -neg_qty)

                    # COGS فروش قبلی = COGS قبلی - (cover*neg_price) + (cover*قیمت خرید جاری)
                    neg_tx.cogs = (neg_tx.cogs - cover * neg_price) + (cover * up)

                    # اگر کامل پوشش داده شد → دیگر موقت نیست
                    if neg_qty + cover == 0:
                        neg_tx.is_cogs_temp = False

                    changed_txs.append(neg_tx)

                    # به‌روزرسانی لایه منفی
                    neg_qty += cover
                    buy_qty -= cover
                    if neg_qty == 0:
                        layers.popleft()
                    else:
                        layers[0][0] = neg_qty
                        # ⚠️ قیمت باقی‌مانده لایه منفی را عوض نکن؛ همان neg_price بماند

                # باقی‌مانده خرید → لایه مثبت
                if buy_qty > 0:
                    layers.append([buy_qty, up, None])

                # آخرین قیمت خرید
                last_buy_price = up

                # خرید COGS ندارد
                tx.cogs = None
                tx.is_cogs_temp = False
                changed_txs.append(tx)

            elif op in (OP_SELL, OP_USE):
                sell_qty = q
                cogs_val = 0

                # مصرف از لایه‌های مثبت (FIFO)
                while sell_qty > 0 and layers and layers[0][0] > 0:
                    layer_qty, layer_price, _ = layers[0]
                    consume = min(sell_qty, layer_qty)
                    cogs_val += consume * layer_price
                    sell_qty -= consume
                    layer_qty -= consume
                    if layer_qty == 0:
                        layers.popleft()
                    else:
                        layers[0][0] = layer_qty

                # اگر هنوز فروش باقی مانده → موجودی منفی
                if sell_qty > 0:
                    # قیمت پایه برای بخش منفی:
                    # 1) اگر لایه مثبتِ قبلی داریم، قیمت همان (آخرین خرید واقعی)
                    # 2) وگرنه اگر قبلاً خریدی دیده‌ایم، همان last_buy_price
                    # 3) وگرنه (هیچ خریدی تا کنون نبوده) از قیمت فروش استفاده کن
                    last_pos_price = None
                    for lqty, lprice, _ in reversed(layers):
                        if lqty > 0:
                            last_pos_price = lprice
                            break

                    if last_pos_price is not None:
                        base_price_for_negative = last_pos_price
                    elif last_buy_price is not None:
                        base_price_for_negative = last_buy_price
                    else:
                        base_price_for_negative = up  # اولین فروش‌ها قبل از هر خرید

                    cogs_val += sell_qty * base_price_for_negative
                    # منفی را به انتهای صف اضافه می‌کنیم تا خریدهای بعدی FIFO پوشش دهند
                    layers.append([-sell_qty, base_price_for_negative, tx])
                    tx.is_cogs_temp = True
                else:
                    tx.is_cogs_temp = False

                tx.cogs = cogs_val
                changed_txs.append(tx)
                updated_count += 1

            else:
                # دریافت/پرداخت و ...: COGS ندارد
                tx.cogs = None
                tx.is_cogs_temp = False
                changed_txs.append(tx)

        if changed_txs:
            Transaction.objects.bulk_update(changed_txs, ["cogs", "is_cogs_temp"])

        if is_consignment:
            # موجودی از قبل در حلقه آپدیت شده، فقط ذخیره کن
            last_buy_cost = last_buy_price or 0
        else:
            # اسنپ‌شات موجودی
            qty_sum = sum(l[0] for l in layers)

            # آخرین قیمت خرید
            last_buy_cost = 0
            for lqty, lprice, _ in reversed(layers):
                if lqty > 0:
                    last_buy_cost = lprice
                    break
            if last_buy_cost == 0 and last_buy_price is not None:
                last_buy_cost = last_buy_price

            inv.qty = qty_sum

        inv.last_buy_cost = last_buy_cost
        inv.save(update_fields=["qty", "last_buy_cost"])

        rebuilt_items += 1

    for iid in item_ids:
        rebuild_one(iid)

    print(f"✅ Rebuild done. Items rebuilt={rebuilt_items}, transactions updated={updated_count}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild inventory (qty, avg_cost, last_buy_cost) and COGS by replaying transactions chronologically.

- Inventory valuation: Moving Average (avg_cost), plus last_buy_cost
- COGS policy: LPP (default) or AVG       <-- choose via --policy
- Does NOT touch Item.unit

Usage:
  python recalc_inventory.py
  python recalc_inventory.py --policy LPP
  python recalc_inventory.py --policy AVG
  python recalc_inventory.py --settings mysite.settings --app ledger
"""

import os, sys, argparse
from typing import Optional

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
    parser = argparse.ArgumentParser(description="Rebuild inventory & COGS by chronological replay.")
    parser.add_argument("--settings", help="Django settings module, e.g. mysite.settings")
    parser.add_argument("--app", default="ledger", help="App label (default: ledger)")
    parser.add_argument("--policy", choices=["LPP","AVG"], default="LPP", help="COGS policy (default LPP)")
    args = parser.parse_args()

    settings_module = django_setup(args.settings)
    print(f"⚙ Using settings: {settings_module} | COGS policy: {args.policy}")

    from django.apps import apps
    from django.db import transaction as dbtx

    Transaction = apps.get_model(args.app, "Transaction")
    Inventory   = apps.get_model(args.app, "Inventory")
    Item        = apps.get_model(args.app, "Item")

    from ledger.models import OP_BUY, OP_SELL, OP_USE

    # 0) Reset snapshots and COGS to rebuild from scratch
    print("♻ Resetting inventory snapshots and COGS...")
    Inventory.objects.update(qty=0, avg_cost=0, last_buy_cost=0)
    Transaction.objects.filter(op_type__in=[OP_SELL, OP_USE]).update(cogs=None)

    # 1) Process each item independently
    item_ids = list(Item.objects.values_list("id", flat=True))
    print(f"📦 Items to rebuild: {len(item_ids)}")

    rebuilt_items = 0
    updated_count = 0

    @dbtx.atomic
    def rebuild_one(item_id: int):
        nonlocal updated_count, rebuilt_items
        inv, _ = Inventory.objects.select_for_update().get_or_create(item_id=item_id, defaults={"qty":0,"avg_cost":0,"last_buy_cost":0})
        qty = int(inv.qty or 0)
        avg_cost = int(inv.avg_cost or 0)
        last_buy_cost = int(inv.last_buy_cost or 0)

        # Get transactions for this item in true chronological order
        qs = (Transaction.objects
              .filter(item_id=item_id)
              .order_by("date_miladi", "id")
              .only("id","op_type","qty","unit_price","total_price","date_miladi","cogs"))

        updated_txs = []
        for tx in qs:
            op = tx.op_type
            q  = int(tx.qty or 0)
            up = int(tx.unit_price or 0)

            if op == OP_BUY:
                new_qty = qty + q
                if new_qty > 0:
                    avg_cost = int((qty * avg_cost + q * up) / new_qty)
                qty = new_qty
                last_buy_cost = up
                # خرید COGS ندارد
                if tx.cogs is not None:
                    tx.cogs = None
                    updated_txs.append(tx)

            elif op in ( OP_SELL, OP_USE):
                base_cost = last_buy_cost if args.policy == "LPP" else avg_cost
                cogs = base_cost * q
                qty -= q
                if tx.cogs != cogs:
                    tx.cogs = cogs
                    updated_txs.append(tx)
                    updated_count += 1

            else:
                # دریافت/پرداخت/سایر: در موجودی اثر ندارد؛ COGS هم ندارد
                if tx.cogs is not None:
                    tx.cogs = None
                    updated_txs.append(tx)

        if updated_txs:
            Transaction.objects.bulk_update(updated_txs, ["cogs"])

        # Save snapshot back
        changed = []
        if inv.qty != qty: changed.append("qty")
        if inv.avg_cost != avg_cost: changed.append("avg_cost")
        if inv.last_buy_cost != last_buy_cost: changed.append("last_buy_cost")
        if changed:
            inv.qty = qty
            inv.avg_cost = avg_cost
            inv.last_buy_cost = last_buy_cost
            inv.save(update_fields=changed)
        rebuilt_items += 1

    # Run rebuild
    for iid in item_ids:
        rebuild_one(iid)

    print(f"✅ Rebuild done. Items rebuilt={rebuilt_items}, transactions updated (COGS)={updated_count}")

if __name__ == "__main__":
    main()

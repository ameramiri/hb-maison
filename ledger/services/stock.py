# ledger/services/stock.py
from django.db import transaction
from collections import deque
from ledger.models import Transaction, Inventory, OP_BUY, OP_SELL, OP_USE

@transaction.atomic
def post_stock_tx(
    *, date_shamsi, date_miladi, op_type, item=None, party=None,
    qty=0, unit_price=0, total_price=0, payment_method=None, **extra
):
    """
    ثبت تراکنش + بازپخش کامل تاریخچه همان کالا با FIFO:
    - COGS همه‌ی فروش‌ها (قدیمی و جدید) محاسبه/اصلاح می‌شود
    - فروش‌های قبل از خرید: موقت با قیمت فروش و بعداً با خرید اصلاح می‌شوند
    - اسنپ‌شات موجودی (qty/last_buy_cost) به‌روز می‌شود
    """
    qty = int(qty or 0)
    unit_price = int(unit_price or 0)
    total_price = int(total_price or 0)

    # قفل موجودی کالا
    inv, _ = Inventory.objects.select_for_update().get_or_create(
        item=item, defaults={"qty": 0, "last_buy_cost": 0}
    )

    # 1) ابتدا تراکنش جدید را بسازیم (با cogs=None) تا در بازپخش لحاظ شود
    new_tx = Transaction.objects.create(
        date_shamsi=date_shamsi,
        date_miladi=date_miladi,
        op_type=op_type,
        item=item,
        party=party,
        qty=qty,
        unit_price=unit_price,
        total_price=total_price,
        payment_method=payment_method,
        cogs=None,
        is_cogs_temp=False,
        **extra
    )

    # 2) بازپخش کل تاریخچه همان کالا (همراهِ تراکنش جدید)
    qs = (Transaction.objects
          .filter(item=item)
          .order_by("date_miladi", "id")
          .all())

    is_consignment = getattr(item, "is_consignment", False)

    # هر لایه: [qty, unit_price, tx_ref]
    # tx_ref فقط برای لایه‌های منفی (فروش‌های موقت) نگه داشته می‌شود
    layers = deque()
    changed_txs = []

    last_buy_price = None  # آخرین قیمت خریدِ دیده‌شده در بازپخش

    if is_consignment:
        inv.qty = 0

    for tx in qs:
        op = tx.op_type
        q  = int(tx.qty or 0)
        up = int(tx.unit_price or 0)

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
                    commission = tx.item.commission_amount
                elif tx.item.commission_percent:
                    commission = int(tx.unit_price * tx.item.commission_percent / 100)

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
            # ❗ بعد از انجام منطق امانی، برو آیتم بعدی
            continue

        if op == OP_BUY:
            buy_qty = q

            # ابتدا قدیمی‌ترین منفی‌ها را پوشش بده و COGS فروش‌هایشان را اصلاح کن
            while buy_qty > 0 and layers and layers[0][0] < 0:
                neg_qty, neg_price, neg_tx = layers[0]
                cover = min(buy_qty, -neg_qty)

                # اگر قبلاً COGS نداشت، صفر فرض کن
                orig_cogs = int(neg_tx.cogs or 0)
                # COGS جدید = قدیمی - (cover * neg_price) + (cover * up)
                neg_tx.cogs = orig_cogs - cover * int(neg_price) + cover * up

                # اگر کامل پوشش داده شد → دیگر موقت نیست
                if neg_qty + cover == 0:
                    neg_tx.is_cogs_temp = False
                    layers.popleft()
                else:
                    # پوشش جزئی: temp باقی می‌ماند، فقط مقدار باقی‌مانده منفی کم می‌شود
                    layers[0][0] = neg_qty + cover

                changed_txs.append(neg_tx)
                buy_qty -= cover

            # باقی‌مانده خرید → لایه مثبت
            if buy_qty > 0:
                layers.append([buy_qty, up, None])

            last_buy_price = up

            # خرید COGS ندارد؛ اگر قبلاً چیزی بوده پاک شود
            if tx.cogs is not None or tx.is_cogs_temp:
                tx.cogs = None
                tx.is_cogs_temp = False
                changed_txs.append(tx)

        elif op in (OP_SELL, OP_USE):
            sell_qty = q
            cogs_val = 0

            # مصرف از لایه‌های مثبت (FIFO)
            while sell_qty > 0 and layers and layers[0][0] > 0:
                layer_qty, layer_price, _ = layers[0]
                use = min(sell_qty, layer_qty)
                cogs_val += use * int(layer_price)
                sell_qty -= use
                layer_qty -= use
                if layer_qty == 0:
                    layers.popleft()
                else:
                    layers[0][0] = layer_qty

            # اگر هنوز فروش باقی مانده → موجودی منفی
            if sell_qty > 0:
                # قیمت پایه برای بخش منفی:
                # 1) اگر لایه مثبت داریم → آخرین قیمت خرید واقعی
                # 2) وگرنه اگر قبلاً خریدی دیده‌ایم → last_buy_price
                # 3) وگرنه (هیچ خریدی تا کنون نبوده) → قیمت فروش
                last_pos_price = None
                for lqty, lprice, _ in reversed(layers):
                    if lqty > 0:
                        last_pos_price = lprice
                        break

                if last_pos_price is not None:
                    base_price = int(last_pos_price)
                elif last_buy_price is not None:
                    base_price = int(last_buy_price)
                else:
                    base_price = up  # اولین فروش‌ها قبل از هر خرید

                cogs_val += sell_qty * base_price
                # منفی را به انتهای صف اضافه کن تا خریدهای بعدی FIFO پوشش دهند
                layers.append([-sell_qty, base_price, tx])
                tx.is_cogs_temp = True
            else:
                tx.is_cogs_temp = False

            tx.cogs = cogs_val
            changed_txs.append(tx)

        else:
            # دریافت/پرداخت و ...: COGS ندارد
            if tx.cogs is not None or tx.is_cogs_temp:
                tx.cogs = None
                tx.is_cogs_temp = False
                changed_txs.append(tx)

    # 3) همهٔ تراکنش‌های تغییرکرده را یکجا ذخیره کن
    if changed_txs:
        Transaction.objects.bulk_update(changed_txs, ["cogs", "is_cogs_temp"])

    if is_consignment:
        last_buy_cost = last_buy_price
    else:
        # 4) اسنپ‌شات موجودی را از روی لایه‌ها به‌روز کن
        qty_sum = sum(l[0] for l in layers)

        # آخرین قیمت خرید
        last_buy_cost = 0
        for lqty, lprice, _ in reversed(layers):
            if lqty > 0:
                last_buy_cost = int(lprice)
                break
        if last_buy_cost == 0 and last_buy_price is not None:
            last_buy_cost = int(last_buy_price)

        inv.qty = qty_sum

    inv.last_buy_cost = last_buy_cost
    inv.save(update_fields=["qty", "last_buy_cost"])

    # 5) رکورد جدید را با COGS نهایی برگردان
    new_tx.refresh_from_db(fields=["cogs", "is_cogs_temp"])
    return new_tx

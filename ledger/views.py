from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Item, Party, Transaction, Inventory, OP_SELL, OP_BUY, OP_USE, OP_RCV, OP_PAY, OP_CHOICES, PERSIAN_MONTHS
from django import forms
from .forms import TransactionForm, PartyForm, ItemForm
from django.urls import reverse
from django.utils.http import urlencode
from django.contrib import messages
from django.db.models import Window, Sum, Count, Case, When, Value, F, Q, ExpressionWrapper, IntegerField, BigIntegerField, FloatField
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from datetime import timedelta
from decimal import Decimal
import jdatetime
from .services.stock import post_stock_tx
from django.db.models.functions import Coalesce, Substr, Cast
from persiantools.jdatetime import JalaliDate
from .utils import toEn, ajax_debug_logger

def _last_n_keep_ascending(qs, n):
    # آخرین n تا را می‌گیریم ولی برای نمایش صعودی می‌چینیم
    last_desc = list(qs.order_by('-date_miladi', '-id')[:n])
    return list(reversed(last_desc))

def ajax_party_txs(request):
    party_id    = request.GET.get('party_id')
    from_last   = request.GET.get('from_last') == "1"
    page_source = request.GET.get("source")

    if not party_id:
        return JsonResponse({"html": "<tr><td colspan='6'>طرف حساب انتخاب نشده.</td></tr>", "balance": 0, })

    # پیدا کردن طرف حساب
    try:
        party_id = int(party_id)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("party_id invalid")

    party = Party.objects.filter(id=party_id).first()

    if not party:
        return JsonResponse({
            "html": "<tr><td colspan='6'>طرف حساب پیدا نشد.</td></tr>", "balance": 0, })

    # ساخت QuerySet پایه
    qs = (
        Transaction.objects
        .select_related('item', 'party')
        .filter(party_id=party_id)
        .order_by('date_miladi', 'id')
    )

    # محاسبه delta برای طرف حساب
    qs = qs.annotate(
        delta=Case(
            When(op_type__in=[OP_SELL, OP_USE, OP_PAY], then= Coalesce(F('total_price'), Value(0))),
            When(op_type__in=[OP_BUY, OP_RCV],          then=-Coalesce(F('total_price'), Value(0))),
            default=Value(0),
            output_field=BigIntegerField(),
        )
    )

    # running balance
    qs = qs.annotate(
        running_balance=Window(
            expression=Sum('delta'),
            order_by=[F('date_miladi').asc(), F('id').asc()],
        )
    )

    total_count = qs.count()
    if total_count == 0:
        return JsonResponse({
            "html": "<tr><td colspan='7' class='text-center'>رکوردی یافت نشد</td></tr>",
            "last_id": None,
            "has_more": False,
            "balance": 0,
        })

    # ----- از آخرین تسویه -----
    if from_last:
        last_settle = qs.filter(running_balance=0).last()
        if last_settle:
            qs = qs.filter(id__gt=last_settle.id)

    # ----- آخرین مانده حساب -----
    last_tx = qs.last()
    balance = last_tx.running_balance if last_tx else 0

    # تولید html
    html = render_to_string(
        "ledger/partials/party_modal_txs.html",
        {"txs": qs, "page_source": page_source},
        request=request
    )

    return JsonResponse({
        "html": html,
        "balance": balance,
    })

def ajax_item_txs(request):
    item_id     = request.GET.get("item_id")
    page_source = request.GET.get("source")

    if not item_id:
        return JsonResponse({"html": "<tr><td colspan='6'>کالا انتخاب نشده.</td></tr>"})

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return HttpResponseBadRequest("item_id invalid")

    item = Item.objects.filter(id=item_id).first()
    if not item:
        return JsonResponse({"html": "<tr><td colspan='6'>کالا پیدا نشد.</td></tr>"})

    qs = (
        Transaction.objects
        .select_related('item','party')
        .filter(item_id=item_id, op_type__in=[OP_SELL, OP_BUY, OP_USE])
        .order_by('date_miladi', 'id')
        .annotate(
            delta=Case(
                When(op_type=OP_BUY,  then=Coalesce(F('qty'), Value(0))),
                When(op_type=OP_SELL, then=-Coalesce(F('qty'), Value(0))),
                When(op_type=OP_USE,  then=-Coalesce(F('qty'), Value(0))),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        )
        .annotate(
            running_balance=Window(
                expression=Sum('delta'),
                order_by=[F('date_miladi').asc(), F('id').asc()],
            )
        )
    )

    txs = list(qs)

    html = render_to_string(
        "ledger/partials/item_modal_txs.html",
        {"txs": txs, "page_source": page_source},
        request=request
    )

    return JsonResponse({
        "html": html,
    })

@login_required
@ajax_debug_logger
def register_transaction(request, op_type):
    items = Item.objects.all()

    OP_LABELS = dict(OP_CHOICES)

    # فیلتر طرف حساب بر اساس نوع عملیات
    if op_type in (OP_SELL, OP_USE):
        parties = Party.objects.filter(is_customer=True)
        page_source = 'sell'
    elif op_type == OP_BUY:
        parties = Party.objects.filter(is_supplier=True)
        page_source = "buy"
    elif op_type == OP_RCV:
        parties = Party.objects.filter(is_customer=True)
        page_source = "rcv"
    elif op_type == OP_PAY:
        parties = Party.objects.filter(is_supplier=True)
        page_source = "pay"
    else:
        parties = Party.objects.all()

    if request.method == 'POST':
        form = TransactionForm(request.POST, op_type=op_type)

        is_use = request.POST.get('giftuse') in ('1', 'true', 'on')
        if is_use:
            op_type = OP_USE
            form.fields['unit_price'].required = False
            form.fields['total_price'].required = False

        if form.is_valid():
            request.dlog("✅ Form valid:", form.cleaned_data)

            # تبدیل تاریخ شمسی به میلادی
            date_shamsi = request.POST.get('date_shamsi')
            y, m, d = [int(x) for x in toEn(date_shamsi).split('/')]
            mi_date = jdatetime.date(y, m, d).togregorian()

            # تبدیل اعداد فارسی و حذف کاما
            def parse_number(val):
                if val is None:
                    return 0
                if not isinstance(val, str):
                    val = str(val)

                val = val.replace('٬', '').replace(',', '').replace('\u066C', '').strip()

                val = val.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
                val = val.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
                try:
                    return float(val)
                except:
                    return 0

            party = form.cleaned_data['party']
            total_price = Decimal(str(parse_number(form.cleaned_data['total_price'])))

            created = []
            if page_source in ("buy", "sell"):
                item = form.cleaned_data['item']


                qty = Decimal(str(parse_number(form.cleaned_data['qty'])))
                if op_type == OP_USE:
                    unit_price = Decimal("0")
                else:
                    unit_price = Decimal(str(parse_number(form.cleaned_data['unit_price'])))

                post_stock_tx(
                    date_shamsi=date_shamsi,
                    date_miladi=mi_date,
                    op_type=op_type,
                    party=party,
                    item=item,
                    qty=qty,
                    unit_price=unit_price,
                    total_price=total_price,
                    payment_method="",
                    description=form.cleaned_data.get('description'),
                )

                created.append(op_type)

            if form.cleaned_data.get('payment_amount') > 0:
                op_type2 = 'PAY' if page_source in ('buy', 'pay') else 'RCV'
                Transaction.objects.create(
                    date_shamsi=date_shamsi,
                    date_miladi=mi_date,
                    op_type=op_type2,
                    party=party,
                    item=None,
                    qty=0,
                    unit_price=0,
                    total_price=form.cleaned_data.get('payment_amount'),
                    payment_method=form.cleaned_data.get('payment_method'),
                    description=form.cleaned_data.get('description'),
                )
                created.append(op_type2)

            request.dlog("✅ operations:", created)
            return JsonResponse({
                "success": True,
                "operations": created
            })
        else:
            request.dlog("❌ Form invalid:", form.errors)
            return JsonResponse({ "success": False, "errors": form.errors })
    else:
        form = TransactionForm(op_type=op_type)

    if op_type in [OP_RCV, OP_PAY]:
        for fld in ["item", "qty", "unit_price", "total_price"]:
            if fld in form.fields:
                form.fields[fld].widget = forms.HiddenInput()

    recent_qs = Transaction.objects.order_by('-date_miladi')
    if op_type in (OP_SELL, OP_BUY):
        recent_qs = recent_qs.filter(op_type=op_type)

    context = {
        'form': form,
        'parties': parties,
        'items': items,
        'readonly_total_price': (page_source == "sell"),
        'op_type': op_type,
        'recent_transactions': recent_qs[:20],
        'page_source': page_source,
    }

    return render(request, 'ledger/transaction_form.html', context)

@login_required
def register_purchase(request):
    return register_transaction(request, OP_BUY)

@login_required
def register_sell(request):
    return register_transaction(request, OP_SELL)

@login_required
def register_payment(request):
    return register_transaction(request, OP_PAY)

@login_required
def register_receipt(request):
    return register_transaction(request, OP_RCV)

@login_required
def get_sell_price(request):
    item_id = request.GET.get('item_id')
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return JsonResponse({'sell_price': 0, 'stock': 0, 'unit': '', 'is_consignment': False})

    row = (Item.objects
           .filter(pk=item_id)
           .values('sell_price', 'unit', 'inventory__qty', 'is_consignment')  # ← unit از Item و qty از OneToOne
           .first()) or {}

    sell_price = float(row.get('sell_price') or 0)
    stock      = float(row.get('inventory__qty') or 0)
    unit       = row.get('unit') or ''
    is_consignment = row.get('is_consignment') or False

    return JsonResponse({'sell_price': sell_price, 'stock': stock, 'unit': unit, 'is_consignment': is_consignment})

@login_required
def items_list(request):
    q = (request.GET.get("q") or "").strip()
    exclude_zero = request.GET.get("exclude_zero") == "on"
    only_consignment = request.GET.get("only_consignment") == "on"

    items = (
        Item.objects
        .select_related("inventory")
        .annotate(
            value_sales=ExpressionWrapper(
                F("sell_price") * F("inventory__qty"),
                output_field=IntegerField()
            ),
            value_inventory=ExpressionWrapper(
                F("inventory__last_buy_cost") * F("inventory__qty"),
                output_field=IntegerField()
            )
        )
        .order_by("name")
    )

    if q:
        items = items.filter(name__icontains=q)

    if exclude_zero:
        items = items.filter(Q(inventory__qty__isnull=False))  # رکورد موجودی داشته باشه
        items = items.exclude(inventory__qty=0)                # ولی مقدارش صفر نباشه

    if only_consignment:
        items = items.filter(is_consignment=True)

    totals = items.aggregate(
        sum_sales=Coalesce(Sum("value_sales"), 0),
        sum_inventory=Coalesce(Sum("value_inventory"), 0),
    )

    return render(request,
        "ledger/items_list.html",
        {"items": items,
         "totals": totals,
         "q": q,
         "exclude_zero": exclude_zero,
         "only_consignment": only_consignment,
        }
    )

@login_required
def item_create(request):
    if request.method == "POST":
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            items = Item.objects.all().order_by("name")
            return JsonResponse({
                "success": True,
                "table_html": render_to_string("ledger/partials/items_table.html", {"items": items}, request=request),
                "new_option": {"value": item.id, "label": item.name}
            })
        else:
            return JsonResponse({
                "success": False,
                "errors": form.errors,
                "form_html": render_to_string("ledger/partials/item_form.html", {"form": form}, request=request)
            })
    else:
        form = ItemForm()
        return render(request, "ledger/partials/item_form.html", {"form": form})

@login_required
def parties_list(request):
    q = (request.GET.get("q") or "").strip()
    include_customers = request.GET.get("include_customers") == "on"
    include_suppliers = request.GET.get("include_suppliers") == "on"
    exclude_zero = request.GET.get("exclude_zero") == "on"

    parties = (
        Party.objects.annotate(
            total_sell=Sum(
                Case(
                    When(transactions__op_type=OP_SELL, then=F("transactions__total_price")),
                    default=0, output_field=IntegerField(),
                )
            ),
            total_rcv=Sum(
                Case(
                    When(transactions__op_type=OP_RCV, then=F("transactions__total_price")),
                    default=0, output_field=IntegerField(),
                )
            ),
            total_buy=Sum(
                Case(
                    When(transactions__op_type=OP_BUY, then=F("transactions__total_price")),
                    default=0, output_field=IntegerField(),
                )
            ),
            total_pay=Sum(
                Case(
                    When(transactions__op_type=OP_PAY, then=F("transactions__total_price")),
                    default=0, output_field=IntegerField(),
                )
            ),
        )
        .annotate(
            balance=ExpressionWrapper(
                (F("total_sell") - F("total_rcv")) - (F("total_buy") - F("total_pay")),
                output_field=IntegerField(),
            )
        ).order_by("name")
    )

    if q:
        parties = parties.filter(name__icontains=q)

    if include_customers:
        parties = parties.filter(is_customer=True)

    if include_suppliers:
        parties = parties.filter(is_supplier=True)

    if exclude_zero:
        parties = parties.exclude(balance=0)

    totals = parties.aggregate(
        sum_balance=Coalesce(Sum("balance"), 0),
    )

    return render(request,
        "ledger/parties_list.html",
        {"parties": parties,
         "totals": totals,
         "q": q,
         "include_customers": include_customers,
         "include_suppliers": include_suppliers,
         "exclude_zero": exclude_zero,
        }
    )

@login_required
def party_create(request):
    context_type = request.GET.get("context") or request.POST.get("context")
    if request.method == "POST":
        post_data = request.POST.copy()

        if not post_data.get('party_type') and context_type in ('customer', 'supplier'):
            post_data['party_type'] = context_type

        form = PartyForm(post_data, context_type=context_type)

        if form.is_valid():
            party = form.save()
            parties = Party.objects.all().order_by("name")
            return JsonResponse({
                "success": True,
                "table_html": render_to_string("ledger/partials/parties_table.html", {"parties": parties}, request=request),
                "new_option": {"value": party.id, "label": party.name}
            })
        else:
            return JsonResponse({
                "success": False,
                "errors": form.errors,
                "form_html": render_to_string("ledger/partials/party_form.html", {"form": form}, request=request)
            })
    else:
        form = PartyForm(context_type=context_type)
        return render(request, "ledger/partials/party_form.html", {"form": form})

def normalize_jdate_str(s:str)->str:
    # رقم ها انگلیسی، جداکننده ها اسلاش
    s = toEn((s or '').strip().replace('-', '/'))
    # حذف فاصله های اضافی
    s = '/'.join(part.strip() for part in s.split('/'))
    return s

@login_required
def transaction_list(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'ledger/partials/tx_rows.html', {'transactions': qs})

    from .forms import TransactionFilterForm
    params = request.GET.copy()
    form = TransactionFilterForm(params or None)

    # --- فیلترها ---
    qs = Transaction.objects.select_related('item', 'party')
    if form.is_valid():
        op_type     = form.cleaned_data.get('op_type') or ''
        party       = form.cleaned_data.get('party') or ''
        item        = form.cleaned_data.get('item') or ''
        qty         = toEn(form.cleaned_data.get('qty'), True)
        unit_price  = toEn(form.cleaned_data.get('unit_price'), True)
        total_price = toEn(form.cleaned_data.get('total_price'), True)
        cogs        = toEn(form.cleaned_data.get('cogs'), True)
        description = form.cleaned_data.get('description') or ''

        if op_type:     qs = qs.filter(op_type=op_type)
        if item:        qs = qs.filter(item=item)
        if party:       qs = qs.filter(party=party)
        if qty is not None:         qs = qs.filter(qty=qty)
        if unit_price is not None:  qs = qs.filter(unit_price=unit_price)
        if total_price is not None: qs = qs.filter(total_price=total_price)
        if cogs is not None:        qs = qs.filter(cogs=cogs)
        if description: qs = qs.filter(description__icontains=description)

        day   = toEn(form.cleaned_data.get('day_input'))
        month = toEn(form.cleaned_data.get('month_input'))
        year  = toEn(form.cleaned_data.get('year_input'))

        # 🧠 فیلتر ترکیبی تاریخ
        if year or month or day:
            # ساخت regex دینامیک
            pattern = '^'
            if year:
                pattern += str(year).zfill(4)
            else:
                pattern += r'\d{4}'  # هر سالی

            if month:
                pattern += '/' + str(month).zfill(2)
            else:
                pattern += r'/\d{2}'  # هر ماهی

            if day:
                pattern += '/' + str(day).zfill(2)
            else:
                pattern += r'/\d{2}'  # هر روزی

            qs = qs.filter(date_shamsi__regex=pattern)

    # --- Infinite scroll ---
    last_id = request.GET.get('last_id')
    limit = 50

    if last_id:
        # رکوردهای قدیمی‌تر از آخرین ردیف فعلی
        qs = qs.filter(id__lt=last_id).order_by('-date_miladi', '-id')[:limit]
    else:
        # بار اول → جدیدترین‌ها
        qs = qs.order_by('-date_miladi', '-id')[:limit]

    txs = list(qs)
    last_id = txs[-1].id if txs else None

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string("ledger/partials/tx_rows.html", {"transactions": txs, "page_source": "ALL"}, request=request)
        return JsonResponse({
            "html": html,
            "last_id": txs[-1].id if txs else None,   # قدیمی‌ترین در مجموعه فعلی
            "has_more": len(txs) == limit,
        })

    return render(request, "ledger/transaction_list.html", {
        "transactions": txs,
        "form": form,
        "transactions_last_id": last_id,
        "page_source": "ALL",
    })

@login_required
def get_party_transactions(request):
    """
    بازگرداندن جدول تراکنش‌های یک طرف حساب (خریدار/فروشنده) به‌صورت HTML (partial).
    ستون «مانده» برای هر ردیف بر اساس کل دیتاست (بدون توجه به صفحه‌بندی) محاسبه می‌شود.
    """
    party_id = request.GET.get('party')
    limit    = int(request.GET.get('limit', 20) or 20) # تعداد
    page_source   = request.GET.get('source', '')

    if not party_id:
        html = '<tr><td colspan="7" style="text-align:center;">طرف حساب انتخاب نشده است.</td></tr>'
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    # اگر بعداً فیلترهایی مثل تاریخ/نوع عملیات خواستی اضافه کنی، اینجا اعمال کن:
    base_qs = (
        Transaction.objects
        .select_related('item', 'party')
        .filter(party_id=party_id)
        .order_by('date_miladi', 'id')
        .annotate(
            delta=Case(
                When(op_type=OP_SELL, then= Coalesce(F('total_price'), Value(0))),
                When(op_type=OP_RCV,  then=-Coalesce(F('total_price'), Value(0))),
                When(op_type=OP_BUY,  then=-Coalesce(F('total_price'), Value(0))),
                When(op_type=OP_PAY,  then= Coalesce(F('total_price'), Value(0))),
                When(op_type=OP_USE,  then= Coalesce(F('total_price'), Value(0))),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        )
        .annotate(
            running_balance=Window(
                expression=Sum('delta'),
                order_by=[F('date_miladi').asc(), F('id').asc()],
            )
        )
    )

    if page_source == 'buy':
        base_qs = base_qs.annotate(
            running_balance=-(Coalesce(F('running_balance'), Value(0)))
        )

    total_count = base_qs.count()
    if total_count == 0:
        html = '<tr><td colspan="7" class="text-center">رکوردی یافت نشد</td></tr>'
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    start_index = max(0, total_count - limit)
    page_qs = base_qs[start_index:total_count]  # برش صفحه بعد از محاسبه مانده

    html = render_to_string('ledger/partials/party_modal_rows.html', {'txs': page_qs, 'page_source': page_source}, request=request)
    return HttpResponse(html, content_type='text/html; charset=utf-8')

@login_required
def get_item_transactions(request):
    """جدول تراکنش‌های یک کالا (برای مودال کالا)."""
    item_id = request.GET.get('item')
    limit = int(request.GET.get('limit', 20) or 20)
    if not item_id:
        html = '<tr><td colspan="6" style="text-align:center;">کالا انتخاب نشده است.</td></tr>'
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    base_qs = (
        Transaction.objects
        .select_related('item', 'party')
        .filter(
            item_id=item_id,
            op_type__in = (OP_SELL, OP_BUY, OP_USE)
        )
        .order_by('date_miladi', 'id')
        .annotate(
            delta=Case(
                When(op_type=OP_SELL, then=-Coalesce(F('qty'), Value(0))),
                When(op_type=OP_BUY,  then= Coalesce(F('qty'), Value(0))),
                When(op_type=OP_USE,  then=-Coalesce(F('qty'), Value(0))),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        )
        .annotate(
            running_balance=Window(
                expression=Sum('delta'),
                order_by=[F('date_miladi').asc(), F('id').asc()],
            )
        )
    )

    total_count = base_qs.count()
    if total_count == 0:
        html = '<tr><td colspan="6" class="text-center">رکوردی یافت نشد</td></tr>'
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    start_index = max(0, total_count - limit)
    page_qs = base_qs[start_index:total_count]  # برش صفحه بعد از محاسبه مانده

    html = render_to_string('ledger/partials/item_modal_rows.html', {'txs': page_qs}, request=request)
    return HttpResponse(html, content_type='text/html; charset=utf-8')

@login_required
def get_recent_transactions(request):
    op_type = request.GET.get("op_type")
    last_id = request.GET.get("last_id")

    limit = int(request.GET.get("limit", 50))
    qs = Transaction.objects.select_related("item", "party")

    if op_type:
        if op_type == OP_SELL:
            qs = qs.filter(Q(op_type=OP_SELL) | Q(op_type=OP_USE))
        else:
            qs = qs.filter(op_type=op_type)

    if last_id:
        qs = qs.filter(id__lt=last_id)

    qs = qs.order_by("-date_miladi", "-id")[:limit]

    txs = list(qs)  # ترتیب نزولی (جدیدترین → قدیمی‌تر)

    if not txs:
        html = '<tr><td colspan="7" class="text-center">هیچ تراکنشی یافت نشد</td></tr>'
    else:
        if op_type in (OP_BUY, OP_SELL, OP_USE):
            page_source = "BUYSELL"
        else:
            page_source = "PAYRCV"

        html = render_to_string("ledger/partials/tx_rows.html", {"transactions": txs, "page_source": page_source}, request=request)
        html += f'<input type="hidden" class="last-id" value="{txs[-1].id}" data-hasmore="false">'
    return HttpResponse(html, content_type="text/html; charset=utf-8")

def customer_balance_report(request):
    q = (request.GET.get("q") or "").strip()
    exclude_zero = request.GET.get("exclude_zero") == "on"

    int0 = Value(0, output_field=IntegerField())

    base = (
        Transaction.objects
        .values("party_id", party_name=F("party__name"))
        .annotate(
            total_purchase=Coalesce(
                Sum(
                    Case(
                        When(op_type = OP_SELL, then=F("total_price")),
                        default=int0,
                        output_field=IntegerField(),
                    ),
                    output_field=IntegerField(),
                ),
                int0,
                output_field=IntegerField(),
            ),
            total_payment=Coalesce(
                Sum(
                    Case(
                        When(op_type = OP_RCV, then=F("total_price")),
                        default=int0,
                        output_field=IntegerField(),
                    ),
                    output_field=IntegerField(),
                ),
                int0,
                output_field=IntegerField(),
            ),
        )
        .annotate(
            balance=ExpressionWrapper(
                F("total_purchase") - F("total_payment"),
                output_field=IntegerField(),
            )
        )
    )

    if q:
        base = base.filter(party__name__icontains=q)

    if exclude_zero:
        base = base.filter(~Q(balance=0))

    # ترتیب نمایش
    rows_qs = base.order_by("-balance", "party__name")

    # ردیف‌های قابل‌نمایش را به لیست تبدیل کن
    rows = list(rows_qs)

    # جمع مانده‌ها روی همین rows (دقیقاً همان چیزی که کاربر می‌بیند)
    sum_balance = sum((r.get("balance") or 0) for r in rows)

    totals = {
        # اگر بعداً لازم شد این دو را هم می‌توانی اضافه کنی
        # "sum_purchase": sum((r.get("total_purchase") or 0) for r in rows),
        # "sum_payment":  sum((r.get("total_payment")  or 0) for r in rows),
        "sum_balance":  sum_balance,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # فقط جدول رو برگردون
        html = render_to_string("reports/partials/customer_balance_table.html", {
            "rows": rows, "totals": totals
        })
        return JsonResponse({"html": html})

    context = {
        "rows": rows,
        "totals": totals,
        "q": q,
        "exclude_zero": exclude_zero,
    }
    return render(request, "reports/customer_balance_report.html", context)

def monthly_sales(request):
    monthly_sales = (
        Transaction.objects
        .filter(op_type__in=[OP_SELL, OP_USE])  # فقط فروش
        .annotate(
            year =Cast(Substr("date_shamsi", 1, 4), IntegerField()),
            month=Cast(Substr("date_shamsi", 6, 2), IntegerField()),
            day  =Cast(Substr("date_shamsi", 9, 2), IntegerField()),
        )
        .values("year", "month")
        .annotate(
            total_sales    =Coalesce(Sum("total_price"), Value(0)),
            total_cogs     =Coalesce(Sum("cogs"), Value(0)),
            days_with_sales=Count("day", distinct=True),  # تعداد روزهای فروش در ماه
        )
        .annotate(
            profit=F("total_sales") - F("total_cogs"),
            profit_percent=ExpressionWrapper(100.0 * F("profit") / F("total_sales"), output_field=FloatField(),)
        )
        .order_by("-year", "-month")
    )

    sum_sales = sum_profit = sum_days = max_sales = 0
    for r in monthly_sales:
        r["month_name"] = PERSIAN_MONTHS.get(r["month"], "-")
        sum_sales += r["total_sales"]
        sum_profit += r["profit"]
        sum_days += r["days_with_sales"]
        if r["total_sales"] > max_sales:
            max_sales = r["total_sales"]

    totals = {
        "sum_sales": sum_sales,
        "sum_profit": sum_profit,
        "sum_days": sum_days,
        "profit_percent": (sum_profit / sum_sales * 100.0) if sum_sales else 0.0
    }

    context = {"monthly_sales": monthly_sales, "totals": totals, "max_sales": max_sales}
    return render(request, "ledger/monthly_sales.html", context)

def daily_sales(request, year, month):
    # محاسبات روزانه

    start_day = JalaliDate(year, month, 1).to_gregorian()
    if month == 12:
        end_day = JalaliDate(year + 1, 1, 1).to_gregorian()
    else:
        end_day = JalaliDate(year, month + 1, 1).to_gregorian()

    qs = (
        Transaction.objects
        .filter(
            date_miladi__gte=start_day,
            date_miladi__lt=end_day,
            op_type__in=[OP_SELL, OP_USE])
        .annotate(day=Cast(Substr("date_shamsi", 9, 2), IntegerField()))
        .values("day")
        .annotate(
            total_sales =Coalesce(Sum("total_price"), Value(0)),
            total_cogs  =Coalesce(Sum("cogs"), Value(0)),
        )
        .annotate(
            profit=F("total_sales") - F("total_cogs"),
            profit_percent=ExpressionWrapper(100.0 * F("profit") / F("total_sales"), output_field=FloatField(),)
        )
        .order_by("date_shamsi")
    )

    qs_map = {}
    for row in qs:
        qs_map[row["day"]] = row

    # تعداد روزهای ماه شمسی
    num_days = (end_day - start_day).days

    # لیست همه روزها
    daily_sales = []
    for d in range(1, num_days + 1):
        row = qs_map.get(d, {
            "day": d,
            "total_sales": 0,
            "total_cogs": 0,
            "profit": 0,
            "profit_percent": 0,
        })
        daily_sales.append(row)

    sum_sales  = sum(item["total_sales"] for item in daily_sales)
    sum_profit = sum(item["profit"] for item in daily_sales)
    totals = {
        "sum_sales": sum_sales,
        "sum_profit": sum_profit,
        "profit_percent": (sum_profit / sum_sales * 100.0) if sum_sales else 0.0
    }

    max_sales = max([r["total_sales"] for r in daily_sales], default=0)

    return render(request, "ledger/partials/daily_sales.html", {"daily_sales": daily_sales, "totals": totals, "max_sales": max_sales})

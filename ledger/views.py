from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Item, Party, Transaction, Inventory, OP_SELL, OP_BUY, OP_USE, OP_RCV, OP_PAY, OP_CHOICES, PERSIAN_MONTHS
from .forms import TransactionForm, ItemForm
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

def fa_to_en(s):
    return s.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))

def en_to_fa(s):
    return s.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

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
            # تبدیل تاریخ شمسی به میلادی
            date_shamsi = form.cleaned_data['date_shamsi']
            y, m, d = [int(x) for x in fa_to_en(date_shamsi).split('/')]
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
                messages.success(request, f'{OP_LABELS.get(op_type, op_type)} با موفقیت ثبت شد.')

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
                messages.success(request, f'{OP_LABELS.get(op_type2, op_type2)} با موفقیت ثبت شد.')

            if page_source == "buy":
                return redirect('register_purchase')
            elif page_source == "sell":
                return redirect('register_sell')
            elif page_source == "pay":
                return redirect('register_payment')
            elif page_source == "rcv":
                return redirect('register_receipt')
        else:
            messages.error(request, form.errors)
    else:
        form = TransactionForm(op_type=op_type)

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


def items_list(request):
    items = Item.objects.all().order_by("name")
    return render(request, "ledger/items_list.html", {"items": items})

def item_create(request):
    if request.method == "POST":
        form = ItemForm(request.POST)
        if form.is_valid():
            form.save()
            items = Item.objects.all().order_by("name")
            return JsonResponse({
                "success": True,
                "table_html": render_to_string("ledger/partials/items_table.html", {"items": items}, request=request)
            })
        else:
            return JsonResponse({
                "success": False,
                "form_html": render_to_string("ledger/partials/item_form.html", {"form": form}, request=request)
            })
    else:
        form = ItemForm()
        return render(request, "ledger/partials/item_form.html", {"form": form})




@login_required
def register_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            it = Item.objects.create(
                name=cd["name"],
                unit=cd["unit"],
                sell_price=cd["sell_price"],
                group=cd["group"],
                is_consignment=cd["is_consignment"],
                commission_amount=cd["commission_amount"],
                commission_percent=cd["commission_percent"],
            )

            # اطمینان از وجود موجودی (OneToOne)
            Inventory.objects.get_or_create(item=it, defaults={'qty': Decimal('0')})

            messages.success(request, 'کالا ثبت شد.')
            return redirect('register_item')
        else:
            messages.error(request, f'خطا در فرم: {form.errors}')
    else:
        form = ItemForm()

    recent_items = Item.objects.select_related('inventory').order_by('-id')   #[:20]

    return render(request, 'ledger/register_item.html', {
        'form': form,
        'recent_items': recent_items,
    })

@login_required
def register_party(request):
    if request.method == 'POST':
        name = request.POST.get('name')

        def _parse_role(value: str):
            s = (value or "").strip().lower()
            if s in ("supplier", "فروشنده"):
                return False, True           # is_customer, is_supplier
            if s in ("both", "هردو"):
                return True, True
            return True, False               # پیش‌فرض: مشتری

        role_str = request.POST.get("role")
        is_customer, is_supplier = _parse_role(role_str)

        if name:
            Party.objects.create(
                name=name,
                is_customer=is_customer,
                is_supplier=is_supplier,
            )
            messages.success(request, "طرف حساب ثبت شد.")
            return redirect('register_party')

    # 🔧 این قسمت فیلتر سریع
    role = request.GET.get("role")
    qs = Party.objects.all()
    if role == "cust":
        qs = qs.filter(is_customer=True, is_supplier=False)
    elif role == "supp":
        qs = qs.filter(is_customer=False, is_supplier=True)
    elif role == "both":
        qs = qs.filter(is_customer=True, is_supplier=True)

    recent_parties = qs.order_by('-id')[:20]

    return render(request, 'ledger/register_party.html', {
        'recent_parties': recent_parties
    })

def normalize_jdate_str(s:str)->str:
    # رقم ها انگلیسی، جداکننده ها اسلاش
    s = fa_to_en((s or '').strip().replace('-', '/'))
    # حذف فاصله های اضافی
    s = '/'.join(part.strip() for part in s.split('/'))
    return s

@login_required
def transaction_list(request):
    from .forms import TransactionFilterForm
    params = request.GET.copy()
    form = TransactionFilterForm(params or None)

    # تاریخ ورودی (ممکن است خالی باشد)
    raw_date = params.get('date_shamsi', '')
    norm_date = normalize_jdate_str(raw_date)

    # اگر کاربر دکمه روز قبل/بعد زد ولی تاریخ خالی بود، مبنا را امروز بگذار
    if params.get('shift') and not norm_date:
        norm_date = jdatetime.date.today().strftime('%Y/%m/%d')

    # پردازش شیفت
    shift = params.get('shift')
    if shift and norm_date:
        try:
            y, m, d = [int(x) for x in norm_date.split('/')]
            jdate = jdatetime.date(y, m, d) + timedelta(days=(-1 if shift == 'prev' else 1))
            params['date_shamsi'] = en_to_fa(jdate.strftime('%Y/%m/%d'))
            params.pop('shift', None)
            return HttpResponseRedirect(reverse('transaction_list') + '?' + urlencode(params, doseq=True))
        except Exception:
            params.pop('shift', None)
            return HttpResponseRedirect(reverse('transaction_list') + ('?' + urlencode(params, doseq=True) if params else ''))

    # Query پایه
    qs = Transaction.objects.select_related('item', 'party').order_by('date_miladi', 'id')

    # اعمال فیلترهای دیگر
    if form.is_valid():
        op_type = form.cleaned_data.get('op_type') or ''
        party   = form.cleaned_data.get('party') or ''
        item    = form.cleaned_data.get('item') or ''
        qty     = form.cleaned_data.get('qty') or 0

        if op_type: qs = qs.filter(op_type=op_type)
        if item:    qs = qs.filter(item=item)
        if party:   qs = qs.filter(party=party)
        if qty > 0: qs = qs.filter(qty=qty)

    if norm_date:
        try:
            y, m, d = [int(x) for x in norm_date.split('/')]
            mi_date = jdatetime.date(y, m, d).togregorian()
            qs = qs.filter(date_miladi=mi_date)
        except Exception:
            # اگر تاریخ خراب بود، فیلتر تاریخ را نادیده بگیر (تا حداقل خروجی ببینی)
            pass

    # 🔹 آخرین id یا offset
    last_id = request.GET.get('last_id')
    limit = 50

    if last_id:
        # وقتی اسکرول بالا رفت → رکوردهای قدیمی‌تر از last_id
        qs = qs.filter(id__lt=last_id).order_by('-date_miladi', '-id')[:limit]
    else:
        # بار اول → آخرین ۵۰ رکورد
        qs = qs.order_by('-date_miladi', '-id')[:limit]

    # 🔹 مرتب‌سازی نهایی صعودی برای نمایش
    txs = list(qs)[::-1]

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string("ledger/partials/tx_rows.html", {"transactions": txs}, request=request)
        return JsonResponse({
            "html": html,
            "last_id": txs[0].id if txs else None,   # قدیمی‌ترین رکوردی که لود شده
            "has_more": len(txs) == limit,           # اگه کمتر از limit بود یعنی دیگه تموم شد
        })

    return render(request, "ledger/transaction_list.html", {
        "transactions": txs,
        "form": form,
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
    limit = 50
    op_type = request.GET.get("op_type")
    last_id = request.GET.get("last_id")

    qs = Transaction.objects.select_related("item", "party").order_by("-date_miladi", "-id")

    if op_type:
        qs = qs.filter(op_type=op_type)

    if last_id:
        qs = qs.filter(id__lt=last_id)

    qs = qs[:limit]
    txs = list(qs)  # ترتیب نزولی (جدیدترین → قدیمی‌تر)

    if not txs:
        html = '<tr><td colspan="7" class="text-center">هیچ تراکنشی یافت نشد</td></tr>'
    else:
        html = render_to_string("ledger/partials/tx_rows.html", {"transactions": txs}, request=request)
        html += f'<input type="hidden" class="last-id" value="{txs[-1].id}" data-hasmore="{str(len(txs)==limit).lower()}">'

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

    context = {
        "rows": rows,
        "q": q,
        "exclude_zero": exclude_zero,
        "totals": totals,
    }
    return render(request, "reports/customer_balance_report.html", context)

def monthly_sales(request):
    monthly_sales = (
        Transaction.objects
        .filter(op_type="SELL")  # فقط فروش
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
        .order_by("year", "month")
    )

    for r in monthly_sales:
        r["month_name"] = PERSIAN_MONTHS.get(r["month"], "-")

    context = {"monthly_sales": monthly_sales}
    return render(request, "ledger/monthly_sales.html", context)

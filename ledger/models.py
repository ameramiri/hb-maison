from django.db import models
from django.db.models import Q

# --- ثابت‌ها (کنار مدل‌ها) ---
OP_SELL = "SELL"
OP_BUY  = "BUY"
OP_RCV  = "RCV"
OP_PAY  = "PAY"
OP_USE  = "USE"

OP_CHOICES = [
    (OP_SELL, "فروش"),
    (OP_BUY,  "خرید"),
    (OP_RCV,  "دریافت"),
    (OP_PAY,  "پرداخت"),
    (OP_USE,  "استفاده/هدیه"),
]

# ماه‌های شمسی
PERSIAN_MONTHS = {
    1: "فروردین", 2: "اردیبهشت", 3: "خرداد",
    4: "تیر", 5: "مرداد", 6: "شهریور",
    7: "مهر", 8: "آبان", 9: "آذر",
    10: "دی", 11: "بهمن", 12: "اسفند"
}

class PaymentMethod(models.TextChoices):
    POS2 = "POS2", "کارت خوان جدید"
    ACC3 = "ACC3", "حساب بلو"
    CASH = "CASH", "نقدی"
    POS1 = "POS1", "کارت خوان قدیم"
    ACC2 = "ACC2", "حساب 5802"
    ACC1 = "ACC1", "حساب 1901"
    HEN1 = "HEN1", "کارت هنگامه"
    HEN2 = "HEN2", "حساب هستی"

# --- QuerySet/Manager تمیز ---
class TransactionQuerySet(models.QuerySet):
    def sales(self):     return self.filter(op_type=OP_SELL)
    def purchases(self): return self.filter(op_type=OP_BUY)
    def receipts(self):  return self.filter(op_type=OP_RCV)
    def payments(self):  return self.filter(op_type=OP_PAY)
    def ownuse(self):    return self.filter(op_type=OP_USE)

class TransactionManager(models.Manager):
    def get_queryset(self): return TransactionQuerySet(self.model, using=self._db)
    def sales(self):     return self.get_queryset().sales()
    def purchases(self): return self.get_queryset().purchases()
    def receipts(self):  return self.get_queryset().receipts()
    def payments(self):  return self.get_queryset().payments()

# --- خود مدل Transaction (فقط قسمت‌های لازم را نشان می‌دهم) ---
class Transaction(models.Model):
    # مثال: party = models.ForeignKey(Party, on_delete=models.PROTECT)
    # مثال: item  = models.ForeignKey(Item,  on_delete=models.PROTECT, null=True, blank=True)
    # ↓↓↓ مهم: فیلدهای زیر را مطابق پروژه خودت اصلاح کن ↓↓↓

    op_type     = models.CharField(max_length=15, choices=OP_CHOICES)
    date_miladi = models.DateField(null=True, blank=True)
    date_shamsi = models.CharField(max_length=10, null=True, blank=True)

    party = models.ForeignKey(
        'Party',
        on_delete=models.SET_NULL,    # موقّت: به NULL ست شود
        related_name='transactions',
        null=True, blank=True,
        db_constraint=False           # موقّت: بررسی FK را غیرفعال کن
    )
    item        = models.ForeignKey('Item', on_delete=models.PROTECT, null=True, blank=True)
    qty         = models.IntegerField(null=True, blank=True)
    unit_price  = models.IntegerField(null=True, blank=True)
    total_price = models.IntegerField()

    cogs           = models.IntegerField(null=True, blank=True)
    is_cogs_temp   = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.POS2, null=True, blank=True,)
    description    = models.CharField(max_length=50, null=True, blank=True)

    objects = TransactionManager()

    class Meta:
        indexes = [
            models.Index(fields=["party", "op_type"]),
            models.Index(fields=["date_miladi"]),
        ]

    def __str__(self):
        return f"{self.op_type} - {getattr(self, 'party', None)} - {self.total_price}"

    @property
    def gross_profit(self):
        # حاشیه سود ناخالص (اگر cogs موجود باشد)
        if self.cogs is None:
            return None
        return (self.total_price or 0) - self.cogs

    @property
    def op_label(self) -> str:
        return self.get_op_type_display()

    # آیا این تراکنش «تعداد» دارد؟ (برای خرید/فروش/استفاده)
    @property
    def is_qty_based(self) -> bool:
        return self.op_type in (OP_BUY, OP_SELL, OP_USE)

    @property
    def is_purchase_tx(self) -> bool:
        return self.op_type in (OP_BUY)

    # کلاس بجِ نمایشی براساس نوع عملیات (برای رنگ/استایل)
    @property
    def op_badge_class(self) -> str:
        mapping = {
            OP_BUY:  "badge-op-buy",
            OP_SELL: "badge-op-sell",
            OP_RCV:  "badge-op-receipt",
            OP_PAY:  "badge-op-payment",
            OP_USE:  "badge-op-sell",  # اگر کلاس جدا می‌خواهی، یکی بساز
        }
        return mapping.get(self.op_type, "")

class OpType(models.TextChoices):
    ALL  = "", "همه"
    BUY  = "BUY", "خرید"
    SELL = "SELL", "فروش"
    RCV  = "RCV", "دریافت"
    PAY  = "PAY", "پرداخت"
    USE  = "USE", "استفاده/هدیه"

class PartyQuerySet(models.QuerySet):
    def customers(self): return self.filter(is_customer=True)
    def suppliers(self): return self.filter(is_supplier=True)

class PartyManager(models.Manager):
    def get_queryset(self): return PartyQuerySet(self.model, using=self._db)
    def customers(self): return self.get_queryset().customers()
    def suppliers(self): return self.get_queryset().suppliers()

class Party(models.Model):
    name = models.CharField(max_length=50)
    # ✅ دو بولین به‌جای role:
    is_customer = models.BooleanField(default=False, verbose_name="مشتری")   # ← جدید
    is_supplier = models.BooleanField(default=False, verbose_name="فروشنده") # ← جدید

    objects = PartyManager()

    class Meta:
        verbose_name = "طرف حساب"
        verbose_name_plural = "طرف حساب‌ها"
        indexes = [
            models.Index(fields=["name"]),
        ]
        # ✅ حداقل یکی از نقش‌ها باید True باشد
        constraints = [
            models.CheckConstraint(
                check=Q(is_customer=True) | Q(is_supplier=True),
                name="party_at_least_one_role"
            )
        ]

    def __str__(self):
        return self.name

    @property
    def role_display(self):
        if self.is_customer and self.is_supplier:
            return "هردو"
        if self.is_customer:
            return "مشتری"
        if self.is_supplier:
            return "فروشنده"
        return "—"  # نباید رخ بدهد چون کانسترینت داریم

class ItemGroup(models.TextChoices):
    FORMAL    = "formal",    "لباس مجلسی"
    SPORT     = "sport",     "لباس اسپرت"
    SHOES     = "shoes",     "کفش"
    BAG       = "bag",       "کیف"
    ACCESSORY = "accessory", "اکسسوری"
    SWIM      = "swim",      "مایو"
    UNDERWEAR = "underwear", "لباس زیر"

class Item(models.Model):
    name       = models.CharField(max_length=255)
    unit       = models.CharField(max_length=50, blank=True, null=True)
    sell_price = models.IntegerField(null=True, blank=True)
    group      = models.CharField(max_length=100, choices=ItemGroup.choices, blank=True, null=True)

    is_consignment     = models.BooleanField(default=False)
    commission_amount  = models.PositiveIntegerField(null=True, blank=True)                          # اگر مشارکتی ثابت باشد
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # اگر مشارکتی درصدی باشد

    class Meta:
        verbose_name = "کالا"
        verbose_name_plural = "کالاها"
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name

    @property
    def settlement_type(self):
        """برای راحتی در گزارش‌گیری"""
        if self.is_consignment:
            if self.commission_amount is not None and self.commission_amount > 0:       #کمیسیون عدد ثابت
                return "COMM_AMOUNT"
            elif self.commission_percent is not None and self.commission_percent > 0:   #کمیسیون درصد از فروش
                return "COMM_PERCENT"
            return "CONS_NO_COMMISSION"   # امانی بدون کمیسیون
        return "FIXED_PURCHASE"

class Inventory(models.Model):
    # اگر قبلاً ForeignKey بوده، الان OneToOne کن
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name="inventory")
    qty = models.DecimalField(max_digits=18, decimal_places=0, default=0)
    last_buy_cost = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="آخرین قیمت خرید")

    def __str__(self):
        return f"{self.item} — {self.qty}"

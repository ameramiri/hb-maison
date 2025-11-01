from decimal import Decimal, InvalidOperation
from django import forms
from .models import Item, Party, PaymentMethod, OpType, OP_SELL, OP_BUY, OP_RCV, OP_PAY, OP_USE, ItemGroup
import jdatetime
from .utils import toFa

_digit_map = str.maketrans({
    "۰":"0","۱":"1","۲":"2","۳":"3","۴":"4","۵":"5","۶":"6","۷":"7","۸":"8","۹":"9",
    "٠":"0","١":"1","٢":"2","٣":"3","٤":"4","٥":"5","٦":"6","٧":"7","٨":"8","٩":"9",
})

def _normalize_number(value, allow_decimal=False):
    if value is None:
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    s = str(value).strip().translate(_digit_map)
    s = (s
         .replace("٬", "")   # U+066C Arabic thousands
         .replace(",", "")   # western thousands
         .replace("\u200c", "")  # ZWNJ
         .replace("\xa0", "")    # NBSP
         .replace(" ", ""))
    s = s.replace("٫", ".")  # U+066B Arabic decimal
    if s == "":
        s = "0"
    try:
        if allow_decimal:
            return Decimal(s)
        return int(Decimal(s))
    except InvalidOperation:
        raise forms.ValidationError("مقدار عددی نامعتبر است.")

class TransactionForm(forms.Form):
    # تاریخ (مخفی و نمایشی)
    date_shamsi = forms.CharField(
        label="تاریخ",
        required=True,
        widget=forms.TextInput(attrs={
            "id": "id_date_shamsi",
            "type": "hidden",
        })
    )
    date_shamsi_display = forms.CharField(
        label="تاریخ",
        required=True,
        widget=forms.TextInput(attrs={
            "id": "id_date_shamsi_display",
            "placeholder": "مثلاً ۱۴۰۴/۰۵/۲۰",
            "class": "field-sm",
        })
    )

    # استفاده خودم/هدیه
    giftuse = forms.BooleanField(
        label="استفاده/هدیه",
        required=False,
        widget=forms.CheckboxInput(attrs={
            "id": "giftuse",
            "style": "cursor:pointer;",
            "class": "field-sm",
        })
    )

    # طرف حساب
    party = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        label="طرف حساب",
        widget=forms.Select(attrs={
            "class": "select2 field-md",
            "id": "party",
            "required": "required",
        })
    )

    # کالا
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        label="کالا",
        widget=forms.Select(attrs={
            "class": "select2 field-md",
            "id": "item",
            "required": "required",
        })
    )

    # تعداد (کوچک)
    qty = forms.CharField(
        label="تعداد",
        required=True,
        widget=forms.TextInput(attrs={
            "id": "qty",
            "placeholder": "تعداد",
            "class": "field-sm",
            "data-maxint": "4", "inputmode": "numeric"
        })
    )

    # قیمت واحد (کوچک)
    unit_price = forms.CharField(
        label="قیمت واحد",
        required=True,
        widget=forms.TextInput(attrs={
            "id": "unit_price",
            "placeholder": "قیمت واحد",
            "class": "field-sm",
            "inputmode": "numeric"
        })
    )

    # قیمت کل (بزرگ‌تر)
    total_price = forms.CharField(
        label="قیمت کل",
        required=True,
        widget=forms.TextInput(attrs={
            "id": "total_price",
            "placeholder": "قیمت کل",
            "class": "field-lg",
            "inputmode": "numeric"
        })
    )

    # مبلغ پرداخت
    payment_amount = forms.CharField(
        label="پرداخت",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "digit-input",
            "id": "payment_amount",
            "placeholder": "مبلغ",
            "class": "field-sm",
            "inputmode": "numeric"
        })
    )

    # روش پرداخت
    payment_method = forms.ChoiceField(
        label="پرداخت",
        choices=PaymentMethod.choices,
        required=False,
        widget=forms.Select(attrs={
            "class": "select2 field-md",
            "id": "payment_method",
            "placeholder":"انتخاب روش پرداخت",
        })
    )

    # توضیحات
    description = forms.CharField(
        label="توضیحات",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "class": "field-lg",
            "style": "height:50px;",
        })
    )

    def __init__(self, *args, op_type=None, **kwargs):
        self.op_type = op_type
        super().__init__(*args, **kwargs)

        self.fields['date_shamsi_display'].initial = jdatetime.date.today().strftime('%Y/%m/%d')

        self.fields["payment_method"].initial = PaymentMethod.POS2

        qs_party = Party.objects.all().order_by("name")
        qs_item = Item.objects.all().order_by("name")

        # فیلتر طرف حساب
        if op_type in (OP_SELL, OP_RCV, OP_USE):
            qs_party = qs_party.filter(is_customer=True)
            self.fields["party"].label = "مشتری:"
            self.fields["total_price"].widget.attrs["readonly"] = True
            self.fields["payment_amount"].label = "دریافت"
        elif op_type in (OP_BUY, OP_PAY):
            qs_party = qs_party.filter(is_supplier=True)
            self.fields["party"].label = "فروشنده:"
            self.fields["total_price"].widget.attrs["readonly"] = False
            self.fields["payment_amount"].label = "پرداخت"

        self.fields["party"].queryset = qs_party
        self.fields["item"].queryset = qs_item

        # دریافت/پرداخت → این فیلدها لازم نیستند
        if op_type in (OP_RCV, OP_PAY):
            for fname in ("item", "qty", "unit_price", "total_price"):
                if fname in self.fields:
                    self.fields[fname].required = False

        # تاریخ پیش‌فرض
        self.fields["date_shamsi"].initial = jdatetime.date.today().strftime("%Y/%m/%d")

    # Validation ها
    def clean_qty(self):
        return _normalize_number(self.cleaned_data.get("qty"))

    def clean_unit_price(self):
        return _normalize_number(self.cleaned_data.get("unit_price"))

    def clean_total_price(self):
        return _normalize_number(self.cleaned_data.get("total_price"))

    def clean_payment_amount(self):
        return _normalize_number(self.cleaned_data.get("payment_amount"))

    def clean(self):
        cleaned = super().clean()
        op = self.op_type or cleaned.get("op_type")

        i = cleaned.get("item")
        q = cleaned.get("qty")
        u = cleaned.get("unit_price")
        t = cleaned.get("total_price")

        if op in (OP_SELL, OP_BUY, OP_USE):
            if not i:
                self.add_error("item", "انتخاب کالا الزامی است.")
            if q is None or q <= 0:
                self.add_error("qty", "تعداد باید بزرگتر از صفر باشد.")
            if u is None or u < 0:
                self.add_error("unit_price", "قیمت واحد نباید منفی باشد.")
            if t is None or t < 0:
                self.add_error("total_price", "قیمت کل نباید منفی باشد.")
        elif op in (OP_RCV, OP_PAY):
            if t is None or t < 0:
                self.add_error("total_price", "مبلغ نباید منفی باشد.")

        if op in (OP_SELL, OP_USE) and q and u:
            cleaned["total_price"] = (Decimal(q) * u).quantize(Decimal("1"))
        elif op == OP_BUY and q and t:
            if q > 0:
                cleaned["unit_price"] = (t / Decimal(q)).quantize(Decimal("1"))

        return cleaned

class TransactionFilterForm(forms.Form):
    # تاریخ - روز/ماه/سال
    day_input   = forms.CharField(required=False, widget=forms.TextInput(attrs={'data-maxint': '2', 'inputmode': 'numeric'}))
    month_input = forms.CharField(required=False, widget=forms.TextInput(attrs={'data-maxint': '2', 'inputmode': 'numeric'}))
    year_input  = forms.CharField(required=False, widget=forms.TextInput(attrs={'data-maxint': '4', 'inputmode': 'numeric'}))

    op_type = forms.ChoiceField(choices=OpType.choices, required=False, widget=forms.Select(attrs={"class": "select", "size": 6}))
    item    = forms.ModelChoiceField(queryset=Item.objects.none(), required=False)
    party   = forms.ModelChoiceField(queryset=Party.objects.none(), required=False)

    qty          = forms.CharField(required=False, widget=forms.TextInput(attrs={"data-maxint": "4", 'inputmode': 'numeric'}))
    unit_price   = forms.CharField(required=False)
    total_price  = forms.CharField(required=False)
    cogs         = forms.CharField(required=False)
    description  = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['item'].queryset  = Item.objects.all().order_by('name')
        self.fields['party'].queryset = Party.objects.all().order_by('name')
        self.fields['party'].empty_label = 'همه'
        self.fields['item'].empty_label = 'همه'

class ItemForm(forms.ModelForm):
    sell_price = forms.CharField(
        label="قیمت فروش",
        required=True,
        widget=forms.TextInput(attrs={
            "id": "sell_price",
            "placeholder": "قیمت فروش",
            "style": "width:85px; display:inline-block;",
            "inputmode": "numeric"
        })
    )
    commission_amount = forms.CharField(
        label="سهم از فروش",
        required=False,
        widget=forms.TextInput(attrs={
            "id": "commission_amount",
            "placeholder": "مبلغ",
            "style": "width:85px; display:inline-block;",
            "inputmode": "numeric"
        })
    )
    commission_percent = forms.CharField(
        label="سهم از فروش",
        required=False,
        widget=forms.TextInput(attrs={
            "id": "commission_percent",
            "placeholder": "درصد",
            "style": "width:50px; display:inline-block;",
            "data-maxint": "3", "data-decimals": "2", "inputmode": "numeric"
        })
    )

    class Meta:
        model = Item
        fields = [
            "name",
            "unit",
            "sell_price",
            "group",
            "is_consignment",
            "commission_amount",
            "commission_percent",
        ]

        labels = {
            "name": "نام کالا",
            "unit": "واحد",
            "group": "گروه کالا",
            "is_consignment": "کالای امانی؟",
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "نام کالا",
                "style": "width:215px;",
            }),
            "unit": forms.TextInput(attrs={
                "id": "unit",
                "placeholder": "واحد اندازه گیری",
                "style": "width:215px;",
            }),
            "group": forms.Select(attrs={
                "id": "group",
                "style": "width:237px; height:28px; padding:0 8px;",
            }),
            "is_consignment": forms.CheckboxInput(attrs={
                "id": "is_consignment",
            }),
        }

    def clean_sell_price(self):
        return _normalize_number(self.cleaned_data.get("sell_price"))

    def clean_commission_amount(self):
        return _normalize_number(self.cleaned_data.get("commission_amount"))

    def clean_commission_percent(self):
        return _normalize_number(self.cleaned_data.get("commission_percent"), allow_decimal=True)

    def clean(self):
        cleaned_data = super().clean()
        commission_amount = cleaned_data.get("commission_amount")
        commission_percent = cleaned_data.get("commission_percent")

        if commission_amount and commission_percent:
            raise forms.ValidationError("فقط یکی از فیلدهای مبلغ ثابت یا درصد باید پر شود، نه هر دو.")

        if commission_percent and (commission_percent <= 0 or commission_percent > 100):
            self.add_error("commission_percent", "درصد باید بین ۰ و ۱۰۰ باشد.")

        return cleaned_data

class PartyForm(forms.ModelForm):
    PARTY_TYPE_CHOICES = [
        ('customer', 'مشتری'),
        ('supplier', 'فروشنده'),
    ]

    party_type = forms.ChoiceField(
        label='نوع طرف حساب',
        choices=PARTY_TYPE_CHOICES,
        widget=forms.Select(attrs={'id': 'id_party_type'})
    )

    class Meta:
        model = Party
        fields = ["name", "is_customer", "is_supplier"]
        labels = {
            "name": "نام طرف حساب",
        }

    def __init__(self, *args, context_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        # در صورت وجود instance، انتخاب مناسب را در dropdown بگذار
        if self.instance:
            if self.instance.is_customer:
                self.fields['party_type'].initial = 'customer'
            elif self.instance.is_supplier:
                self.fields['party_type'].initial = 'supplier'

        if context_type in ["customer", "supplier"]:
            self.fields["party_type"].initial = context_type
            self.fields["party_type"].widget.attrs["disabled"] = True

        # فیلدهای اصلی را از فرم حذف کن تا نمایش داده نشوند
        self.fields['is_customer'].widget = forms.HiddenInput()
        self.fields['is_supplier'].widget = forms.HiddenInput()

    def save(self, commit=True):
        instance = super().save(commit=False)
        party_type = self.cleaned_data.get("party_type")

        instance.is_customer = (party_type == 'customer')
        instance.is_supplier = (party_type == 'supplier')

        if commit:
            instance.save()
        return instance
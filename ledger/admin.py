from django.contrib import admin
from .models import Item, Party, Inventory, Transaction, OP_RCV, OP_PAY
from .proxies import Receipt, Payment
from .forms import PartyForm

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id","date_shamsi","date_miladi", "op_type","item","item_id","party","party_id","qty","unit_price","total_price","description","cogs")
    list_select_related = ("item","party")
    list_filter  = ("op_type", "party", "date_shamsi", "date_miladi")
    search_fields = ("item__name","party__name")
    ordering = ("-date_miladi",)

# پایه‌ی مشترک برای دریافت/پرداخت
class _MoneyMoveBaseAdmin(admin.ModelAdmin):
    list_display = ("date_shamsi", "date_miladi", "party", "op_type", "total_price", "payment_method", "description")
    list_filter  = ("party", "payment_method", "date_shamsi", "date_miladi")
    search_fields = ("party__name",)
    exclude = ("item", "qty", "unit_price")  # این فیلدها در دریافت/پرداخت نیستند
    readonly_fields = ("op_type",)

    def save_model(self, request, obj, form, change):
        obj.op_type = self.fixed_type
        super().save_model(request, obj, form, change)

@admin.register(Receipt)
class ReceiptAdmin(_MoneyMoveBaseAdmin):
    fixed_type = OP_RCV
    def get_queryset(self, request):
        return super().get_queryset(request).filter(op_type=OP_RCV)

@admin.register(Payment)
class PaymentAdmin(_MoneyMoveBaseAdmin):
    fixed_type = OP_PAY
    def get_queryset(self, request):
        return super().get_queryset(request).filter(op_type=OP_PAY)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display  = ("id", "name", "unit", "group", "sell_price", "is_consignment", "commission_amount", "commission_percent")
    search_fields = ("name",)
    ordering      = ("name",)

class RoleQuickFilter(admin.SimpleListFilter):
    title = "نقش"
    parameter_name = "role"

    def lookups(self, request, model_admin):
        return (
            ("cust", "مشتری"),
            ("vend", "فروشنده"),
            ("both", "هردو"),
            ("any", "همه"),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "cust":
            return queryset.filter(is_customer=True, is_supplier=False)
        if val == "vend":
            return queryset.filter(is_customer=False, is_supplier=True)
        if val == "both":
            return queryset.filter(is_customer=True, is_supplier=True)
        if val == "any" or val is None:
            return queryset
        return queryset

@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    form = PartyForm  # اگر داری
    list_display = ("name", "role_display_admin", "is_customer", "is_supplier")
    search_fields = ("name",)
    list_filter = (RoleQuickFilter,)  # می‌تونی ('is_customer','is_supplier') رو هم اضافه کنی

    def role_display_admin(self, obj):
        if obj.is_customer and obj.is_supplier:
            return "هردو"
        if obj.is_customer:
            return "مشتری"
        if obj.is_supplier:
            return "فروشنده"
        return "—"
    role_display_admin.short_description = "نقش"

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display  = ("item", "qty", "last_buy_cost")
    search_fields = ("item__name",)

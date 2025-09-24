from .models import Transaction

class Receipt(Transaction):
    class Meta:
        proxy = True
        verbose_name = "دریافت"
        verbose_name_plural = "دریافت‌ها"

class Payment(Transaction):
    class Meta:
        proxy = True
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"

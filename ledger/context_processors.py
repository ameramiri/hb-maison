from .models import OP_SELL, OP_BUY, OP_RCV, OP_PAY, OP_USE
from django import template
register = template.Library()

def op_constants(request):
    OP_LABELS = {
        OP_SELL: "فروش",
        OP_BUY: "خرید",
        OP_RCV: "دریافت",
        OP_PAY: "پرداخت",
        OP_USE: "مصرف",
    }
    return {
        "OP_SELL": OP_SELL,
        "OP_BUY": OP_BUY,
        "OP_RCV": OP_RCV,
        "OP_PAY": OP_PAY,
        "OP_USE": OP_USE,
        "OP_LABELS": OP_LABELS,
    }

@register.filter
def get_item(dictionary, key):
    if dictionary and key:
        return dictionary.get(key, key)
    return key


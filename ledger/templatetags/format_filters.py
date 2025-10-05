from django.utils.safestring import mark_safe
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def get_item(dictionary, key):
    try:
        return dictionary.get(key, key)
    except Exception:
        return key

@register.filter
def thousand_separator(value):
    try:
        value = float(value)
        formatted = "{:,.0f}".format(value).replace(",", "٬")
        return formatted
    except (ValueError, TypeError):
        return value

_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"

def _to_fa_digits(s: str) -> str:
    s = str(s)
    out = []
    for ch in s:
        if "0" <= ch <= "9":
            out.append(_PERSIAN[ord(ch) - ord("0")])
        else:
            out.append(ch)
    return "".join(out)

@register.filter
def to_persian_digits(value):
    """فقط رقم‌های یک رشته/عدد را فارسی می‌کند (بدون جداکننده)."""
    if value is None:
        return ""
    return _to_fa_digits(value)

@register.filter
def fa_thousand(value, ndigits=0):
    """
    فرمت عدد با جداکننده هزارگانی + ارقام فارسی.
    استفاده:
      {{ n|fa_thousand }}       # بدون اعشار
      {{ n|fa_thousand:2 }}     # با 2 رقم اعشار
    """
    if value in ("", None):
        return ""
    try:
        q = Decimal(str(value))
    except (InvalidOperation, ValueError):
        # اگر ورودی عددی نبود، فقط رقم‌ها را فارسی کن
        return _to_fa_digits(value)

    if int(ndigits) > 0:
        fmt = f"{{:,.{int(ndigits)}f}}"
        s = fmt.format(abs(q))
    else:
        s = f"{abs(q):,.0f}"

    # جداکننده هزارگانی: اگر کاما می‌خواهی این خط را حذف کن
    s = s.replace(",", "٬")  # U+066C Arabic Thousands Separator
    s = _to_fa_digits(s)

    if q < 0:
        # منفی → پرانتز و قرمز
        return mark_safe(f"<span style='color:red; font-size:inherit; line-height:inherit;'>({s})</span>")
    return s

@register.filter
def fa_percent(value, ndigits=0):
    if value in ("", None):
        return ""

    try:
        q = Decimal(str(value))
    except (InvalidOperation, ValueError):
        # اگر ورودی اصلاً عدد نبود، همون مقدار رو برگردون
        return value

    s = fa_thousand(value, ndigits)

    percent = "\u200E\u066A"         # ‎ + ٪

    if q < 0:
        return mark_safe(f"<span style='color:red; font-size:inherit; line-height:inherit;'>{s}{percent}</span>")
    else:
        return mark_safe(f"{s}{percent}")

@register.filter
def abs_val(value):
    try:
        return abs(value)
    except:
        return value


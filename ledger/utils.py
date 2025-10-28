from functools import wraps
from django.conf import settings

def ajax_debug_logger(view_func):
    """
    Decorator: لاگ‌های ثبت‌شده در view را به خروجی JSON اضافه می‌کند (در حالت DEBUG=True)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        request._debug_logs = []  # لیست موقت برای ذخیره لاگ‌ها

        def dlog(*parts):
            msg = " ".join(str(p) for p in parts)
            request._debug_logs.append(msg)
            print("🪵 DEBUG:", msg)  # در کنسول سرور هم چاپ می‌شود

        request.dlog = dlog  # اضافه به request برای استفاده در view
        response = view_func(request, *args, **kwargs)

        # اگر پاسخ از نوع JSON است و DEBUG=True → لاگ‌ها را به آن اضافه کن
        if settings.DEBUG and hasattr(request, "_debug_logs"):
            try:
                if hasattr(response, "content") and response.get("Content-Type") == "application/json":
                    import json
                    data = json.loads(response.content)
                    data["_debug"] = request._debug_logs
                    response.content = json.dumps(data, ensure_ascii=False)
            except Exception:
                pass

        return response
    return wrapper

# تبدیل رقم به انگلیسی
def toEn(s, as_int=False):
    """
    تبدیل اعداد فارسی به انگلیسی و حذف جداکننده‌های سه‌رقمی (کاما یا فاصله).
    اگر as_int=True باشد، در صورت امکان عدد int برمی‌گرداند.
    """
    if s is None:
        return None if as_int else ''

    s = str(s).strip()
    # تبدیل اعداد فارسی به انگلیسی
    s = s.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))

    # حذف جداکننده‌های سه‌رقمی
    s = s.replace(',', '').replace('٬', '').replace(' ', '')

    if s == '':
        return None if as_int else ''

    if as_int:
        try:
            return int(s)
        except ValueError:
            return None

    return s

# تبدیل رقم به فارسی
def toFa(s):
    return s.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


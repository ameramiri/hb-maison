from ledger import views as ledger_views
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('ledger.urls')),  # اطمینان از این خط مهمه
    path('', ledger_views.register_purchase, name='home')
]

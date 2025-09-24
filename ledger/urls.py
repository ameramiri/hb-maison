from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='/login/'), name='logout'),

    path('purchase/', views.register_purchase, name='register_purchase'),
    path('sell/', views.register_sell, name='register_sell'),
    path('payment/', views.register_payment, name='register_payment'),
    path('receipt/', views.register_receipt, name='register_receipt'),
    path("items/", views.items_list, name="items_list"),
    path("items/create/", views.item_create, name="item_create"),
    path('register-item/', views.register_item, name='register_item'),
    path('register-party/', views.register_party, name='register_party'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path("reports/customer-balance/", views.customer_balance_report, name="customer_balance_report"),
    path("monthly_sales/", views.monthly_sales, name="monthly_sales"),
    path('ajax/get-sell-price/', views.get_sell_price, name='get_sell_price'),
    path('ajax/get-party-transactions/', views.get_party_transactions, name='get_party_transactions'),
    path('ajax/get-item-transactions/', views.get_item_transactions, name='get_item_transactions'),
    path('ajax/get-recent-transactions/', views.get_recent_transactions, name='get_recent_transactions'),
    path('ajax/party-txs/', views.ajax_party_txs, name='ajax_party_txs'),
    path('ajax/item-txs/', views.ajax_item_txs, name='ajax_item_txs'),
]

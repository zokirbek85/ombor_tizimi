from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, GroupListView, CurrentUserAPIView, ReturnedProductViewSet,
    ProductListAPIView, ProductDetailAPIView, ProductTransferAPIView, ProductExportAPIView, ProductImportAPIView, ProductPriceAPIView,
    CustomerListAPIView, CustomerExportAPIView, CustomerImportAPIView, CustomerReconciliationAPIView,
    SalesListAPIView, SaleDetailAPIView, SaleExportAPIView, SaleCreateAPIView, SaleStatusUpdateAPIView,
    PaymentCreateAPIView, GoodsReceiptCreateAPIView,
    DashboardStatsAPIView
)

# 1. "Kombayn"lar (ViewSet'lar) uchun router
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'returns', ReturnedProductViewSet, basename='returnedproduct')

# 2. "Kurak"lar (oddiy View'lar) uchun standart ro'yxat
urlpatterns = [
    # Foydalanuvchi ma'lumotlari
    path('user/', CurrentUserAPIView.as_view(), name='current-user'),

    # Guruhlar
    path('groups/', GroupListView.as_view(), name='group-list'),

    # Dashboard
    path('dashboard-stats/', DashboardStatsAPIView.as_view(), name='dashboard-stats'),

    # Mahsulotlar
    path('products/', ProductListAPIView.as_view(), name='product-list'),
    path('products/<int:pk>/', ProductDetailAPIView.as_view(), name='product-detail'),
    path('products/export/', ProductExportAPIView.as_view(), name='product-export'),
    path('products/import/', ProductImportAPIView.as_view(), name='product-import'),
    path('products/<int:pk>/price/', ProductPriceAPIView.as_view(), name='product-price'),
    path('products/<int:pk>/transfer/', ProductTransferAPIView.as_view(), name='product-transfer'),

    # Mijozlar
    path('customers/', CustomerListAPIView.as_view(), name='customer-list'),
    path('customers/export/', CustomerExportAPIView.as_view(), name='customer-export'),
    path('customers/import/', CustomerImportAPIView.as_view(), name='customer-import'),
    path('customers/<int:pk>/reconciliation/', CustomerReconciliationAPIView.as_view(), name='customer-reconciliation'),

    # Sotuvlar
    path('sales/', SalesListAPIView.as_view(), name='sales-list'),
    path('sales/<int:pk>/', SaleDetailAPIView.as_view(), name='sale-detail'),
    path('sales/<int:pk>/update-status/', SaleStatusUpdateAPIView.as_view(), name='sale-update-status'),
    path('sales/export/', SaleExportAPIView.as_view(), name='sale-export'),
    path('sales/create/', SaleCreateAPIView.as_view(), name='sale-create'),

    # To'lovlar
    path('payments/create/', PaymentCreateAPIView.as_view(), name='payment-create'),

    # Tovar kirimi
    path('receipts/create/', GoodsReceiptCreateAPIView.as_view(), name='receipt-create'),

    # 3. Router yaratgan manzillarni umumiy ro'yxatga qo'shamiz
    path('', include(router.urls)),
]

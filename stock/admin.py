from django.contrib import admin
from .models import Product, Customer, Sale, SaleItem, Payment, GoodsReceipt, ReturnedProduct  # <-- GoodsReceipt'ni import qildik

# --- Sotuv uchun sozlamalar ---
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'seller', 'created_at')
    list_filter = ('created_at', 'seller')
    search_fields = ('customer__full_name',)
    inlines = [SaleItemInline]

    class Media:
        js = ('admin/js/get_product_price.js',)


# --- To'lov uchun sozlamalar ---
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'amount', 'created_at')
    list_filter = ('created_at', 'customer')
    search_fields = ('customer__full_name',)


# --- Yuk kirimi uchun sozlamalar (YANGI QISM) ---
@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'quantity', 'created_at')
    list_filter = ('created_at', 'product')
    search_fields = ('product__name',)


@admin.register(ReturnedProduct)
class ReturnedProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'returned_at', 'customer', 'product', 'quantity', 'condition', 'recorded_by')
    list_filter = ('condition', 'returned_at', 'product')
    search_fields = ('customer__full_name', 'product__name', 'reason')
    autocomplete_fields = ('customer', 'product', 'recorded_by')


# --- Qolgan modellarni ro'yxatdan o'tkazish ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price')
    search_fields = ('name', 'brand', 'category')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'debt')
    search_fields = ('full_name', 'phone_number')


admin.site.register(SaleItem)

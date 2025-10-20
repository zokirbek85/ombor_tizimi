from django_filters import rest_framework as filters
from .models import Sale, ReturnedProduct


class SaleFilter(filters.FilterSet):
    # Sana oralig'i uchun filtrlar
    start_date = filters.DateFilter(field_name="created_at", lookup_expr='gte')  # ...dan katta yoki teng
    end_date = filters.DateFilter(field_name="created_at", lookup_expr='lte')    # ...dan kichik yoki teng
    status = filters.CharFilter(field_name="status")  # Status bo'yicha filtr

    class Meta:
        model = Sale
        # Mijoz va status bo'yicha filtrlar
        fields = ['customer', 'status']


class ReturnedProductFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name="returned_at", lookup_expr='gte')
    end_date = filters.DateFilter(field_name="returned_at", lookup_expr='lte')

    class Meta:
        model = ReturnedProduct
        fields = ['customer', 'product', 'condition']

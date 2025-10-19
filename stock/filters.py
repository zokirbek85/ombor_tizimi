from django_filters import rest_framework as filters
from .models import Sale

class SaleFilter(filters.FilterSet):
    # Sana oralig'i uchun filtrlar
    start_date = filters.DateFilter(field_name="created_at", lookup_expr='gte') # ...dan katta yoki teng
    end_date = filters.DateFilter(field_name="created_at", lookup_expr='lte')   # ...dan kichik yoki teng

    class Meta:
        model = Sale
        # Mijoz bo'yicha aniq moslikni qidiramiz
        fields = ['customer']
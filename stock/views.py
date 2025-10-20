# stock/views.py faylining TO'LIQ va TO'G'RI ko'rinishi

from django.db import transaction
from django.contrib.auth.models import User
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta
# --- O'zgartirilgan importlar ---
from rest_framework import generics, status, serializers  # <-- serializers to‘liq import qilindi
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets
# --------------------------------
from django.contrib.auth.models import Group
from .permissions import IsAdminUser, IsProductManager
from .serializers import UserListSerializer, UserCreateSerializer, GroupSerializer, UserSerializer
from .serializers import SaleStatusUpdateSerializer # <-- Importlarga qo'shing
from .models import Product, Customer, Sale, SaleItem, Payment, GoodsReceipt, ReturnedProduct
from .filters import SaleFilter, ReturnedProductFilter
from .serializers import UserUpdateSerializer
from .permissions import IsSotuvchi, IsOmborchi, IsBuxgalter
from rest_framework.permissions import IsAuthenticated # Bu ham kerak bo'ladi
from .serializers import (
    ProductSerializer,
    CustomerSerializer,
    SaleSerializer,
    PaymentSerializer,
    GoodsReceiptSerializer,
    SalesListSerializer,
    ReturnedProductSerializer
)

# --- MAHSULOTLAR, MIJOZLAR, NARXLAR RO‘YXATI --- #
class ProductListAPIView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsProductManager()]


class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsProductManager()]


class ProductTransferAPIView(APIView):
    permission_classes = [IsProductManager]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': 'Mahsulot topilmadi'}, status=status.HTTP_404_NOT_FOUND)

        from_condition = request.data.get('from_condition')
        to_condition = request.data.get('to_condition')
        quantity = request.data.get('quantity')

        valid_conditions = {ReturnedProduct.CONDITION_HEALTHY, ReturnedProduct.CONDITION_DEFECTIVE}
        if from_condition not in valid_conditions or to_condition not in valid_conditions or from_condition == to_condition:
            return Response({'error': "Holatlar noto'g'ri tanlangan."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({'error': "Miqdor butun son bo'lishi kerak."}, status=status.HTTP_400_BAD_REQUEST)

        if quantity <= 0:
            return Response({'error': "Miqdor 0 dan katta bo'lishi kerak."}, status=status.HTTP_400_BAD_REQUEST)

        from_field = 'quantity_healthy' if from_condition == ReturnedProduct.CONDITION_HEALTHY else 'quantity_defective'
        to_field = 'quantity_defective' if to_condition == ReturnedProduct.CONDITION_DEFECTIVE else 'quantity_healthy'

        with transaction.atomic():
            current_from = getattr(product, from_field, 0) or 0
            if current_from < quantity:
                return Response({'error': "Ko'chirish uchun yetarli qoldiq mavjud emas."}, status=status.HTTP_400_BAD_REQUEST)

            setattr(product, from_field, current_from - quantity)
            current_to = getattr(product, to_field, 0) or 0
            setattr(product, to_field, current_to + quantity)
            product.save(update_fields=[from_field, to_field])

        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)


class CustomerListAPIView(generics.ListAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated] # Tizimga kirgan hamma ko'ra olsin


class ProductPriceAPIView(APIView):
    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
            return Response({'price': product.price})
        except Product.DoesNotExist:
            return Response({'error': 'Mahsulot topilmadi'}, status=404)


# --- SOTUV YARATISH VIEW --- #
class SaleCreateAPIView(generics.CreateAPIView):
    serializer_class = SaleSerializer
    permission_classes = [IsAdminUser | IsSotuvchi]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data['customer']
        items_data = serializer.validated_data.pop('items')

        default_seller = User.objects.first()
        if not default_seller:
            return Response(
                {'error': "Tizimda birorta ham foydalanuvchi mavjud emas."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        sale = Sale.objects.create(customer=customer, seller=default_seller)
        total_debt_increase = 0

        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            price = item_data['price']

            if product.quantity_healthy < quantity:
                raise serializers.ValidationError(
                    {'error': f"'{product.name}' mahsuloti omborda yetarli emas. Qoldiq: {product.quantity_healthy}"}
                )

            SaleItem.objects.create(sale=sale, product=product, quantity=quantity, price=price)
            product.quantity_healthy -= quantity
            product.save()
            total_debt_increase += price * quantity

        customer.debt += total_debt_increase
        customer.save()

        response_serializer = SaleSerializer(sale)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# --- TO‘LOV YARATISH VIEW --- #
class PaymentCreateAPIView(generics.CreateAPIView):
    queryset = Payment.objects.all() # queryset qo'shish yaxshi amaliyot
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminUser | IsBuxgalter] # <-- "YOKI" MANTIG'I

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data['customer']
        amount = serializer.validated_data['amount']

        if customer.debt < amount:
            raise serializers.ValidationError(
                {'error': f"To‘lov summasi ({amount}) mijozning qarzidan ({customer.debt}) katta bo‘lishi mumkin emas."}
            )

        self.perform_create(serializer)
        customer.debt -= amount
        customer.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# --- YUK KIRIMI VIEW --- #
class GoodsReceiptCreateAPIView(generics.CreateAPIView):
    serializer_class = GoodsReceiptSerializer
    permission_classes = [IsAdminUser | IsOmborchi]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        self.perform_create(serializer)
        product.quantity_healthy += quantity
        product.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# --- SOTUVLAR RO‘YXATI VIEW --- #
class SalesListAPIView(generics.ListAPIView):
    queryset = Sale.objects.all().order_by('-created_at')
    serializer_class = SalesListSerializer
    filterset_class = SaleFilter


# --- MAHSULOTLARNI EXPORT QILISH --- #
class ProductExportAPIView(APIView):
    def get(self, request, *args, **kwargs):
        products = Product.objects.all().values(
            'brand', 'category', 'name', 'price', 'quantity_healthy', 'quantity_defective'
        )
        if not products:
            return Response({"message": "Eksport uchun mahsulotlar mavjud emas."}, status=status.HTTP_404_NOT_FOUND)

        df = pd.DataFrame(list(products))
        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Mahsulotlar')

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="mahsulotlar.xlsx"'
        return response


# --- MAHSULOT IMPORT VIEW --- #
class ProductImportAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            return Response({"error": "Fayl topilmadi. 'file' ni tanlang."}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES['file']
        try:
            df = pd.read_excel(file_obj)
            created_count, updated_count = 0, 0

            required_columns = ['name', 'price', 'quantity_healthy']
            for col in required_columns:
                if col not in df.columns:
                    return Response({"error": f"Excel faylda '{col}' ustuni topilmadi."},
                                    status=status.HTTP_400_BAD_REQUEST)

            for _, row in df.iterrows():
                product, created = Product.objects.update_or_create(
                    name=row['name'],
                    defaults={
                        'brand': row.get('brand', ''),
                        'category': row.get('category', ''),
                        'price': row.get('price', 0),
                        'quantity_healthy': row.get('quantity_healthy', 0),
                        'quantity_defective': row.get('quantity_defective', 0),
                    }
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            return Response({
                "message": "Import muvaffaqiyatli.",
                "created": created_count,
                "updated": updated_count
            })

        except Exception as e:
            return Response({"error": f"Xatolik: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


# --- MIJOZ EXPORT VIEW --- #
class CustomerExportAPIView(APIView):
    def get(self, request, *args, **kwargs):
        customers = Customer.objects.all().values('full_name', 'phone_number', 'address', 'debt')
        if not customers:
            return Response({"message": "Eksport uchun mijozlar mavjud emas."}, status=status.HTTP_404_NOT_FOUND)

        df = pd.DataFrame(list(customers))
        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Mijozlar')

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="mijozlar.xlsx"'
        return response


# --- MIJOZ IMPORT VIEW --- #
class CustomerImportAPIView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            return Response({"error": "Fayl topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES['file']
        try:
            df = pd.read_excel(file_obj)

            required_columns = ['full_name', 'phone_number']
            for col in required_columns:
                if col not in df.columns:
                    return Response({"error": f"Excel faylda '{col}' ustuni topilmadi."},
                                    status=status.HTTP_400_BAD_REQUEST)

            created_count, updated_count = 0, 0
            for _, row in df.iterrows():
                customer, created = Customer.objects.update_or_create(
                    full_name=row['full_name'],
                    defaults={
                        'phone_number': row.get('phone_number', ''),
                        'address': row.get('address', ''),
                        'debt': row.get('debt', 0),
                    }
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            return Response({
                "message": "Import muvaffaqiyatli.",
                "created": created_count,
                "updated": updated_count
            })

        except Exception as e:
            return Response({"error": f"Xatolik: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


# --- SOTUVLARNI EXPORT QILISH --- #
class SaleExportAPIView(APIView):
    def get(self, request, *args, **kwargs):
        queryset = Sale.objects.all().order_by('-created_at')
        filter = SaleFilter(request.GET, queryset=queryset)
        filtered_queryset = filter.qs

        if not filtered_queryset.exists():
            return Response({"message": "Eksport uchun ma'lumot topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        data_for_excel = []
        for sale in filtered_queryset:
            for item in sale.items.all():
                data_for_excel.append({
                    'Chek ID': sale.id,
                    'Sana': sale.created_at.strftime('%Y-%m-%d %H:%M'),
                    'Mijoz': sale.customer.full_name,
                    'Sotuvchi': sale.seller.username,
                    'Mahsulot': item.product.name,
                    'Soni': item.quantity,
                    'Narxi': item.price,
                    'Qator Summasi': item.quantity * item.price,
                    'Status': sale.status,
                })

        df = pd.DataFrame(data_for_excel)
        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sotuvlar')

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="sotuvlar_tarixi.xlsx"'
        return response


# --- SOTUV DETAIL VIEW --- #
class SaleDetailAPIView(generics.RetrieveAPIView):
    queryset = Sale.objects.all()
    serializer_class = SalesListSerializer


# views.py fayli ichida FAQAT SHU KLASSNI ALMASHTIRING

class SaleStatusUpdateAPIView(APIView):  # <-- generics.UpdateAPIView'dan APIView'ga o'zgartirdik
    permission_classes = [IsAuthenticated]
    """ Bitta sotuvning faqat statusini o'zgartiradi (qo'lda yozilgan mantiq) """

    SELLER_ALLOWED_STATUSES = {
        'yaratildi',
        'omborga_yuborildi',
        'bron_qilindi',
        'bron_bekor_qilindi',
        'buyurtma_bekor_qilindi',
    }
    WAREHOUSE_ALLOWED_STATUSES = {
        'yigildi',
        'yuborildi',
        'bron_yuborildi',
    }

    def patch(self, request, pk, *args, **kwargs):
        # 1. URL'dan kelgan 'pk' bo'yicha sotuvni topishga harakat qilamiz
        try:
            sale_instance = Sale.objects.get(pk=pk)
        except Sale.DoesNotExist:
            return Response({"error": "Sotuv topilmadi"}, status=status.HTTP_404_NOT_FOUND)

        previous_status = sale_instance.status

        # 2. Serializer orqali kelgan ma'lumotni tekshiramiz
        # 'partial=True' - bu PATCH uchun kerak, faqat o'zgargan maydonlarni olish imkonini beradi
        serializer = SaleStatusUpdateSerializer(instance=sale_instance, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        requested_status = serializer.validated_data.get('status', previous_status)
        user = request.user

        if not self._is_status_change_allowed(user, requested_status):
            return Response(
                {"error": "Sizda bu statusga o'zgartirish uchun ruxsat yo'q."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer.save()

        if self._is_seller(user) and requested_status != previous_status:
            self._notify_warehouse_about_status_change(sale_instance, user, requested_status)

        # 4. Muvaffaqiyatli javobni qaytaramiz
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _is_seller(self, user):
        return user.groups.filter(name='Sotuvchilar').exists()

    def _is_warehouse(self, user):
        return user.groups.filter(name='Omborchilar').exists()

    def _is_status_change_allowed(self, user, status_value):
        if user.is_staff:
            return True  # Administrator barcha statuslarni o'zgartira oladi.

        if self._is_seller(user):
            return status_value in self.SELLER_ALLOWED_STATUSES

        if self._is_warehouse(user):
            return status_value in self.WAREHOUSE_ALLOWED_STATUSES

        return False

    def _notify_warehouse_about_status_change(self, sale, actor, new_status):
        """
        Sotuvchi statusni o'zgartirganda Omborchilar guruhiga xabar yuboramiz.
        Xabar e-mail orqali jo'natiladi; agar email topilmasa, server logiga yozib qo'yamiz.
        """
        from django.core.mail import send_mail

        warehouse_group = Group.objects.filter(name='Omborchilar').first()
        if not warehouse_group:
            print(f"[NOTIFICATION] Omborchilar guruhi topilmadi. Sotuv #{sale.id} statusi {new_status} ga o'zgartirildi.")
            return

        recipient_emails = list(warehouse_group.user_set.exclude(email='').values_list('email', flat=True))
        subject = f"Sotuv #{sale.id} status o'zgarishi"
        message = (
            "Salom!\n\n"
            f"Sotuvchi {actor.get_full_name() or actor.username} sotuv #{sale.id} (mijoz: {sale.customer.full_name}) "
            f"statusini \"{sale.get_status_display()}\" ga o'zgartirdi.\n"
            "Iltimos, buyurtmani ko'rib chiqing.\n\nRahmat."
        )

        if recipient_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=recipient_emails,
                fail_silently=True,
            )
        else:
            print(f"[NOTIFICATION] Omborchilar uchun email topilmadi. {message}")


# views.py fayli ichida FAQAT SHU KLASSNI ALMASHTIRING


class ReturnedProductViewSet(viewsets.ModelViewSet):
    queryset = ReturnedProduct.objects.select_related('customer', 'product', 'recorded_by').order_by('-returned_at', '-id')
    serializer_class = ReturnedProductSerializer
    permission_classes = [IsAdminUser | IsOmborchi | IsSotuvchi | IsBuxgalter]
    filterset_class = ReturnedProductFilter

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(
                recorded_by=self.request.user if self.request.user.is_authenticated else None
            )
            self._apply_stock(instance.product, instance.quantity, instance.condition, add=True)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_product = instance.product
        old_quantity = instance.quantity
        old_condition = instance.condition

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            self.perform_update(serializer)
            updated_instance = serializer.instance
            self._apply_stock(old_product, old_quantity, old_condition, add=False)
            self._apply_stock(updated_instance.product, updated_instance.quantity, updated_instance.condition, add=True)

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        with transaction.atomic():
            self._apply_stock(instance.product, instance.quantity, instance.condition, add=False)
            self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _apply_stock(self, product, quantity, condition, add=True):
        field_name = 'quantity_healthy' if condition == ReturnedProduct.CONDITION_HEALTHY else 'quantity_defective'
        current_value = getattr(product, field_name, 0) or 0
        quantity = int(quantity)
        if add:
            new_value = current_value + quantity
        else:
            new_value = current_value - quantity
            if new_value < 0:
                new_value = 0
        setattr(product, field_name, new_value)
        product.save(update_fields=[field_name])

class DashboardStatsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # 1. Filtrlarni URL parametrlaridan olamiz
        customer_id = request.query_params.get('customer')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # 2. Asosiy so'rovlar uchun boshlang'ich "queryset"larni tayyorlaymiz
        sales_queryset = Sale.objects.all()
        payments_queryset = Payment.objects.all()

        # 3. Filtrlarni qo'llaymiz
        if customer_id:
            sales_queryset = sales_queryset.filter(customer_id=customer_id)
            payments_queryset = payments_queryset.filter(customer_id=customer_id)

        if start_date:
            sales_queryset = sales_queryset.filter(created_at__gte=start_date)
            payments_queryset = payments_queryset.filter(created_at__gte=start_date)

        if end_date:
            # Kun oxirigacha bo'lgan vaqtni olish uchun
            end_date_dt = timezone.datetime.strptime(end_date, "%Y-%m-%d").date() + timedelta(days=1)
            sales_queryset = sales_queryset.filter(created_at__lt=end_date_dt)
            payments_queryset = payments_queryset.filter(created_at__lt=end_date_dt)

        # 4. Filtrlangan ma'lumotlar asosida hisob-kitoblarni bajaramiz
        filtered_sale_items = SaleItem.objects.filter(sale__in=sales_queryset)

        total_sales_amount = filtered_sale_items.aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0
        total_sales_count = sales_queryset.count()
        total_payments = payments_queryset.aggregate(total=Sum('amount'))['total'] or 0
        average_check = total_sales_amount / total_sales_count if total_sales_count > 0 else 0

        # 5. Global (filtrlanmaydigan) statistikalar
        total_customer_debt = Customer.objects.aggregate(total=Sum('debt'))['total'] or 0
        total_customers_count = Customer.objects.count()
        total_products_count = Product.objects.count()

        today = timezone.localdate()

        returns_aggregates = ReturnedProduct.objects.aggregate(
            total_quantity=Sum('quantity'),
            healthy_quantity=Sum('quantity', filter=Q(condition=ReturnedProduct.CONDITION_HEALTHY)),
            defective_quantity=Sum('quantity', filter=Q(condition=ReturnedProduct.CONDITION_DEFECTIVE)),
            today_quantity=Sum('quantity', filter=Q(returned_at=today))
        )

        total_returns_quantity = returns_aggregates['total_quantity'] or 0
        healthy_returns_quantity = returns_aggregates['healthy_quantity'] or 0
        defective_returns_quantity = returns_aggregates['defective_quantity'] or 0
        today_returns_quantity = returns_aggregates['today_quantity'] or 0

        # 6. Grafiklar uchun ma'lumotlarni ham filtrlangan queryset asosida hisoblaymiz
        sales_by_seller = User.objects.filter(sale__in=sales_queryset).annotate(
            total_amount=Sum(F('sale__items__quantity') * F('sale__items__price')),
            sales_count=Count('sale')
        ).filter(sales_count__gt=0).order_by('-total_amount').values('username', 'total_amount', 'sales_count')

        top_products = Product.objects.filter(saleitem__in=filtered_sale_items).annotate(
            total_sold=Sum('saleitem__quantity')
        ).filter(total_sold__gt=0).order_by('-total_sold')[:5].values('name', 'total_sold')

        data = {
            'stats_cards': {
                'total_sales_amount': total_sales_amount,
                'total_sales_count': total_sales_count,
                'total_payments': total_payments,
                'average_check': average_check,
                'total_customer_debt': total_customer_debt, # Bu global bo'lib qoladi
                'total_customers_count': total_customers_count, # Bu global
                'total_products_count': total_products_count, # Bu global
                'total_returns_quantity': total_returns_quantity,
                'healthy_returns_quantity': healthy_returns_quantity,
                'defective_returns_quantity': defective_returns_quantity,
                'today_returns_quantity': today_returns_quantity,
            },
            'sales_by_seller': list(sales_by_seller),
            'top_products': list(top_products),
        }
        return Response(data)
    
# views.py faylining OXIRIGA qo'shing

class CustomerReconciliationAPIView(APIView):
    def get(self, request, pk, *args, **kwargs):
        # 1. URL parametrlaridan mijoz va sanalarni olamiz
        try:
            customer = Customer.objects.get(pk=pk)
        except Customer.DoesNotExist:
            return Response({"error": "Mijoz topilmadi"}, status=status.HTTP_404_NOT_FOUND)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response({"error": "Sana oralig'i to'liq kiritilishi shart."}, status=status.HTTP_400_BAD_REQUEST)

        start_date = timezone.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = timezone.datetime.strptime(end_date_str, "%Y-%m-%d").date() + timedelta(days=1)

        # 2. Boshlang'ich qoldiqni hisoblash (davr boshigacha bo'lgan barcha operatsiyalar)
        sales_before = SaleItem.objects.filter(sale__customer=customer, sale__created_at__lt=start_date).aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0
        payments_before = Payment.objects.filter(customer=customer, created_at__lt=start_date).aggregate(total=Sum('amount'))['total'] or 0
        starting_balance = sales_before - payments_before

        # 3. Davr ichidagi barcha operatsiyalarni yig'amiz
        sales_in_period = Sale.objects.filter(customer=customer, created_at__gte=start_date, created_at__lt=end_date)
        payments_in_period = Payment.objects.filter(customer=customer, created_at__gte=start_date, created_at__lt=end_date)

        # 4. Operatsiyalarni bitta ro'yxatga birlashtirib, sana bo'yicha saralaymiz
        transactions = []
        total_debit_in_period = 0
        total_credit_in_period = 0

        for sale in sales_in_period:
            sale_total = sale.items.aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0
            transactions.append({
                "date": sale.created_at,
                "type": "Sotuv",
                "document": f"Chek #{sale.id}",
                "debit": sale_total,
                "credit": 0
            })
            total_debit_in_period += sale_total

        for payment in payments_in_period:
            transactions.append({
                "date": payment.created_at,
                "type": "To'lov",
                "document": f"To'lov #{payment.id}",
                "debit": 0,
                "credit": payment.amount
            })
            total_credit_in_period += payment.amount

        transactions.sort(key=lambda x: x['date']) # Sana bo'yicha saralash

        # 5. Yakuniy qoldiqni hisoblash
        ending_balance = starting_balance + total_debit_in_period - total_credit_in_period

        # 6. Javobni tayyorlaymiz
        data = {
            "customer": CustomerSerializer(customer).data,
            "period": {"start_date": start_date_str, "end_date": end_date_str},
            "starting_balance": starting_balance,
            "ending_balance": ending_balance,
            "total_debit": total_debit_in_period,
            "total_credit": total_credit_in_period,
            "transactions": transactions
        }

        return Response(data)
    

class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Faqat tizimga kirgan foydalanuvchilar o'z ma'lumotini olishlari mumkin.

    def get(self, request):
        serializer = UserSerializer(request.user)  # Serializer guruhlar va is_staff maydonlarini ham qaytaradi.
        return Response(serializer.data)
    
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('id') # <-- Tartiblab olamiz
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        # --- YANGI QISM ---
        if self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        # --- YANGI QISM TUGADI ---
        return UserListSerializer

# Guruhlar ro'yxatini olish uchun
class GroupListView(APIView): # <-- genercis.ListAPIView'dan APIView'ga o'zgartirdik
    """ Guruhlar ro'yxatini qo'lda qaytaradi (diagnostika uchun) """
    permission_classes = [IsAdminUser] # <-- Hozircha bu o'chiq tursin

    def get(self, request, *args, **kwargs):
        # 1. Ma'lumotlar bazasidan BARCHA guruhlarni so'rab olamiz
        groups = Group.objects.all()

        # 2. ENG MUHIM QISM: Topilgan natijani terminalga chiqaramiz
        print("BAZADAN TOPILGAN GURUHLAR:", groups)

        # 3. Serializer yordamida ma'lumotlarni JSON'ga o'giramiz
        serializer = GroupSerializer(groups, many=True)

        # 4. JSON javobni qaytaramiz
        return Response(serializer.data)
    

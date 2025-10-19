# stock/views.py faylining TO'LIQ va TO'G'RI ko'rinishi

from django.db import transaction
from django.contrib.auth.models import User
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from django.db.models import Sum, Count, F
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
from .permissions import IsAdminUser
from .serializers import UserListSerializer, UserCreateSerializer, GroupSerializer
from .serializers import SaleStatusUpdateSerializer # <-- Importlarga qo'shing
from .models import Product, Customer, Sale, SaleItem, Payment, GoodsReceipt
from .filters import SaleFilter
from .serializers import UserUpdateSerializer
from .permissions import IsAdminUser, IsSotuvchi, IsOmborchi, IsBuxgalter
from rest_framework.permissions import IsAuthenticated # Bu ham kerak bo'ladi
from .serializers import (
    ProductSerializer,
    CustomerSerializer,
    SaleSerializer,
    PaymentSerializer,
    GoodsReceiptSerializer,
    SalesListSerializer
)

# --- MAHSULOTLAR, MIJOZLAR, NARXLAR RO‘YXATI --- #
class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated] # Tizimga kirgan hamma ko'ra olsin


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
    permission_classes = [IsAdminUser | IsSotuvchi]
    """ Bitta sotuvning faqat statusini o'zgartiradi (qo'lda yozilgan mantiq) """

    def patch(self, request, pk, *args, **kwargs):
        # 1. URL'dan kelgan 'pk' bo'yicha sotuvni topishga harakat qilamiz
        try:
            sale_instance = Sale.objects.get(pk=pk)
        except Sale.DoesNotExist:
            return Response({"error": "Sotuv topilmadi"}, status=status.HTTP_404_NOT_FOUND)

        # 2. Serializer orqali kelgan ma'lumotni tekshiramiz
        # 'partial=True' - bu PATCH uchun kerak, faqat o‘zgargan maydonlarni olish imkonini beradi
        serializer = SaleStatusUpdateSerializer(instance=sale_instance, data=request.data, partial=True)

        if serializer.is_valid():
            # 3. Ma'lumot to‘g‘ri bo‘lsa, saqlaymiz
            serializer.save()
            # 4. Muvaffaqiyatli javobni qaytaramiz
            return Response(serializer.data, status=status.HTTP_200_OK)

        # 5. Agar ma'lumot xato bo‘lsa, validatsiya xatolarini qaytaramiz
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# views.py fayli ichida FAQAT SHU KLASSNI ALMASHTIRING

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
    def get(self, request):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        return Response(data)
    
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
    

from rest_framework import serializers
from django.contrib.auth.models import User, Group
from .models import (
    Product, Customer, Sale, SaleItem, Payment, GoodsReceipt, ReturnedProduct
)

# --- ASOSIY MODELLAR UCHUN ---
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


# --- FOYDALANUVCHILARNI BOSHQARISH UCHUN ---

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name')


class UserSerializer(serializers.ModelSerializer):
    groups = GroupSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'groups', 'is_staff')


class UserListSerializer(serializers.ModelSerializer):
    groups = GroupSerializer(many=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'groups')


class UserCreateSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Group.objects.all()
    )

    class Meta:
        model = User
        fields = ('username', 'password', 'first_name', 'last_name', 'groups')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        groups = validated_data.pop('groups')
        user = User.objects.create_user(**validated_data)
        user.groups.set(groups)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Group.objects.all(), required=False
    )
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('username', 'password', 'first_name', 'last_name', 'groups')

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        return super().update(instance, validated_data)


# --- SOTUVLAR UCHUN ---
class ProductForSaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ('name',)


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ('product', 'quantity', 'price')


class SaleItemDetailSerializer(serializers.ModelSerializer):
    product = ProductForSaleItemSerializer()

    class Meta:
        model = SaleItem
        fields = ('product', 'quantity', 'price')


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    seller = serializers.ReadOnlyField(source='seller.username')

    class Meta:
        model = Sale
        fields = ('id', 'customer', 'seller', 'created_at', 'items')


# --- SHU QISM O'ZGARTIRILDI ---
class SalesListSerializer(serializers.ModelSerializer):
    """ Barcha sotuvlar ro'yxatini chiroyli ko'rsatish uchun maxsus serializer """
    customer = CustomerSerializer()
    seller = UserSerializer()
    items = SaleItemDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Sale  # to'g'rilandi (avval xato bilan User edi)
        fields = ('id', 'customer', 'seller', 'status', 'created_at', 'items')  # 'items' qo'shildi
# --------------------------------


class SaleStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ('status',)


# --- TO‘LOVLAR VA KIRIMLAR UCHUN ---
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'customer', 'amount', 'created_at')


class GoodsReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodsReceipt
        fields = ('id', 'product', 'quantity', 'created_at')


class ReturnedProductSerializer(serializers.ModelSerializer):
    customer_detail = CustomerSerializer(source='customer', read_only=True)
    product_detail = ProductSerializer(source='product', read_only=True)
    recorded_by_detail = UserSerializer(source='recorded_by', read_only=True)

    class Meta:
        model = ReturnedProduct
        fields = (
            'id',
            'customer',
            'product',
            'quantity',
            'condition',
            'reason',
            'returned_at',
            'recorded_by',
            'created_at',
            'customer_detail',
            'product_detail',
            'recorded_by_detail',
        )
        read_only_fields = (
            'recorded_by',
            'created_at',
            'customer_detail',
            'product_detail',
            'recorded_by_detail',
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Miqdor musbat bo'lishi kerak.")
        return value

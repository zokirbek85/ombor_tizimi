from django.db import models
from django.contrib.auth.models import User  # <-- SHU QATOR QO'SHILDI

# Ma'lumotlar bazasi jadvallarining "chizmalari" (modellar) shu yerda yaratiladi.


class Product(models.Model):
    """
    Ombordagi mahsulotlar (tovarlar) haqidagi ma'lumotlarni saqlaydi.
    """
    brand = models.CharField(max_length=200, verbose_name="Mahsulot brendi")
    category = models.CharField(max_length=200, verbose_name="Mahsulot kategoriyasi")
    name = models.CharField(max_length=200, verbose_name="Mahsulot nomi")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narxi (USDda)")
    quantity_healthy = models.PositiveIntegerField(default=0, verbose_name="Sog'lom qoldiq (dona)")
    quantity_defective = models.PositiveIntegerField(default=0, verbose_name="Brak qoldiq (dona)")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"


class Customer(models.Model):
    """
    Mijozlar (xaridorlar) va ularning ma'lumotlarini saqlaydi.
    """
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    phone_number = models.CharField(max_length=20, verbose_name="Telefon raqami")
    address = models.TextField(verbose_name="Manzili")
    debt = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Qarzdorligi (USDda)")

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"


class Sale(models.Model):
    """
    Sotuv operatsiyasi (chek) haqidagi umumiy ma'lumotlarni saqlaydi.
    """
    # --- YANGI QISM BOSHLANDI ---
    STATUS_CHOICES = [
        ('yaratildi', 'Yaratildi'),
        ('omborga_yuborildi', 'Omborga yuborildi'),
        ('yigildi', 'Yig\'ildi'),
        ('yuborildi', 'Yuborildi'),
        ('bron_qilindi', 'Bron qilindi'),
        ('bron_yuborildi', 'Bron yuborildi'),
        ('bron_bekor_qilindi', 'Bron bekor qilindi'),
        ('buyurtma_bekor_qilindi', 'Buyurtma bekor qilindi'),
    ]

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='yaratildi',  # Har qanday yangi sotuv shu status bilan boshlanadi
        verbose_name="Sotuv statusi"
    )
    # --- YANGI QISM TUGADI ---

    seller = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Sotuvchi (Menejer)")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Mijoz")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Sotuv sanasi")

    def __str__(self):
        return f"{self.id}-sonli sotuv - {self.customer} ({self.created_at.strftime('%Y-%m-%d')})"

    class Meta:
        verbose_name = "Sotuv (Chek)"
        verbose_name_plural = "Sotuvlar (Cheklar)"


class SaleItem(models.Model):
    """
    Bitta sotuv ("chek") ichidagi har bir mahsulotni alohida saqlaydi.
    """
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE, verbose_name="Tegishli sotuv")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Mahsulot")
    quantity = models.PositiveIntegerField(verbose_name="Soni")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sotuv narxi (1 dona)")

    def __str__(self):
        return f"{self.product.name} - {self.quantity} dona"

    class Meta:
        verbose_name = "Sotilgan mahsulot"
        verbose_name_plural = "Sotilgan mahsulotlar"


class Payment(models.Model):
    """
    Mijozlardan kelib tushgan to'lovlarni saqlaydi.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Mijoz")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="To'lov summasi (USDda)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="To'lov sanasi")

    def __str__(self):
        return f"{self.customer} - {self.amount} USD to'lov"

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"


class GoodsReceipt(models.Model):
    """
    Omborga qabul qilingan yuklar (tovarlar) tarixini saqlaydi.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Mahsulot")
    quantity = models.PositiveIntegerField(verbose_name="Qabul qilingan miqdor (dona)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qabul qilingan sana")

    def __str__(self):
        return f"{self.product.name} - {self.quantity} dona kirim"

    class Meta:
        verbose_name = "Yuk kirimi"
        verbose_name_plural = "Yuk kirimlari"

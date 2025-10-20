from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """ Faqat admin (is_staff=True) foydalanuvchilarga ruxsat beradi. """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)

# --- YANGI "QO'RIQCHI"LAR ---

class IsSotuvchi(permissions.BasePermission):
    """ Foydalanuvchi "Sotuvchilar" guruhiga a'zoligini tekshiradi. """
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Sotuvchilar').exists()

class IsOmborchi(permissions.BasePermission):
    """ Foydalanuvchi "Omborchilar" guruhiga a'zoligini tekshiradi. """
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Omborchilar').exists()

class IsBuxgalter(permissions.BasePermission):
    """ Foydalanuvchi "Buxgalterlar" guruhiga a'zoligini tekshiradi. """
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Buxgalterlar').exists()


class IsProductManager(permissions.BasePermission):
    """ Admin, omborchi yoki buxgalterlarga mahsulotlarni boshqarishga ruxsat beradi. """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return user.groups.filter(name__in=['Omborchilar', 'Buxgalterlar']).exists()

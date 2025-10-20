from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase

from .models import Customer, Product


class ReturnedProductAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='admin', password='testpass', is_staff=True)
        self.client.force_authenticate(self.user)

        self.customer = Customer.objects.create(
            full_name='Test Customer',
            phone_number='123456789',
            address='Test Address',
            debt=0
        )
        self.product = Product.objects.create(
            brand='Brand',
            category='Category',
            name='Test Product',
            price=100,
            quantity_healthy=10,
            quantity_defective=2,
        )

    def test_create_returned_product_updates_stock(self):
        url = reverse('returnedproduct-list')
        payload = {
            'customer': self.customer.id,
            'product': self.product.id,
            'quantity': 3,
            'condition': 'healthy',
            'reason': 'Test reason',
            'returned_at': '2025-01-01',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_healthy, 13)
        self.assertEqual(self.product.quantity_defective, 2)

    def test_update_returned_product_rebalances_stock(self):
        list_url = reverse('returnedproduct-list')
        create_payload = {
            'customer': self.customer.id,
            'product': self.product.id,
            'quantity': 4,
            'condition': 'healthy',
            'reason': 'Initial',
            'returned_at': '2025-01-02',
        }
        create_response = self.client.post(list_url, create_payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        return_id = create_response.data['id']

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_healthy, 14)
        self.assertEqual(self.product.quantity_defective, 2)

        detail_url = reverse('returnedproduct-detail', args=[return_id])
        update_payload = {
            'quantity': 2,
            'condition': 'defective',
        }
        response = self.client.patch(detail_url, update_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity_healthy, 10)
        self.assertEqual(self.product.quantity_defective, 4)


class ProductAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='manager', password='testpass', is_staff=True)
        self.client.force_authenticate(self.user)

    def test_create_product(self):
        url = reverse('product-list')
        payload = {
            'brand': 'Brand',
            'category': 'Doors',
            'name': 'Wood Door',
            'price': 250.5,
            'quantity_healthy': 5,
            'quantity_defective': 1,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Product.objects.filter(name='Wood Door').exists())

    def test_transfer_stock_between_conditions(self):
        product = Product.objects.create(
            brand='Brand',
            category='Windows',
            name='Window Frame',
            price=120,
            quantity_healthy=10,
            quantity_defective=3,
        )
        transfer_url = reverse('product-transfer', args=[product.id])
        payload = {
            'from_condition': 'healthy',
            'to_condition': 'defective',
            'quantity': 4,
        }
        response = self.client.post(transfer_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        product.refresh_from_db()
        self.assertEqual(product.quantity_healthy, 6)
        self.assertEqual(product.quantity_defective, 7)

        # transfer back
        payload_back = {
            'from_condition': 'defective',
            'to_condition': 'healthy',
            'quantity': 2,
        }
        response_back = self.client.post(transfer_url, payload_back, format='json')
        self.assertEqual(response_back.status_code, status.HTTP_200_OK)

        product.refresh_from_db()
        self.assertEqual(product.quantity_healthy, 8)
        self.assertEqual(product.quantity_defective, 5)

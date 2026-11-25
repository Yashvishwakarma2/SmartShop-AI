from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Customer, Lead, Shop


class DashboardShopIsolationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='shop_admin',
            password='StrongPass!234',
            is_staff=True,
            is_superuser=True,
        )
        self.admin_shop = Shop.objects.create(
            owner=self.admin,
            name='Admin Shop',
            shop_type='Retail',
            phone='1111111111',
            address='Admin address',
        )

        other_owner = User.objects.create_user(
            username='other_owner',
            password='StrongPass!234',
        )
        other_shop = Shop.objects.create(
            owner=other_owner,
            name='Other Shop',
            shop_type='Retail',
            phone='2222222222',
            address='Other address',
        )
        Customer.objects.create(
            shop=other_shop,
            name='Other Customer',
            phone='3333333333',
        )
        Lead.objects.create(
            shop=other_shop,
            customer=Customer.objects.get(shop=other_shop),
            status='NEW',
        )

        self.client.force_login(self.admin)

    def test_new_super_dashboard_starts_empty_without_its_own_shop(self):
        self.admin.shop.delete()

        response = self.client.get(reverse('superuser_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_shops'], 0)
        self.assertEqual(response.context['total_customers'], 0)
        self.assertEqual(response.context['total_leads'], 0)
        self.assertQuerySetEqual(response.context['customers'], [])

    def test_super_dashboard_only_counts_its_associated_shop(self):
        Customer.objects.create(
            shop=self.admin_shop,
            name='Admin Customer',
            phone='4444444444',
        )
        Lead.objects.create(
            shop=self.admin_shop,
            customer=Customer.objects.get(shop=self.admin_shop),
            status='NEW',
        )

        response = self.client.get(reverse('superuser_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_shops'], 1)
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_leads'], 1)
        self.assertEqual(response.context['new_leads'], 1)
        self.assertEqual(
            list(response.context['customers'].values_list('name', flat=True)),
            ['Admin Customer'],
        )

    def test_lead_dashboard_only_counts_its_associated_shop(self):
        Customer.objects.create(
            shop=self.admin_shop,
            name='Admin Customer',
            phone='4444444444',
        )
        Lead.objects.create(
            shop=self.admin_shop,
            customer=Customer.objects.get(shop=self.admin_shop),
            status='NEW',
        )

        response = self.client.get(reverse('lead_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_leads'], 1)
        self.assertEqual(response.context['new_leads'], 1)

    def test_reports_page_loads_with_shop_scoped_metrics(self):
        Customer.objects.create(
            shop=self.admin_shop,
            name='Report Customer',
            phone='5555555555',
        )

        response = self.client.get(reverse('reports'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crm/reports.html')
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_leads'], 0)

from django.db import models
from django.contrib.auth.models import User




class Shop(models.Model):

    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=150)

    shop_type = models.CharField(max_length=100)

    phone = models.CharField(max_length=15)

    address = models.TextField()

    def __str__(self):
        return self.name
    

class Customer(models.Model):

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=150)

    phone = models.CharField(max_length=15)

    email = models.EmailField(blank=True)

    address = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Product(models.Model):

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=150)

    category = models.CharField(max_length=100)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    


class Lead(models.Model):

    STATUS = [
        ('NEW', 'New Lead'),
        ('INTERESTED', 'Interested'),
        ('FOLLOWUP', 'Follow-up'),
        ('RETURNED', 'Customer Returned'),
        ('DOCUMENT', 'Document Verification'),
        ('BANK', 'Bank Processing'),
        ('CONVERTED', 'Purchase Completed'),
        ('LOST', 'Lost Lead'),
    ]

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads'
    )

    expected_purchase_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default='NEW'
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.customer.name

    @property
    def latest_document(self):
        return self.customerdocument_set.order_by('-id').first()

    @property
    def document_status_badge(self):
        doc = self.customerdocument_set.order_by('-id').first()
        if not doc:
            return {'status': 'NONE', 'label': 'No Document', 'color': '#64748b', 'bg': '#f1f5f9', 'icon': 'minus'}
        mapping = {
            'VERIFIED': {'label': 'Verified', 'color': '#059669', 'bg': '#ecfdf5', 'icon': 'check'},
            'PENDING': {'label': 'Pending Review', 'color': '#d97706', 'bg': '#fef3c7', 'icon': 'clock'},
            'REJECTED': {'label': 'Rejected', 'color': '#dc2626', 'bg': '#fee2e2', 'icon': 'xmark'},
            'CORRECTION': {'label': 'Correction Needed', 'color': '#2563eb', 'bg': '#eff6ff', 'icon': 'triangle-exclamation'},
        }
        res = mapping.get(doc.status, {'label': doc.get_status_display(), 'color': '#64748b', 'bg': '#f1f5f9', 'icon': 'info'}).copy()
        res['status'] = doc.status
        res['doc_name'] = doc.document_name
        res['id'] = doc.id
        return res

    @property
    def bank_status_badge(self):
        bank = getattr(self, 'bankapplication', None)
        if not bank:
            return {'status': 'NONE', 'label': 'Not Applied', 'color': '#64748b', 'bg': '#f1f5f9', 'icon': 'minus'}
        mapping = {
            'APPROVED': {'label': 'Approved', 'color': '#059669', 'bg': '#ecfdf5', 'icon': 'check'},
            'REVIEW': {'label': 'Under Review', 'color': '#2563eb', 'bg': '#eff6ff', 'icon': 'magnifying-glass'},
            'PENDING': {'label': 'Pending Review', 'color': '#d97706', 'bg': '#fef3c7', 'icon': 'clock'},
            'REJECTED': {'label': 'Rejected', 'color': '#dc2626', 'bg': '#fee2e2', 'icon': 'xmark'},
        }
        res = mapping.get(bank.status, {'label': bank.get_status_display(), 'color': '#64748b', 'bg': '#f1f5f9', 'icon': 'info'}).copy()
        res['status'] = bank.status
        res['bank_name'] = bank.bank_name
        res['loan_amount'] = bank.loan_amount
        res['id'] = bank.id
        return res
    
    



class FollowUp(models.Model):

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE
    )

    reminder_date = models.DateField()

    message = models.TextField(blank=True)

    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.lead.customer.name
    
    
    


class CallLog(models.Model):

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE
    )

    call_date = models.DateTimeField(auto_now_add=True)

    remarks = models.TextField()

    next_followup = models.DateField(
        null=True,
        blank=True
    )

    def __str__(self):
        return self.lead.customer.name
    


class CustomerDocument(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('CORRECTION', 'Correction Required'),
    ]

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE
    )

    document_name = models.CharField(max_length=100)

    document_file = models.FileField(
        upload_to='customer_documents/'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.document_name} - {self.lead.customer.name}"
    
    

class BankApplication(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE
    )

    bank_name = models.CharField(max_length=100)

    loan_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    def __str__(self):
        return f"{self.bank_name} - {self.lead.customer.name}"
    
    
    
    

class Purchase(models.Model):

    PAYMENT_CHOICES = [
        ('CASH', 'Cash'),
        ('BANK', 'Bank'),
        ('UPI', 'UPI'),
        ('CARD', 'Card'),
    ]

    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES
    )

    purchase_date = models.DateField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.lead.customer.name} - {self.amount}"
    

from django.db import models
from django.contrib.auth.models import User


class StaffProfile(models.Model):

    ROLE_CHOICES = [
        ('LEAD', 'Lead Manager'),
        ('DOCUMENT', 'Document Manager'),
        ('BANK', 'Bank Manager'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='staff_members'
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class DashboardAccessCode(models.Model):

    DASHBOARD_CHOICES = [
        ('LEAD', 'Lead Dashboard'),
        ('DOCUMENT', 'Document Dashboard'),
        ('BANK', 'Bank Dashboard'),
    ]

    dashboard = models.CharField(
        max_length=20,
        choices=DASHBOARD_CHOICES,
        unique=True
    )
    code = models.CharField(max_length=12, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_dashboard_display()}: {self.code}"
 
 
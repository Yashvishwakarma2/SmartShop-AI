from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Shop

 
 
from .models import Lead, Customer, Product


class LeadForm(forms.ModelForm):

    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Assign to Lead Dashboard",
        empty_label="-- Select Lead Dashboard (or leave unassigned) --",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Lead

        fields = [
            'customer',
            'product',
            'assigned_to',
            'expected_purchase_date',
            'status',
            'notes'
        ]

        widgets = {
            'expected_purchase_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),

            'status': forms.Select(
                attrs={'class': 'form-control'}
            ),

            'notes': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Enter customer interest details'
                }
            )
        }

    def __init__(self, *args, shop=None, is_lead_manager=False, **kwargs):

        super().__init__(*args, **kwargs)

        if shop:
            self.fields['customer'].queryset = Customer.objects.filter(
                shop=shop
            )
            self.fields['product'].queryset = Product.objects.filter(
                shop=shop
            )
            # Associated Lead Dashboard users for this shop
            lead_staff = User.objects.filter(
                staff_profile__shop=shop,
                staff_profile__role='LEAD'
            ).distinct()
            self.fields['assigned_to'].queryset = lead_staff
            self.fields['assigned_to'].label_from_instance = (
                lambda user: f"{user.username} (Lead Dashboard)"
            )
        else:
            self.fields['customer'].queryset = Customer.objects.none()
            self.fields['product'].queryset = Product.objects.none()
            self.fields['assigned_to'].queryset = User.objects.none()

        self.fields['product'].required = False

        if is_lead_manager:
            self.fields['assigned_to'].widget = forms.HiddenInput()

class CustomerForm(forms.ModelForm):

    class Meta:
        model = Customer

        fields = [
            'name',
            'phone',
            'email',
            'address'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer name'
            }),

            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),

            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),

            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer address',
                'rows': 3
            }),
        }


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product

        fields = [
            'name',
            'category',
            'price',
            'description'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name'
            }),

            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category'
            }),

            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter price'
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Product description',
                'rows': 3
            }),
        }


class SignupForm(UserCreationForm):

    email = forms.EmailField()
    dashboard = forms.ChoiceField(
        choices=[
            ('LEAD', 'Lead Dashboard (Lead Manager)'),
            ('DOCUMENT', 'Document Dashboard (Document Manager)'),
            ('BANK', 'Bank Dashboard (Bank Manager)'),
            ('OWNER', 'Shop Owner Dashboard (Shop Owner)'),
        ],
        widget=forms.RadioSelect,
        initial='OWNER'
    )
    access_code = forms.CharField(
        max_length=15,
        required=False,
        label="Dashboard Access Key",
        help_text="Required for Lead, Document, and Bank dashboards.",
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter Access Key (e.g. LEAD-DASH, DOC-DASH, BANK-DASH)',
            'style': 'text-transform: uppercase;'
        })
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'dashboard',
            'access_code',
            'password1',
            'password2'
        ]

    def clean(self):
        cleaned_data = super().clean()
        dashboard = cleaned_data.get('dashboard')
        access_code = (cleaned_data.get('access_code') or '').strip().upper()

        code_map = {
            'LEAD': 'LEAD-DASH',
            'DOCUMENT': 'DOC-DASH',
            'BANK': 'BANK-DASH',
        }

        if dashboard in code_map:
            default_code = code_map[dashboard]
            from .models import DashboardAccessCode
            db_code = DashboardAccessCode.objects.filter(dashboard=dashboard, is_active=True).first()
            valid_codes = {default_code}
            if db_code and db_code.code:
                valid_codes.add(db_code.code.strip().upper())

            if not access_code:
                self.add_error('access_code', f'Access Key is required to create a {dict(self.fields["dashboard"].choices).get(dashboard)} account.')
            elif access_code not in valid_codes:
                self.add_error('access_code', f'Invalid Access Key for {dict(self.fields["dashboard"].choices).get(dashboard)}.')

        return cleaned_data

from django import forms
from .models import CustomerDocument


from django import forms
from .models import BankApplication

from django import forms
from .models import Purchase


class PurchaseForm(forms.ModelForm):

    class Meta:
        model = Purchase

        fields = [
            'amount',
            'payment_method',
        ]

        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter purchase amount',
                'min': '0.01',
                'step': '0.01'
            }),

            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

class BankApplicationForm(forms.ModelForm):

    class Meta:
        model = BankApplication

        fields = [
            'bank_name',
            'loan_amount',
        ]

        widgets = {
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter bank name'
            }),

            'loan_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter loan amount',
                'min': '1',
                'step': '0.01'
            }),
        }

class DocumentForm(forms.ModelForm):

    class Meta:
        model = CustomerDocument

        fields = [
            'document_name',
            'document_file',
            'remarks'
        ]

        widgets = {
            'document_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Example: Aadhaar Card'
            }),

            'document_file': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),

            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter document details'
            }),
        }

    def clean_document_file(self):

        file = self.cleaned_data.get('document_file')

        if file:

            allowed_extensions = [
                '.pdf', '.jpg', '.jpeg', '.png'
            ]

            extension = '.' + file.name.rsplit('.', 1)[-1].lower()

            if extension not in allowed_extensions:
                raise forms.ValidationError(
                    'Only PDF, JPG, JPEG and PNG files are allowed.'
                )

            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    'File size must not exceed 5 MB.'
                )

        return file


class ShopForm(forms.ModelForm):

    class Meta:
        model = Shop

        fields = [
            'name',
            'shop_type',
            'phone',
            'address'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter shop name'
            }),

            'shop_type': forms.TextInput(attrs={
                'placeholder': 'Clothing, Grocery, Jewellery etc.'
            }),

            'phone': forms.TextInput(attrs={
                'placeholder': 'Enter mobile number'
            }),

            'address': forms.Textarea(attrs={
                'placeholder': 'Enter shop address',
                'rows': 3
            })
        }


class UserProfileForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
        }
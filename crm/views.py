from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group, User
from django.shortcuts import reverse
from django.utils.crypto import get_random_string

from .forms import LeadForm, SignupForm, ShopForm, UserProfileForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .models import Shop
from .models import Customer, Lead, FollowUp, Purchase
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Customer, Product
from .forms import CustomerForm, ProductForm

from django.utils import timezone

from .models import CustomerDocument, Lead
from .forms import DocumentForm


from .models import BankApplication, Lead
from .forms import BankApplicationForm
from django.contrib import messages

from .models import Purchase, Lead, DashboardAccessCode


STATIC_DASHBOARD_CODES = {
    'LEAD': 'LEAD-DASH',
    'DOCUMENT': 'DOC-DASH',
    'BANK': 'BANK-DASH',
}


def set_dashboard_access_code(dashboard, code):
    code = code.strip().upper()
    if not code:
        code = STATIC_DASHBOARD_CODES.get(dashboard, 'CODE')
    if len(code) > 12:
        raise ValidationError('Access keys must be 12 characters or fewer.')

    conflict = DashboardAccessCode.objects.filter(code=code).exclude(dashboard=dashboard).first()
    if conflict:
        raise ValidationError(
            f'This access key is already used by the {conflict.get_dashboard_display()}.'
        )

    with transaction.atomic():
        DashboardAccessCode.objects.update_or_create(
            dashboard=dashboard,
            defaults={'code': code, 'is_active': True},
        )


class DashboardLoginView(LoginView):
    template_name = 'authentication/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected = self.request.GET.get('dashboard', 'owner')
        if selected not in {'super', 'lead', 'document', 'bank', 'owner'}:
            selected = 'owner'
        context['selected_dashboard'] = selected
        return context

    def post(self, request, *args, **kwargs):
        access_code = request.POST.get('access_code', '').strip().upper()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # If user is logging in using code directly without username/password
        if access_code and not (username and password):
            code_obj = DashboardAccessCode.objects.filter(
                code=access_code,
                is_active=True
            ).first()
            if not code_obj:
                messages.error(request, 'Invalid dashboard access code.')
                return redirect(f"{reverse('login')}?dashboard={request.POST.get('dashboard', 'owner')}")

            role_user_map = {
                'LEAD': ('lead_staff', 'Lead Manager', 'lead_dashboard'),
                'DOCUMENT': ('document_staff', 'Document Manager', 'document_dashboard'),
                'BANK': ('bank_staff', 'Bank Manager', 'bank_dashboard'),
            }
            if code_obj.dashboard in role_user_map:
                uname, gname, dest = role_user_map[code_obj.dashboard]
                user, _ = User.objects.get_or_create(username=uname, defaults={'is_active': True})
                group, _ = Group.objects.get_or_create(name=gname)
                # Ensure user only has this role
                all_mgr_groups = Group.objects.filter(name__in=['Lead Manager', 'Document Manager', 'Bank Manager'])
                user.groups.remove(*all_mgr_groups)
                user.groups.add(group)
                login(request, user)
                return redirect(dest)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        user = self.request.user

        if getattr(self, 'code_obj', None):
            dest_map = {
                'SUPER': 'superuser_dashboard',
                'LEAD': 'lead_dashboard',
                'DOCUMENT': 'document_dashboard',
                'BANK': 'bank_dashboard',
            }
            if self.code_obj.dashboard in dest_map:
                return reverse(dest_map[self.code_obj.dashboard])

        dashboard = self.request.POST.get('dashboard')
        destinations = {
            'super': ('superuser_dashboard', lambda: user.is_superuser),
            'lead': ('lead_dashboard', lambda: user.is_superuser or user.groups.filter(name='Lead Manager').exists()),
            'document': ('document_dashboard', lambda: user.is_superuser or user.groups.filter(name='Document Manager').exists()),
            'bank': ('bank_dashboard', lambda: user.is_superuser or user.groups.filter(name='Bank Manager').exists()),
            'owner': ('dashboard', lambda: hasattr(user, 'shop') and not user.groups.exists()),
        }

        if dashboard in destinations and destinations[dashboard][1]():
            return reverse(destinations[dashboard][0])

        return reverse('dashboard_redirect')
from .forms import PurchaseForm
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Sum

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count

from .models import Lead, CallLog
from ai_engine.predict import predict_lead


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

@login_required
def dashboard_redirect(request):

    user = request.user

    if user.is_superuser:
        return redirect('superuser_dashboard')

    if user.groups.filter(name='Lead Manager').exists():
        return redirect('lead_dashboard')

    if user.groups.filter(name='Document Manager').exists():
        return redirect('document_dashboard')

    if user.groups.filter(name='Bank Manager').exists():
        return redirect('bank_dashboard')

    if hasattr(user, 'shop'):
        return redirect('dashboard')

    return redirect('lead_dashboard')


def _is_role_user(user):
    """Return True if the user is a role-based staff (not a shop owner)."""
    return user.groups.filter(
        name__in=['Lead Manager', 'Document Manager', 'Bank Manager']
    ).exists()


def _role_redirect(user):
    """Redirect a role user back to their own dashboard."""
    if user.groups.filter(name='Lead Manager').exists():
        return redirect('lead_dashboard')
    if user.groups.filter(name='Document Manager').exists():
        return redirect('document_dashboard')
    if user.groups.filter(name='Bank Manager').exists():
        return redirect('bank_dashboard')
    return redirect('login')

def dashboard(request):

    if request.user.is_superuser:
        return redirect('superuser_dashboard')

    if is_lead_manager(request.user):
        return redirect('lead_dashboard')

    if is_document_manager(request.user):
        return redirect('document_dashboard')

    if is_bank_manager(request.user):
        return redirect('bank_dashboard')

    shop = get_user_shop(request.user)

    if not shop:
        return redirect('shop_register')

    context = {
        'total_customers': Customer.objects.filter(shop=shop).count(),
        'total_revenue': Purchase.objects.filter(
            lead__shop=shop
        ).aggregate(
                total=Sum('amount')
            )['total'] or 0,
        'total_leads': Lead.objects.filter(shop=shop).count(),

        'pending_followups': FollowUp.objects.filter(
            lead__shop=shop,
            is_completed=False
        ).count(),

        'total_purchases': Purchase.objects.filter(
            lead__shop=shop
        ).count(),
    }

    return render(request, 'crm/dashboard.html', context)

@login_required
def ai_predictions(request):

    # Role-based staff cannot access AI predictions
    if _is_role_user(request.user):
        return _role_redirect(request.user)

    shop = get_user_shop(request.user)
    if not shop:
        return redirect('shop_register')

    leads = Lead.objects.select_related(
        'customer',
        'product'
    ).filter(shop=shop).exclude(
        status__in=['CONVERTED', 'LOST']
    )

    today = timezone.localdate()

    results = []

    for lead in leads:

        # Count customer visits represented by recorded leads.
        customer_visits = Lead.objects.filter(
            shop=shop,
            customer=lead.customer
        ).count()

        # Days since last recorded lead.
        days_since_last_visit = (
            today - lead.created_at.date()
        ).days

        # Number of recorded calls for this lead.
        followup_count = CallLog.objects.filter(
            lead=lead
        ).count()

        # Map status to a numeric interest level.
        interest_mapping = {
            'NEW': 1,
            'INTERESTED': 2,
            'FOLLOWUP': 2,
            'RETURNED': 3,
            'DOCUMENT': 3,
            'BANK': 3,
        }

        interest_level = interest_mapping.get(
            lead.status,
            1
        )

        product_price = float(
            lead.product.price if lead.product else 0
        )

        prediction = predict_lead(
            customer_visits,
            days_since_last_visit,
            followup_count,
            interest_level,
            product_price
        )

        results.append({
            'lead': lead,
            'prediction': prediction['prediction'],
            'probability': prediction['probability'],
        })

    results.sort(
        key=lambda item: item['probability'],
        reverse=True
    )

    return render(
        request,
        'crm/ai_predictions.html',
        {
            'results': results
        }
    ) 

@login_required
def customers(request):

    shop = get_user_shop(request.user)
    is_lead_mgr = not request.user.is_superuser and request.user.groups.filter(name='Lead Manager').exists()

    if is_lead_mgr:
        # A Lead Manager ONLY sees customers associated with their assigned leads
        customer_list = Customer.objects.filter(
            shop=shop,
            lead__assigned_to=request.user
        ).distinct().order_by('-created_at')
    else:
        staff_id = request.GET.get('staff_id')
        if staff_id:
            customer_list = Customer.objects.filter(
                shop=shop,
                lead__assigned_to_id=staff_id
            ).distinct().order_by('-created_at')
        else:
            customer_list = Customer.objects.filter(
                shop=shop
            ).order_by('-created_at')

    search = request.GET.get('search')

    if search:
        customer_list = customer_list.filter(
            name__icontains=search
        )

    context = {
        'customers': customer_list,
        'total_customers': customer_list.count()
    }

    return render(request, 'crm/customers.html', context)

@login_required
def add_customer(request):

    shop = get_user_shop(request.user)
    if not shop:
        return redirect('shop_register')

    if request.method == 'POST':

        form = CustomerForm(request.POST)

        if form.is_valid():

            customer = form.save(commit=False)
            customer.shop = shop
            customer.save()

            return redirect('customers')

    else:
        form = CustomerForm()

    return render(request, 'crm/customer_form.html', {
        'form': form
    })

@login_required
def products(request):

    # Role-based staff cannot access this page
    if _is_role_user(request.user):
        return _role_redirect(request.user)

    product_list = Product.objects.filter(
        shop=get_user_shop(request.user)
    ).order_by('-id')

    search = request.GET.get('search')

    if search:
        product_list = product_list.filter(
            name__icontains=search
        )

    return render(request, 'crm/products.html', {
        'products': product_list
    })

@login_required
def add_product(request):

    # Role-based staff cannot access this page
    if _is_role_user(request.user):
        return _role_redirect(request.user)

    shop = get_user_shop(request.user)

    if request.method == 'POST':

        form = ProductForm(request.POST)

        if form.is_valid():

            product = form.save(commit=False)
            product.shop = shop
            product.save()

            return redirect('products')

    else:
        form = ProductForm()

    return render(request, 'crm/product_form.html', {
        'form': form
    })

@login_required
def leads(request):
     
    status_choices = Lead._meta.get_field('status').choices
    shop = get_user_shop(request.user)
    is_lead_mgr = not request.user.is_superuser and request.user.groups.filter(name='Lead Manager').exists()

    if is_lead_mgr:
        # A Lead Manager ONLY sees leads assigned to their Lead Dashboard
        lead_list = Lead.objects.select_related(
            'customer', 'product', 'assigned_to', 'bankapplication'
        ).prefetch_related(
            'customerdocument_set'
        ).filter(
            shop=shop,
            assigned_to=request.user
        ).order_by('-created_at')
        filter_staff = None
    else:
        lead_list = Lead.objects.select_related(
            'customer', 'product', 'assigned_to', 'bankapplication'
        ).prefetch_related(
            'customerdocument_set'
        ).filter(
            shop=shop
        ).order_by('-created_at')
        staff_id = request.GET.get('staff_id')
        if staff_id:
            lead_list = lead_list.filter(assigned_to_id=staff_id)
            filter_staff = User.objects.filter(id=staff_id).first()
        else:
            filter_staff = None

    search = request.GET.get('search')

    if search:
        lead_list = lead_list.filter(
            customer__name__icontains=search
        )

    context = {
        'leads': lead_list,
        'total_leads': lead_list.count(), 
        'status_choices': status_choices,
        'filter_staff': filter_staff,
    }

    return render(
        request,
        'crm/leads.html',
        context
    )



@login_required
def add_lead(request):

    shop = get_user_shop(request.user)
    if not shop:
        return redirect('shop_register')

    is_lead_mgr = not request.user.is_superuser and request.user.groups.filter(name='Lead Manager').exists()

    if request.method == 'POST':

        form = LeadForm(
            request.POST,
            shop=shop,
            is_lead_manager=is_lead_mgr
        )

        if form.is_valid():

            lead = form.save(commit=False)
            lead.shop = shop
            # If created by a Lead Manager, automatically assign to themselves
            if is_lead_mgr:
                lead.assigned_to = request.user
            lead.save()

            # Automatically create reminder
            if lead.expected_purchase_date:

                FollowUp.objects.create(
                    lead=lead,
                    reminder_date=lead.expected_purchase_date,
                    message="Contact customer about expected purchase.",
                    is_completed=False
                )

            return redirect('leads')

    else:
        initial = {}
        assigned_to_param = request.GET.get('assigned_to')
        if assigned_to_param:
            initial['assigned_to'] = assigned_to_param
        elif is_lead_mgr:
            initial['assigned_to'] = request.user.id

        form = LeadForm(
            shop=shop,
            is_lead_manager=is_lead_mgr,
            initial=initial
        )

    return render(
        request,
        'crm/lead_form.html',
        {'form': form}
    )

@login_required
def delete_lead(request, lead_id):

    lead = get_object_or_404(
        Lead, id=lead_id, shop=get_user_shop(request.user)
    )

    if request.method == 'POST':
        lead.delete()

        messages.success(
            request,
            'Lead deleted successfully!'
        )

    return redirect('leads')



@login_required
def update_lead_status(request, lead_id):

    lead = get_object_or_404(
        Lead, id=lead_id, shop=get_user_shop(request.user)
    )

    if request.method == 'POST':

        new_status = request.POST.get('status')

        valid_statuses = dict(
            Lead._meta.get_field('status').choices
        )

        if new_status in valid_statuses:

            lead.status = new_status
            lead.save(update_fields=['status'])
            messages.success(request, 'Lead status updated successfully!')
        else:
            messages.error(request, 'Invalid status selected!')

    return redirect('leads')

 


@login_required
def followups(request):

    today = timezone.localdate()
    shop = get_user_shop(request.user)
    is_lead_mgr = not request.user.is_superuser and request.user.groups.filter(name='Lead Manager').exists()

    all_followups = FollowUp.objects.select_related(
        'lead__customer',
        'lead__product'
    ).filter(
        lead__shop=shop
    )

    if is_lead_mgr:
        all_followups = all_followups.filter(lead__assigned_to=request.user)

    all_followups = all_followups.order_by('reminder_date')

    pending = all_followups.filter(
        is_completed=False
    )

    overdue = pending.filter(
        reminder_date__lt=today
    )

    today_followups = pending.filter(
        reminder_date=today
    )

    upcoming = pending.filter(
        reminder_date__gt=today
    )

    context = {
        'overdue': overdue,
        'today_followups': today_followups,
        'upcoming': upcoming,
        'total_pending': pending.count(),
    }

    return render(
        request,
        'crm/followups.html',
        context
    )


@login_required
def complete_followup(request, followup_id):

    followup = get_object_or_404(
        FollowUp, id=followup_id, lead__shop=get_user_shop(request.user)
    )

    if request.method == 'POST':

        followup.is_completed = True
        followup.save(update_fields=['is_completed'])

    return redirect('followups')


@login_required
def move_followup_today(request, followup_id):

    followup = get_object_or_404(
        FollowUp, id=followup_id, lead__shop=get_user_shop(request.user)
    )

    if request.method == 'POST':
        followup.reminder_date = timezone.localdate()
        followup.save(update_fields=['reminder_date'])
        messages.success(
            request,
            f"Follow-up for {followup.lead.customer.name} moved to Today's Follow-ups!"
        )

    return redirect('followups')


@login_required
def add_call_log(request, lead_id):

    lead = get_object_or_404(
        Lead, id=lead_id, shop=get_user_shop(request.user)
    )

    if request.method == 'POST':

        remarks = request.POST.get('remarks', '').strip()
        next_date = request.POST.get('next_followup') or None

        if remarks:

            CallLog.objects.create(
                lead=lead,
                remarks=remarks,
                next_followup=next_date
            )

            # Create another reminder if a date is selected
            if next_date:

                FollowUp.objects.create(
                    lead=lead,
                    reminder_date=next_date,
                    message="Scheduled after customer call.",
                    is_completed=False
                )

            return redirect('followups')

    return render(
        request,
        'crm/call_form.html',
        {'lead': lead}
    )


@login_required
def documents(request):

    lead_id = request.GET.get('lead_id')

    leads = Lead.objects.select_related(
        'customer', 'product'
    ).filter(shop=get_user_shop(request.user))

    selected_lead = None

    if lead_id:
        selected_lead = get_object_or_404(
            Lead,
            id=lead_id,
            shop=get_user_shop(request.user)
        )

        document_list = CustomerDocument.objects.filter(
            lead=selected_lead
        )
    else:
        document_list = CustomerDocument.objects.filter(
            lead__shop=get_user_shop(request.user)
        )

    context = {
        'documents': document_list,
        'leads': leads,
        'selected_lead': selected_lead,
    }

    return render(request, 'crm/documents.html', context)

@login_required
def upload_document(request):

    if request.method == 'POST':

        lead_id = request.POST.get('lead_id')

        lead = get_object_or_404(
            Lead,
            id=lead_id,
            shop=get_user_shop(request.user)
        )

        form = DocumentForm(request.POST, request.FILES)

        if form.is_valid():

            document = form.save(commit=False)
            document.lead = lead
            document.save()

            messages.success(
                request,
                'Document uploaded successfully!'
            )

            return redirect(f'/documents/?lead_id={lead.id}')

    else:
        form = DocumentForm()

    leads = Lead.objects.filter(shop=get_user_shop(request.user))

    return render(request, 'crm/document_form.html', {
        'form': form,
        'leads': leads,
        'selected_lead_id': request.GET.get('lead_id', '')
    })

@login_required
def update_document_status(request, document_id):

    document = get_object_or_404(
        CustomerDocument,
        id=document_id,
        lead__shop=get_user_shop(request.user)
    )

    if request.method == 'POST':

        new_status = request.POST.get('status')

        status_choices = dict(
            CustomerDocument._meta.get_field('status').choices
        )

        if new_status in status_choices:

            document.status = new_status
            document.save(update_fields=['status'])

            # Automatically reflect document verification progress on the Lead
            lead = document.lead
            if new_status == 'VERIFIED' and lead.status not in ('CONVERTED', 'LOST'):
                lead.status = 'DOCUMENT'
                lead.save(update_fields=['status'])
            elif new_status in ('PENDING', 'CORRECTION') and lead.status not in ('CONVERTED', 'LOST', 'BANK'):
                lead.status = 'DOCUMENT'
                lead.save(update_fields=['status'])

            messages.success(
                request,
                f'Document status updated to {status_choices[new_status]}! Update reflected on Lead Dashboard.'
            )
        else:
            messages.error(request, 'Invalid document status!')

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('documents')


@login_required
def banks(request):

    # Only bank managers, superusers and shop owners can access
    if request.user.groups.filter(name='Lead Manager').exists() or \
       request.user.groups.filter(name='Document Manager').exists():
        return _role_redirect(request.user)

    applications = BankApplication.objects.select_related(
        'lead__customer',
        'lead__product'
    ).filter(
        lead__shop=get_user_shop(request.user)
    ).order_by('-id')

    context = {
        'applications': applications,
        'total_applications': applications.count(),
        'pending_count': applications.filter(
            status='PENDING'
        ).count(),
        'approved_count': applications.filter(
            status='APPROVED'
        ).count(),
        'rejected_count': applications.filter(
            status='REJECTED'
        ).count(),
    }

    return render(
        request,
        'crm/banks.html',
        context
    )

@login_required
def add_bank_application(request, lead_id):

    lead = get_object_or_404(
        Lead,
        id=lead_id,
        shop=get_user_shop(request.user)
    )

    if BankApplication.objects.filter(lead=lead).exists():
        messages.warning(
            request,
            'A bank application already exists for this lead.'
        )
        return redirect('banks')

    if request.method == 'POST':

        form = BankApplicationForm(request.POST)

        if form.is_valid():

            application = form.save(commit=False)
            application.lead = lead
            application.save()

            lead.status = 'BANK'
            lead.save(update_fields=['status'])

            messages.success(
                request,
                'Bank application created successfully.'
            )

            return redirect('banks')

    else:
        form = BankApplicationForm()

    return render(
        request,
        'crm/bank_form.html',
        {
            'form': form,
            'lead': lead
        }
    )

@login_required
def update_bank_status(request, application_id):

    application = get_object_or_404(
        BankApplication,
        id=application_id,
        lead__shop=get_user_shop(request.user)
    )

    if request.method == 'POST':

        new_status = request.POST.get('status')

        valid_statuses = dict(BankApplication.STATUS_CHOICES)

        if new_status in valid_statuses:

            application.status = new_status

            application.save(
                update_fields=['status']
            )

            # Automatically reflect bank progress on the Lead
            lead = application.lead
            if new_status in ('APPROVED', 'REVIEW', 'PENDING') and lead.status not in ('CONVERTED', 'LOST'):
                lead.status = 'BANK'
                lead.save(update_fields=['status'])

            messages.success(
                request,
                f'Bank application status updated to {valid_statuses.get(new_status, new_status)}! Update reflected on Lead Dashboard.'
            )

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('banks')


@login_required
def purchases(request):

    # Role-based staff cannot access purchases
    if _is_role_user(request.user):
        return _role_redirect(request.user)

    purchase_list = Purchase.objects.select_related(
        'lead__customer',
        'lead__product'
    ).filter(
        lead__shop=get_user_shop(request.user)
    ).order_by('-purchase_date')

    total_revenue = purchase_list.aggregate(
        total=Sum('amount')
    )['total'] or 0

    context = {
        'purchases': purchase_list,
        'total_purchases': purchase_list.count(),
        'total_revenue': total_revenue,
    }

    return render(
        request,
        'crm/purchases.html',
        context
    )

@login_required
def add_purchase(request, lead_id):

    # Role-based staff cannot access purchases
    if _is_role_user(request.user):
        return _role_redirect(request.user)

    lead = get_object_or_404(
        Lead,
        id=lead_id,
        shop=get_user_shop(request.user)
    )

    # Prevent duplicate purchases
    if Purchase.objects.filter(lead=lead).exists():

        messages.warning(
            request,
            'A purchase is already recorded for this lead.'
        )

        return redirect('purchases')

    if request.method == 'POST':

        form = PurchaseForm(request.POST)

        if form.is_valid():

            with transaction.atomic():

                purchase = form.save(commit=False)
                purchase.lead = lead
                purchase.save()

                lead.status = 'CONVERTED'
                lead.save(update_fields=['status'])

            messages.success(
                request,
                'Purchase recorded successfully!'
            )

            return redirect('purchases')

    else:

        form = PurchaseForm()

    return render(
        request,
        'crm/purchase_form.html',
        {
            'form': form,
            'lead': lead
        }
    )


@login_required
def purchase_detail(request, purchase_id):

    purchase = get_object_or_404(
        Purchase,
        id=purchase_id,
        lead__shop=get_user_shop(request.user)
    )

    return render(
        request,
        'crm/purchase_detail.html',
        {
            'purchase': purchase
        }
    )

@login_required
def reports(request):
    if _is_role_user(request.user):
        return _role_redirect(request.user)

    shop = get_user_shop(request.user)
    if not shop:
        return redirect('shop_register')

    today = timezone.localdate()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    try:
        start_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else today.replace(day=1)
    except ValueError:
        start_date = today.replace(day=1)

    try:
        end_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else today
    except ValueError:
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    purchases = Purchase.objects.filter(
        lead__shop=shop,
        purchase_date__gte=start_date,
        purchase_date__lte=end_date,
    ).select_related('lead__customer', 'lead__product')

    customers = Customer.objects.filter(
        shop=shop,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    leads = Lead.objects.filter(
        shop=shop,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )

    lead_status_counts = list(
        leads.values('status').annotate(count=Count('id')).order_by('-count')
    )
    lead_status_map = dict(Lead.STATUS)
    for item in lead_status_counts:
        item['label'] = lead_status_map.get(item['status'], item['status'])

    document_status_counts = list(
        CustomerDocument.objects.filter(
            lead__shop=shop,
            lead__created_at__date__gte=start_date,
            lead__created_at__date__lte=end_date,
        ).values('status').annotate(count=Count('id')).order_by('-count')
    )
    document_status_map = dict(CustomerDocument.STATUS_CHOICES)
    for item in document_status_counts:
        item['label'] = document_status_map.get(item['status'], item['status'])

    bank_status_counts = list(
        BankApplication.objects.filter(
            lead__shop=shop,
            lead__created_at__date__gte=start_date,
            lead__created_at__date__lte=end_date,
        ).values('status').annotate(count=Count('id')).order_by('-count')
    )
    bank_status_map = dict(BankApplication.STATUS_CHOICES)
    for item in bank_status_counts:
        item['label'] = bank_status_map.get(item['status'], item['status'])

    revenue = purchases.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'date_from': start_date.isoformat(),
        'date_to': end_date.isoformat(),
        'total_customers': customers.count(),
        'total_leads': leads.count(),
        'total_purchases': purchases.count(),
        'total_revenue': revenue,
        'pending_followups': FollowUp.objects.filter(
            lead__shop=shop,
            is_completed=False,
            reminder_date__gte=start_date,
            reminder_date__lte=end_date,
        ).count(),
        'lead_status_counts': lead_status_counts,
        'document_status_counts': document_status_counts,
        'bank_status_counts': bank_status_counts,
        'recent_purchases': purchases.order_by('-purchase_date', '-id')[:20],
    }
    return render(request, 'crm/reports.html', context)

def signup(request):

    if request.method == 'POST':

        form = SignupForm(request.POST)

        if form.is_valid():

            user = form.save()
            dashboard = form.cleaned_data['dashboard']

            if dashboard == 'SUPER':
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=['is_staff', 'is_superuser'])
                login(request, user)
                messages.success(
                    request,
                    'Super Administrator account created successfully! Please set up your shop/organization.'
                )
                # Superuser goes to shop_register to create their isolated shop/tenant
                return redirect('shop_register')

            role_groups = {
                'LEAD': ('Lead Manager', 'LEAD'),
                'DOCUMENT': ('Document Manager', 'DOCUMENT'),
                'BANK': ('Bank Manager', 'BANK'),
            }
            if dashboard in role_groups:
                group_name, role_code = role_groups[dashboard]
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)
                login(request, user)
                messages.success(
                    request,
                    f'Account created! Please select which shop you belong to.'
                )
                # Role users go to staff_shop_select to link to a shop (creates StaffProfile)
                return redirect('staff_shop_select')

            login(request, user)

            messages.success(
                request,
                'Account created successfully!'
            )

            return redirect('shop_register')

    else:

        form = SignupForm()

    return render(
        request,
        'authentication/signup.html',
        {'form': form}
    )


@login_required
def shop_register(request):

    if hasattr(request.user, 'shop'):
        # Already has a shop — redirect based on role
        if request.user.is_superuser:
            return redirect('superuser_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':

        form = ShopForm(request.POST)

        if form.is_valid():

            shop = form.save(commit=False)

            shop.owner = request.user

            shop.save()

            messages.success(
                request,
                'Shop registered successfully!'
            )

            # Superusers go to their own dashboard; shop owners to the main dashboard
            if request.user.is_superuser:
                return redirect('superuser_dashboard')
            return redirect('dashboard')

    else:

        form = ShopForm()

    return render(
        request,
        'authentication/shop_register.html',
        {'form': form}
    )


@login_required
def staff_shop_select(request):
    """
    Shown after a Lead/Document/Bank Manager signs up.
    They select which super-admin shop they belong to, and a StaffProfile is created.
    """
    user = request.user

    # Only role users use this view
    if not _is_role_user(user):
        return redirect('dashboard_redirect')

    # Already linked to a shop → go straight to dashboard
    if hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.shop_id:
        return redirect('dashboard_redirect')

    # Determine this user's role
    role_map = {
        'Lead Manager': 'LEAD',
        'Document Manager': 'DOCUMENT',
        'Bank Manager': 'BANK',
    }
    user_role = None
    for group_name, role_code in role_map.items():
        if user.groups.filter(name=group_name).exists():
            user_role = role_code
            break

    # Only shops owned by superusers are shown as valid tenants
    all_shops = Shop.objects.filter(owner__is_superuser=True).select_related('owner')

    if request.method == 'POST':
        shop_id = request.POST.get('shop_id')
        shop = Shop.objects.filter(id=shop_id, owner__is_superuser=True).first()
        if shop and user_role:
            StaffProfile.objects.update_or_create(
                user=user,
                defaults={'shop': shop, 'role': user_role}
            )
            messages.success(request, f'You are now linked to shop: {shop.name}')
            return redirect('dashboard_redirect')
        else:
            messages.error(request, 'Invalid shop selected.')

    return render(request, 'authentication/staff_shop_select.html', {
        'shops': all_shops,
        'user_role': user_role,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def create_lead_dashboard_user(request):
    """
    Called from inside Super Dashboard to create a new Lead Dashboard user.
    The new Lead Manager is automatically associated with this Super Dashboard's shop.
    """
    shop = get_user_shop(request.user)
    if not shop:
        messages.error(request, 'Please register your shop before creating Lead Dashboards.')
        return redirect('shop_register')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('superuser_dashboard')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return redirect('superuser_dashboard')

        new_user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        group, _ = Group.objects.get_or_create(name='Lead Manager')
        new_user.groups.add(group)

        StaffProfile.objects.create(
            user=new_user,
            shop=shop,
            role='LEAD'
        )

        messages.success(
            request,
            f'Lead Dashboard for "{username}" created and automatically added to your dashboard!'
        )

    return redirect('superuser_dashboard')


@login_required
def logout_user(request):

    if request.method == 'POST':

        logout(request)

    return redirect('login')



from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.shortcuts import render
from django.db.models import Count, Sum

from .models import (
    Shop,
    Customer,
    Lead,
    CustomerDocument,
    BankApplication,
    Purchase,
    StaffProfile,
    DashboardAccessCode
)


def get_user_shop(user):
    """
    Returns the Shop for the given user.
    - Staff/role users → their StaffProfile.shop
    - Superusers / shop owners → user.shop (created in shop_register)
    - If no shop is set up yet, returns None safely.
    """
    # Staff member (Lead Manager, Document Manager, Bank Manager)
    try:
        if hasattr(user, 'staff_profile') and user.staff_profile and user.staff_profile.shop_id:
            return user.staff_profile.shop
    except Exception:
        pass

    # Shop owner or superuser with their own shop
    try:
        if hasattr(user, 'shop') and user.shop:
            return user.shop
    except Exception:
        pass

    return None


def is_lead_manager(user):
    return user.is_superuser or user.groups.filter(
        name='Lead Manager'
    ).exists()


def is_document_manager(user):
    return user.is_superuser or user.groups.filter(
        name='Document Manager'
    ).exists()


def is_bank_manager(user):
    return user.is_superuser or user.groups.filter(
        name='Bank Manager'
    ).exists()
    
    
    
@login_required
@user_passes_test(lambda user: user.is_superuser)
def superuser_dashboard(request):

    # Ensure all static codes exist with their default static values
    for d_val, default_code in STATIC_DASHBOARD_CODES.items():
        if not DashboardAccessCode.objects.filter(dashboard=d_val).exists():
            DashboardAccessCode.objects.create(
                dashboard=d_val,
                code=default_code,
                is_active=True
            )

    if request.method == 'POST':
        dashboard = request.POST.get('dashboard')
        custom_code = request.POST.get('custom_code', '').strip().upper()
        valid_dashboards = dict(DashboardAccessCode.DASHBOARD_CHOICES)
        if dashboard in valid_dashboards:
            # Set to custom code if provided, otherwise restore default static code
            code_val = custom_code or STATIC_DASHBOARD_CODES.get(dashboard, 'CODE')
            try:
                set_dashboard_access_code(dashboard, code_val)
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
            except IntegrityError:
                messages.error(request, 'This access key is already in use.')
            else:
                messages.success(request, f'{valid_dashboards[dashboard]} static code set to {code_val}.')
        return redirect('superuser_dashboard')

    shop = get_user_shop(request.user)

    # Safely scope all queries to this super admin's own shop
    if shop:
        customers = Customer.objects.filter(shop=shop)
        leads = Lead.objects.filter(shop=shop)
        documents = CustomerDocument.objects.filter(lead__shop=shop)
        applications = BankApplication.objects.filter(lead__shop=shop)
        purchases = Purchase.objects.filter(lead__shop=shop)
        # Staff users whose StaffProfile is linked to this shop
        staff_profiles = StaffProfile.objects.filter(shop=shop).select_related('user')
        lead_staff_users = list(staff_profiles.filter(role='LEAD'))
        for sp in lead_staff_users:
            sp.assigned_leads_count = Lead.objects.filter(shop=shop, assigned_to=sp.user).count()
            sp.assigned_customers_count = Customer.objects.filter(shop=shop, lead__assigned_to=sp.user).distinct().count()
    else:
        # New super admin — no shop yet, all data shows zero
        customers = Customer.objects.none()
        leads = Lead.objects.none()
        documents = CustomerDocument.objects.none()
        applications = BankApplication.objects.none()
        purchases = Purchase.objects.none()
        staff_profiles = StaffProfile.objects.none()
        lead_staff_users = []

    context = {
        'shop': shop,
        'total_shops': 1 if shop else 0,
        'total_customers': customers.count(),
        'total_leads': leads.count(),
        'total_documents': documents.count(),
        'total_bank_applications': applications.count(),
        'total_purchases': purchases.count(),
        'total_users': staff_profiles.count(),

        # ── Lead Dashboard matching stats ──
        'new_leads': leads.filter(status='NEW').count(),
        'followup_leads': leads.filter(status='FOLLOWUP').count(),
        'converted_leads': leads.filter(status='CONVERTED').count(),
        'interested_leads': leads.filter(status='INTERESTED').count(),
        'lost_leads': leads.filter(status='LOST').count(),

        # ── Document Dashboard matching stats ──
        'pending_documents': documents.filter(status='PENDING').count(),
        'verified_documents': documents.filter(status='VERIFIED').count(),
        'rejected_documents': documents.filter(status='REJECTED').count(),
        'correction_documents': documents.filter(status='CORRECTION').count(),

        # ── Bank Dashboard matching stats ──
        'pending_applications': applications.filter(status='PENDING').count(),
        'review_applications': applications.filter(status='REVIEW').count(),
        'approved_applications': applications.filter(status='APPROVED').count(),
        'rejected_applications': applications.filter(status='REJECTED').count(),
        'total_loan_amount': applications.aggregate(total=Sum('loan_amount'))['total'] or 0,

        # ── Purchases matching stats ──
        'total_revenue': purchases.aggregate(total=Sum('amount'))['total'] or 0,

        'customers': customers.select_related('shop').order_by('-created_at'),

        # ── Staff users associated with this super dashboard's shop ──
        'lead_staff_users': lead_staff_users,
        'document_staff_users': staff_profiles.filter(role='DOCUMENT'),
        'bank_staff_users': staff_profiles.filter(role='BANK'),

        'dashboard_choices': [
            (value, label, DashboardAccessCode.objects.filter(dashboard=value, is_active=True).first())
            for value, label in DashboardAccessCode.DASHBOARD_CHOICES
        ],
    }

    return render(
        request,
        'dashboards/superuser_dashboard.html',
        context
    )
    
    
    

@login_required
@user_passes_test(is_lead_manager)
def lead_dashboard(request):

    shop = get_user_shop(request.user)
    if not shop:
        return render(request, 'dashboards/lead_dashboard.html', {
            'total_customers': 0,
            'total_leads': 0,
            'new_leads': 0,
            'followup_leads': 0,
            'converted_leads': 0,
            'total_docs': 0,
            'verified_docs': 0,
            'pending_docs': 0,
            'rejected_docs': 0,
            'total_banks': 0,
            'approved_banks': 0,
            'review_banks': 0,
            'pending_banks': 0,
            'lead_dashboard_name': None,
        })

    is_lead_mgr = not request.user.is_superuser and request.user.groups.filter(name='Lead Manager').exists()

    if is_lead_mgr:
        # A Lead Manager ONLY sees leads and customers assigned to their Lead Dashboard!
        leads = Lead.objects.filter(shop=shop, assigned_to=request.user)
        customers = Customer.objects.filter(shop=shop, lead__assigned_to=request.user).distinct()
        lead_dashboard_name = request.user.username
        selected_staff = None
    else:
        # Superuser can see all leads or filter by a specific Lead Dashboard via ?staff_id=...
        staff_id = request.GET.get('staff_id')
        if staff_id:
            leads = Lead.objects.filter(shop=shop, assigned_to_id=staff_id)
            customers = Customer.objects.filter(shop=shop, lead__assigned_to_id=staff_id).distinct()
            selected_staff = User.objects.filter(id=staff_id).first()
            lead_dashboard_name = selected_staff.username if selected_staff else "Selected Lead Dashboard"
        else:
            leads = Lead.objects.filter(shop=shop)
            customers = Customer.objects.filter(shop=shop)
            selected_staff = None
            lead_dashboard_name = "All Lead Dashboards"

    all_lead_dashboards = StaffProfile.objects.filter(shop=shop, role='LEAD').select_related('user')

    # Document stats for leads in this dashboard
    total_docs = CustomerDocument.objects.filter(lead__in=leads).count()
    verified_docs = CustomerDocument.objects.filter(lead__in=leads, status='VERIFIED').count()
    pending_docs = CustomerDocument.objects.filter(lead__in=leads, status='PENDING').count()
    rejected_docs = CustomerDocument.objects.filter(lead__in=leads, status='REJECTED').count()

    # Bank stats for leads in this dashboard
    total_banks = BankApplication.objects.filter(lead__in=leads).count()
    approved_banks = BankApplication.objects.filter(lead__in=leads, status='APPROVED').count()
    review_banks = BankApplication.objects.filter(lead__in=leads, status='REVIEW').count()
    pending_banks = BankApplication.objects.filter(lead__in=leads, status='PENDING').count()

    context = {
        'total_customers': customers.count(),
        'total_leads': leads.count(),
        'new_leads': leads.filter(status='NEW').count(),
        'followup_leads': leads.filter(status='FOLLOWUP').count(),
        'converted_leads': leads.filter(status='CONVERTED').count(),
        'total_docs': total_docs,
        'verified_docs': verified_docs,
        'pending_docs': pending_docs,
        'rejected_docs': rejected_docs,
        'total_banks': total_banks,
        'approved_banks': approved_banks,
        'review_banks': review_banks,
        'pending_banks': pending_banks,
        'lead_dashboard_name': lead_dashboard_name,
        'selected_staff': selected_staff,
        'all_lead_dashboards': all_lead_dashboards,
        'is_lead_manager': is_lead_mgr,
        'leads_list': leads.select_related('customer', 'product', 'assigned_to', 'bankapplication').prefetch_related('customerdocument_set').order_by('-created_at')[:15],
    }

    return render(
        request,
        'dashboards/lead_dashboard.html',
        context
    )



@login_required
@user_passes_test(is_document_manager)
def document_dashboard(request):

    documents = CustomerDocument.objects.filter(
        lead__shop=get_user_shop(request.user)
    )

    context = {
        'total_documents': documents.count(),

        'pending_documents': documents.filter(
            status='PENDING'
        ).count(),

        'verified_documents': documents.filter(
            status='VERIFIED'
        ).count(),

        'rejected_documents': documents.filter(
            status='REJECTED'
        ).count(),

        'correction_documents': documents.filter(
            status='CORRECTION'
        ).count(),
    }

    return render(
        request,
        'dashboards/document_dashboard.html',
        context
    )
    
    
    

@login_required
@user_passes_test(is_bank_manager)
def bank_dashboard(request):

    applications = BankApplication.objects.filter(
        lead__shop=get_user_shop(request.user)
    )

    context = {
        'total_applications': applications.count(),

        'pending_applications': applications.filter(
            status='PENDING'
        ).count(),

        'review_applications': applications.filter(
            status='REVIEW'
        ).count(),

        'approved_applications': applications.filter(
            status='APPROVED'
        ).count(),

        'rejected_applications': applications.filter(
            status='REJECTED'
        ).count(),

        'total_loan_amount': applications.aggregate(
            total=Sum('loan_amount')
        )['total'] or 0,
    }

    return render(
        request,
        'dashboards/bank_dashboard.html',
        context
    )


@login_required
def settings_view(request):
    user = request.user
    shop = get_user_shop(user)
    is_admin_or_owner = user.is_superuser or hasattr(user, 'shop')

    profile_form = UserProfileForm(instance=user)
    shop_form = ShopForm(instance=shop) if (shop and is_admin_or_owner) else None
    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = UserProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile information updated successfully!')
                return redirect('settings')
            else:
                messages.error(request, 'Please correct the errors in profile form.')

        elif action == 'update_shop' and shop and is_admin_or_owner:
            shop_form = ShopForm(request.POST, instance=shop)
            if shop_form.is_valid():
                shop_form.save()
                messages.success(request, 'Shop details updated successfully!')
                return redirect('settings')
            else:
                messages.error(request, 'Please correct the errors in shop details.')

        elif action == 'change_password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user_updated = password_form.save()
                update_session_auth_hash(request, user_updated)
                messages.success(request, 'Password changed successfully!')
                return redirect('settings')
            else:
                messages.error(request, 'Failed to update password. Please check requirements.')

        elif action == 'update_code' and user.is_superuser:
            dashboard = request.POST.get('dashboard')
            custom_code = request.POST.get('custom_code', '').strip().upper()
            valid_dashboards = dict(DashboardAccessCode.DASHBOARD_CHOICES)
            if dashboard in valid_dashboards and custom_code:
                try:
                    set_dashboard_access_code(dashboard, custom_code)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                except IntegrityError:
                    messages.error(request, 'This access key is already in use.')
                else:
                    messages.success(request, f'{valid_dashboards[dashboard]} Access Key updated to {custom_code}!')
                    return redirect('settings')

    # Codes for superuser
    access_codes = []
    if user.is_superuser:
        for val, label in DashboardAccessCode.DASHBOARD_CHOICES:
            code_obj = DashboardAccessCode.objects.filter(dashboard=val, is_active=True).first()
            access_codes.append((val, label, code_obj.code if code_obj else STATIC_DASHBOARD_CODES.get(val, '')))

    # Staff list for superuser
    staff_list = []
    if user.is_superuser and shop:
        staff_list = StaffProfile.objects.filter(shop=shop).select_related('user')

    context = {
        'profile_form': profile_form,
        'shop_form': shop_form,
        'password_form': password_form,
        'shop': shop,
        'is_admin_or_owner': is_admin_or_owner,
        'access_codes': access_codes,
        'staff_list': staff_list,
    }

    return render(request, 'crm/settings.html', context)
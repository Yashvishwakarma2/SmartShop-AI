from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication
    path('signup/', views.signup, name='signup'),
    path('', views.DashboardLoginView.as_view(
        template_name='authentication/login.html'
    ), name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('shop-register/', views.shop_register, name='shop_register'),
    path('staff-shop-select/', views.staff_shop_select, name='staff_shop_select'),
    path('create-lead-dashboard/', views.create_lead_dashboard_user, name='create_lead_dashboard_user'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Other modules (temporary routes)
    path('customers/', views.customers, name='customers'),
    path('products/', views.products, name='products'),
    path('leads/', views.leads, name='leads'),
    path('followups/', views.followups, name='followups'),
    path('documents/', views.documents, name='documents'),
    path('banks/', views.banks, name='banks'),
    path('purchases/', views.purchases, name='purchases'),
    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings_view, name='settings'),
    
    path('customers/add/', views.add_customer, name='add_customer'),
    path('products/add/', views.add_product, name='add_product'),
    
    path('leads/', views.leads, name='leads'),

    path('leads/add/', views.add_lead, name='add_lead'),

    
    path('leads/<int:lead_id>/update-status/', views.update_lead_status, name='update_lead_status'),
    path('followups/', views.followups, name='followups'),

    path('followups/<int:followup_id>/complete/', views.complete_followup, name='complete_followup'),
    path('followups/<int:followup_id>/today/', views.move_followup_today, name='move_followup_today'),

    path('leads/<int:lead_id>/call/',views.add_call_log,name='add_call_log'),
    path('documents/', views.documents, name='documents'),

    path('leads/<int:lead_id>/upload-document/', views.upload_document,name='upload_document'),
    path('documents/<int:document_id>/update/',views.update_document_status,name='update_document_status'),
    path('banks/', views.banks, name='banks'),

path('leads/<int:lead_id>/bank-application/',views.add_bank_application, name='add_bank_application'),

path('banks/<int:application_id>/update/',views.update_bank_status,name='update_bank_status'),

path('purchases/', views.purchases, name='purchases'),

path(
    'leads/<int:lead_id>/purchase/',
    views.add_purchase,
    name='add_purchase'
),

path(
    'purchases/<int:purchase_id>/',
    views.purchase_detail,
    name='purchase_detail'
),

path(
    'ai-predictions/',
    views.ai_predictions,
    name='ai_predictions'
),

path('documents/', views.documents, name='documents'),

path('documents/upload/', views.upload_document,
     name='upload_document'),

path(
    'documents/<int:document_id>/update-status/',
    views.update_document_status,
    name='update_document_status'
),

path(
    'leads/<int:lead_id>/delete/',
    views.delete_lead,
    name='delete_lead'
),

# Separate Dashboard URLs

path(
    'superuser-dashboard/',
    views.superuser_dashboard,
    name='superuser_dashboard'
),

path(
    'lead-dashboard/',
    views.lead_dashboard,
    name='lead_dashboard'
),

path(
    'document-dashboard/',
    views.document_dashboard,
    name='document_dashboard'
),

path(
    'bank-dashboard/',
    views.bank_dashboard,
    name='bank_dashboard'
),

path(
    'dashboard-redirect/',
    views.dashboard_redirect,
    name='dashboard_redirect'
),

]
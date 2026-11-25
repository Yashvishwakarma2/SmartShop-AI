from django.contrib import admin

from .models import (
    Shop,
    Customer,
    Product,
    Lead,
    FollowUp,
    CallLog,
    CustomerDocument,
    BankApplication,
    Purchase
)
from .models import StaffProfile

admin.site.register(StaffProfile)

admin.site.register(Shop)
admin.site.register(Customer)
admin.site.register(Product)
admin.site.register(Lead)
admin.site.register(FollowUp)
admin.site.register(CallLog)
admin.site.register(CustomerDocument)
admin.site.register(BankApplication)
admin.site.register(Purchase)
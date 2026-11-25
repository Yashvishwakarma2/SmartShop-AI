from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):

    help = 'Create SmartShop AI user roles'

    def handle(self, *args, **kwargs):

        roles = [
            'Lead Manager',
            'Document Manager',
            'Bank Manager',
        ]

        for role in roles:

            group, created = Group.objects.get_or_create(
                name=role
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{role} created successfully!'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'{role} already exists.'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                'SmartShop AI roles setup completed!'
            )
        )
from django.db import migrations, models


def remove_super_access_code(apps, schema_editor):
    DashboardAccessCode = apps.get_model('crm', 'DashboardAccessCode')
    DashboardAccessCode.objects.filter(dashboard='SUPER').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0006_lead_assigned_to'),
    ]

    operations = [
        migrations.RunPython(remove_super_access_code, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='dashboardaccesscode',
            name='dashboard',
            field=models.CharField(
                choices=[
                    ('LEAD', 'Lead Dashboard'),
                    ('DOCUMENT', 'Document Dashboard'),
                    ('BANK', 'Bank Dashboard'),
                ],
                max_length=20,
                unique=True,
            ),
        ),
    ]

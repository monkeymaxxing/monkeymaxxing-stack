from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("portal", "0001_initial")]
    operations = [migrations.AddField(model_name="record", name="description", field=models.TextField(default="", db_default=""))]

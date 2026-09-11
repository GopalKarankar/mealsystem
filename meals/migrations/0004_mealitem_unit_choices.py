from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("meals", "0003_meal_meal_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mealitem",
            name="unit",
            field=models.CharField(
                max_length=50,
                default="serving",
                choices=[
                    ("g", "Grams"),
                    ("kg", "Kilograms"),
                    ("ml", "Milliliters"),
                    ("l", "Liters"),
                    ("oz", "Ounces"),
                    ("cup", "Cups"),
                    ("bowl", "Bowls"),
                    ("plate", "Plates"),
                    ("piece", "Pieces"),
                    ("serving", "Servings"),
                ],
            ),
        ),
    ]

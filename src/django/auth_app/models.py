from django.db import models

# Create your models here.


class User(models.Model):
    first_name = models.CharField(max_length=100, null=False)
    last_name = models.CharField(max_length=100, null=False)
    email = models.EmailField(unique=True, null=False)
    pin = models.CharField(
        max_length=256
    )  # Store hashed pins -- Allow nullable pin for fresh account (shouldnt be used until password is set)
    birth_date = models.DateField(blank=True, default=None, null=True)
    is_active = models.BooleanField(default=False, null=False)
    is_manager = models.BooleanField(default=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(auto_now=True, null=False)
    clocked_in = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.name

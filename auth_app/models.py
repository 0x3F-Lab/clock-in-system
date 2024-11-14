from django.db import models

# Create your models here.

class User(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=256)  # Store hashed passwords -- Allow nullable pass for fresh account (shouldnt be used until password is set)
    birth_date = models.DateField(blank=True, default=None)
    is_active = models.BooleanField(default=False)
    is_manager = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    clocked_in = models.BooleanField(default=False)

    def __str__(self):
        return self.name
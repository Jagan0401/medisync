from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('doctor', 'Doctor'),
        ('technician', 'Lab Technician'),
        ('hospital_admin', 'Hospital Admin'),
        ('platform_admin', 'Platform Admin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='doctor')
    organization = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

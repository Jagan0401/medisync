from django.db import models


class Hospital(models.Model):
    name = models.CharField(max_length=255)
    tenant_id = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

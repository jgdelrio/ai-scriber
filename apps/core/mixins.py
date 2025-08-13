"""
Mixins for views and models.
"""

from django.contrib.auth.models import User


class UserQuerySetMixin:
    """Mixin to filter querysets by user ownership."""

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class TimestampMixin:
    """Mixin to add timestamp fields to models."""

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        return super().save(*args, **kwargs)

# accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Placeholder for post-user-creation logic.
    Example future uses:
    - Send welcome email.
    - Auto-assign default permissions.
    """
    if created:
        # For now, do nothing. You can add logging or email here later.
        pass

# policies/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Policy
from .services import generate_installments


@receiver(post_save, sender=Policy)
def create_installments_on_policy_create(sender, instance: Policy, created, **kwargs):
    """
    Automatically generate an installment schedule when a new policy is created.

    Default: 4 installments (e.g., quarterly). You can change to monthly, etc.
    """
    if created:
        # Example: quarterly basis
        generate_installments(instance, num_installments=4)

from django.db.models.signals import post_save # type: ignore
from django.contrib.auth.models import User # type: ignore
from django.dispatch import receiver # type: ignore
from .models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    profile, created = Profile.objects.get_or_create(user=instance)
    profile.save()


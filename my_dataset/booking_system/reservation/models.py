from django.db import models # type: ignore
from django.contrib.auth.models import User # type: ignore
from django.utils import timezone # type: ignore


class Place(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    capacity = models.IntegerField(default=0)  # ตั้งค่าเริ่มต้นเป็น 0
    image = models.ImageField(upload_to="locations/", blank=True, null=True)  # สำหรับเก็บรูป
    def __str__(self):
        return self.name

class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='place_images/')
    created_at = models.DateTimeField(auto_now_add=True)


def user_directory_path(instance, filename):
    # เก็บไฟล์ใน media/user_<id>/<filename>
    return f'user_{instance.user.id}/{filename}'

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150, blank=True)
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default-avatar.png')

    def __str__(self):
        return self.user.username
    


class PlaceSchedule(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.place.name} | {self.date} {self.start_time}-{self.end_time}"
    



    

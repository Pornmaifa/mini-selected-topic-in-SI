from django.contrib import admin
from .models import Place, PlaceImage

class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    extra = 1  # เพิ่มช่องให้ใส่รูปได้หลายช่อง

class PlaceAdmin(admin.ModelAdmin):
    inlines = [PlaceImageInline]

admin.site.register(Place, PlaceAdmin)#ลงทะเบียนแอดมิน

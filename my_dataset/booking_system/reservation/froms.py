from django import forms # type: ignore
from django.contrib.auth.models import User # type: ignore
from .models import Profile ,PlaceSchedule, Place

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput)
    avatar = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']
        widgets = {
            "password": forms.PasswordInput(),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")

        if password != password2:
            raise forms.ValidationError("รหัสผ่านไม่ตรงกัน")

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['full_name', 'avatar']

class PlaceScheduleForm(forms.ModelForm):#ไฟล์อัพโหลด
    class Meta:
        model = PlaceSchedule
        fields = ['place', 'date', 'start_time', 'end_time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'place': forms.Select(attrs={'class': 'form-control'}),
        }
class PlaceForm(forms.ModelForm):#ไฟล์หลัก
    class Meta:
        model = Place
        fields = ['name', 'description', 'capacity', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

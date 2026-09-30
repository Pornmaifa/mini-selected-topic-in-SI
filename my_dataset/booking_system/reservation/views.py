import profile
from django.contrib import messages # type: ignore
from django.shortcuts import render, redirect # type: ignore
from django.contrib.auth.models import User # type: ignore
from django.contrib.auth import authenticate, login, logout # type: ignore
from django.contrib.auth.decorators import login_required , user_passes_test # type: ignore
from .froms  import PlaceScheduleForm, RegisterForm ,ProfileForm , PlaceForm
from .models import PlaceSchedule, Profile ,Place , PlaceImage
from django.shortcuts import render, get_object_or_404, redirect # type: ignore
from django.dispatch import receiver # type: ignore
from django.contrib.auth import get_user_model # type: ignore

@login_required
def deactivate_account_view(request):
    if request.method == "POST":
        user = request.user
        # ตั้งค่าให้บัญชีไม่ active
        user.is_active = False
        user.save()
        
        # ทำการ logout ผู้ใช้
        logout(request)
        
        messages.success(request, "บัญชีของคุณถูกปิดการใช้งานเรียบร้อยแล้ว")
        return redirect('login') 

    # ถ้าไม่ใช่ POST ให้กลับไปหน้าโปรไฟล์
    return redirect('profile')




def profile_edit_view(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "อัปเดตโปรไฟล์เรียบร้อย")
            return redirect("dashboard")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "reservation/profile_edit.html", {"form": form})

def profile_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")

        user = request.user
        if username and username != user.username:
            if User.objects.filter(username=username).exists():
                messages.error(request, "มีชื่อผู้ใช้นี้แล้ว")
                return redirect("profile")
            user.username = username

        if email:
            user.email = email

        user.save()
        messages.success(request, "อัปเดตโปรไฟล์สำเร็จ!")
        return redirect("profile")

    return render(request, "reservation/profile.html")

def dashboard_view(request):

    profile = Profile.objects.get(user=request.user)
    places = Place.objects.all()
    query = request.GET.get("q", "")  # รับค่าค้นหาจาก input

    if query:
        places = Place.objects.filter(name__icontains=query)
        if not places.exists():
            messages.warning(request, "ไม่พบสถานที่ที่ค้นหา")
    else:
        places = Place.objects.all()  # แสดงทั้งหมดถ้าไม่ได้ค้นหา

    context = {
        "profile": profile,
        "places": places,
    }
    return render(request, "reservation/dashboard.html", context)


    
def location_detail_view(request, pk):
    place = get_object_or_404(Place, pk=pk)
    schedules = PlaceSchedule.objects.filter(place=place).order_by('date', 'start_time')

    context = {
        "place": place,
        'schedules': schedules,
    }
    return render(request, 'reservation/location_detail.html', context)



def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = (form.cleaned_data['email'])
            user.set_password(form.cleaned_data['password'])
            user.save()

            
            avatar = form.cleaned_data.get('avatar')
            full_name = form.cleaned_data.get('full_name', '')
            Profile.objects.update_or_create(
                user=user,
                defaults={'avatar': avatar, 'full_name': full_name}
            )

            messages.success(request, "สมัครสมาชิกสำเร็จ!")
            return redirect("login")
        else:
            messages.error(request, "กรอกข้อมูลไม่ถูกต้อง")
    else:
        form = RegisterForm()
    return render(request, "reservation/register.html", {"form": form})

# Login
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"ยินดีต้อนรับ {user.username}!")
           
            if user.is_staff or user.is_superuser:
                return redirect("admin_dashboard")  # หน้าแดชบอร์ดแอดมิน
            else:
                return redirect("dashboard")       # หน้าแดชบอร์ดผู้ใช้
        else:
            messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            return redirect("login")

    return render(request, "reservation/login.html")


# Logout
def logout_view(request):
    logout(request)
    messages.success(request, "ออกจากระบบเรียบร้อยแล้ว")
    return redirect("login")  # redirect กลับหน้า login หลัง logout


# เช็คว่าผู้ใช้เป็น superuser หรือ staff
def admin_required(view_func):
    decorated_view_func = login_required(user_passes_test(lambda u: u.is_staff)(view_func))
    return decorated_view_func

@admin_required
def admin_dashboard_view(request):
    profile = Profile.objects.get(user=request.user)
    users = User.objects.all()
    places = Place.objects.all()
    
    context = {
        "profile": profile,
        "users": users,
        "places": places,
    }
    return render(request, "reservation/admin_dashboard.html", context)

# ลบสถานที่จากหน้าแอดมิน
@admin_required
def admin_delete_place(request, place_id):
    place = get_object_or_404(Place, id=place_id)
    place.delete()
    messages.success(request, "ลบสถานที่เรียบร้อยแล้ว")
    return redirect("admin_dashboard")

User = get_user_model()

@admin_required
def admin_delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        messages.error(request, "ไม่สามารถลบตัวเองได้")
    elif user.is_superuser:
        messages.error(request, "ไม่สามารถลบ Superuser ได้")
    else:
        user.delete()
        messages.success(request, f"ลบผู้ใช้งาน {user.username} เรียบร้อยแล้ว")

    return redirect("admin_dashboard")

@admin_required
def add_place_schedule(request):
    if request.method == 'POST':
        form = PlaceScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.save()
            messages.success(request, "เพิ่มวันเวลาให้สถานที่เรียบร้อยแล้ว")
            return redirect('admin_dashboard')
    else:
        form = PlaceScheduleForm()
    
    return render(request, 'reservation/add_place_schedule.html', {'form': form})

@admin_required
def edit_schedule_view(request, pk):#แก้ไขเวลา
    schedule = get_object_or_404(PlaceSchedule, pk=pk)

    if request.method == "POST":
        form = PlaceScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            return redirect('location_detail', pk=schedule.place.id)
    else:
        form = PlaceScheduleForm(instance=schedule)

    return render(request, 'reservation/edit_schedule.html', {'form': form, 'schedule': schedule})

@admin_required
def delete_schedule_view(request, pk):
    schedule = get_object_or_404(PlaceSchedule, pk=pk)
    place_id = schedule.place.id  # เก็บ ID ไว้สำหรับ redirect
    schedule.delete()
    return redirect('location_detail', pk=place_id)

@admin_required
def admin_add_place_view(request):
    if request.method == "POST":
        form = PlaceForm(request.POST, request.FILES)
        images = request.FILES.getlist('images')
        
        if form.is_valid():
            place = form.save()

            # ✅ ถ้ามีการอัปโหลดภาพหลายภาพ ให้สร้าง PlaceImage แยกทีละไฟล์
            for img in images:
                PlaceImage.objects.create(place=place, image=img)

            messages.success(request, "สร้างสถานที่ใหม่สำเร็จ!")
            return redirect('location_detail', pk=place.id)
    else:
        form = PlaceForm()

    return render(request, "reservation/admin_add_place.html", {"form": form})



def add_place_images(request, place_id):
    place = get_object_or_404(Place, id=place_id)

    if request.method == "POST":
        images = request.FILES.getlist('images')  # รับหลายไฟล์
        for img in images:
            PlaceImage.objects.create(place=place, image=img)

        # ✅ ตรวจสอบว่า URL ใช้ pk หรือ place_id
        return redirect('location_detail', pk=place.id)

    return redirect('location_detail', pk=place.id)


def admin_update_place(request, place_id):
    place = get_object_or_404(Place, id=place_id)
    
    if request.method == "POST":
        place.name = request.POST.get("name")
        place.description = request.POST.get("description")
        place.capacity = request.POST.get("capacity")

        if request.FILES.get("image"):
            place.image = request.FILES["image"]

        place.save()
        messages.success(request, "อัปเดตข้อมูลสถานที่เรียบร้อยแล้ว!")                                 
        return redirect('admin_dashboard')

    return render(request, 'reservation/admin_update_place.html', {"place": place})


@admin_required
def delete_place_image(request, image_id):
    image = get_object_or_404(PlaceImage, id=image_id)
    place_id = image.place.id
    image.delete()
    return redirect('location_detail', pk=place_id)

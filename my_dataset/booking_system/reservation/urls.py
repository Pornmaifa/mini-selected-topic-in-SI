from django.urls import path # type: ignore
from . import views
from django.contrib.auth.views import LogoutView # type: ignore



urlpatterns = [
    path('register/', views.register_view, name='register'),
    path("", views.login_view, name="login"),
    path('logout/', views.logout_view, name='logout'),
    path("dashboard/", views.dashboard_view, name="dashboard"),  # สร้างหน้า Dashboard
    path('location/<int:pk>/', views.location_detail_view, name='location_detail'), 
    path('profile/',views.profile_view, name="profile"),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),


    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/delete/<int:user_id>/', views.admin_delete_user, name='custom_admin_delete_user'),
    path('admin-dashboard/delete-place/<int:place_id>/', views.admin_delete_place, name='admin_delete_place'),
    path('admin-dashboard/add-schedule/', views.add_place_schedule, name='add_place_schedule'),
    path('location/<int:pk>/', views.location_detail_view, name='location_detail'),
    path('schedule/edit/<int:pk>/', views.edit_schedule_view, name='edit_schedule'),
    path('schedule/delete/<int:pk>/', views.delete_schedule_view, name='delete_schedule'),
    # reservation/urls.py
    path('dashboard/place/add/', views.admin_add_place_view, name='admin_add_place'),
    path('dashboard/place/update/<int:place_id>/', views.admin_update_place, name='admin_update_place1'),
    path('place/<int:place_id>/add_images/', views.add_place_images, name='add_place_images'),
    # reservation/urls.py
    path('place/image/<int:image_id>/delete/', views.delete_place_image, name='delete_place_image'),
    path('profile/deactivate/', views.deactivate_account_view, name='deactivate_account'),





] 
from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),
    path('register/', views.register_view, name='register_view'),
    path('logged_in/', views.logged_in_view, name='logged_in_view'),
    path('logout/', views.logout_view, name='logout_view'),

    path('teacher/classes/', views.teacher_classes_view, name='teacher_classes_view'),
    path('teacher/profile/', views.teacher_profile_view, name='teacher_profile_view'),

    path('student/classes/', views.student_classes_view, name='student_classes_view'),
    path('student/profile/', views.student_profile_view, name='student_profile_view'),
]

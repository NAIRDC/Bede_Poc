from django.urls import path
from dbr import views

urlpatterns = [
    path('', views.json_upload_view, name='home'),  # الصفحة الرئيسية
    path("login/", views.login_view, name="login"),
    path("locked/", views.locked_view, name="locked"),
    path("logout/", views.logout_view, name="logout"),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/users/',      views.api_users,   name='api_users'),
    path('api/reports/<int:user_id>/',   views.api_reports,  name='api_reports'),
    path('api/accounts/<str:report_id>/', views.api_accounts, name='api_accounts'),
    path('upload-json/', views.json_upload_view, name='upload_json'),  # نفس الدالة يمكن استدعاؤها من مسارين
]

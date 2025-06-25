from django.urls import path
from dbr import views

urlpatterns = [
    path('', views.json_upload_view, name='home'),  # الصفحة الرئيسية
    path('upload-json/', views.json_upload_view, name='upload_json'),  # نفس الدالة يمكن استدعاؤها من مسارين
]

# models.py
from django.db import models

class User(models.Model):
    id_number = models.CharField(max_length=20, unique=True)
    first_name_en = models.CharField(max_length=100, blank=True)
    middle_name1_en = models.CharField(max_length=100, blank=True)
    middle_name2_en = models.CharField(max_length=100, blank=True)
    middle_name3_en = models.CharField(max_length=100, blank=True, null=True)
    last_name_en = models.CharField(max_length=100, blank=True)
    
    first_name_ar = models.CharField(max_length=100, blank=True)
    middle_name1_ar = models.CharField(max_length=100, blank=True)
    middle_name2_ar = models.CharField(max_length=100, blank=True)
    middle_name3_ar = models.CharField(max_length=100, blank=True, null=True)
    last_name_ar = models.CharField(max_length=100, blank=True)

    gender = models.CharField(max_length=100, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True)
    date_of_birth = models.CharField(max_length=100, blank=True)
    
    marital_status = models.CharField(max_length=50, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    employment_status = models.CharField(max_length=50, blank=True)
    name_of_employer = models.CharField(max_length=255, blank=True)
    place_of_birth = models.CharField(max_length=100, blank=True)

    # Contact
    email = models.EmailField(blank=True)
    telephone_number = models.CharField(max_length=20, blank=True)
    home_tel_number = models.CharField(max_length=20, blank=True)
    work_tel_number = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    po_box = models.CharField(max_length=20, blank=True)

    # Address
    address = models.CharField(max_length=255, blank=True)
    address_type = models.CharField(max_length=50, blank=True)
    flat_number = models.CharField(max_length=20, blank=True, null=True)
    building_number = models.CharField(max_length=20, blank=True, null=True)
    building_alpha = models.CharField(max_length=100, blank=True)
    road_number = models.CharField(max_length=20, blank=True, null=True)
    block_number = models.CharField(max_length=20, blank=True, null=True)

    # Passport
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry_date = models.CharField(max_length=20, blank=True)

   

    created_at = models.DateTimeField(auto_now_add=True)

class BCRBReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    report_id = models.CharField(max_length=100, primary_key=True)
    uid = models.CharField(max_length=100)
    score_online = models.IntegerField(null=True)
    score_reason1 = models.TextField(null=True)
    score_reason2 = models.TextField(null=True)
    score_reason3 = models.TextField(null=True)
    gross_salary = models.FloatField(null=True)
    fetching_date = models.DateTimeField(null=True)
    decision = models.CharField(max_length=20, null=True)
    dbr_percent = models.FloatField(null=True)

class BCRBAccount(models.Model):
    report = models.ForeignKey(BCRBReport, on_delete=models.CASCADE)
    account_type = models.CharField(max_length=100)
    account_position = models.CharField(max_length=50)
    payment_amount = models.FloatField(null=True)
    payment_frequency = models.CharField(max_length=50)
    finance_amount_or_credit_limit = models.FloatField(null=True)
    outstanding_balance = models.FloatField(null=True)
    relation_to_account = models.CharField(max_length=50, default="Owner")

    def __str__(self):
        return f"{self.first_name_en} {self.middle_name2_en or ''} ({self.id_number})"

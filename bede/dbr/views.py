from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import JsonFileUploadForm
from .models import BCRBReport
from .util.dbr_calculator import calculate_dbr_from_json
from .models import User, BCRBReport, BCRBAccount
from datetime import datetime
from django.utils import timezone

import json
from django.utils.dateparse import parse_datetime


def save_user_from_json(json_data):
    """Creates or updates a user based on KYC fields."""
    kyc = json_data["response"]["kyc"]["iga_fields"]
    id_number = kyc.get("id_number")

    user, _ = User.objects.update_or_create(
        id_number=id_number,
        defaults={
            "first_name_en": kyc.get("first_name_en", ""),
            "middle_name2_en": kyc.get("middle_name2_en", ""),
            "gender": kyc.get("gender", ""),
            "nationality": kyc.get("nationality", ""),
            "date_of_birth": kyc.get("date_of_birth", ""),
            "occupation": kyc.get("occupation", ""),
            "employment_status": kyc.get("employment_status", ""),
            "name_of_employer": kyc.get("name_of_employer", ""),
            "marital_status": kyc.get("marital_status", ""),
            "telephone_number": kyc.get("telephone_number", ""),
            "passport_number": kyc.get("passport_number", "")
        }
    )
    return user


def save_bcrb_report_from_json(json_data, user):
    report_id = json_data['reportId']
    uid = json_data['uid']
    fetching_dt = json_data.get('fetchingDate', [2025, 1, 1, 0, 0, 0])
    fetch_dt = timezone.make_aware(datetime(*fetching_dt[:6]))

    dbr_percent, decision = calculate_dbr_from_json(json_data)

    report = BCRBReport.objects.create(
        report_id=report_id,
        user=user,
        uid=uid,
        score_online=json_data['response']['bcrb']['score']['online']['score'],
        score_reason1=json_data['response']['bcrb']['score']['online']['reason1'],
        score_reason2=json_data['response']['bcrb']['score']['online']['reason2'],
        score_reason3=json_data['response']['bcrb']['score']['online']['reason3'],
        gross_salary=json_data['response']['gross_salary'],
        fetching_date=fetch_dt,
        dbr_percent=dbr_percent,
        decision=decision
    )

    for acc in json_data['response']['bcrb']['accounts']['account_detail']:
        BCRBAccount.objects.create(
            report=report,
            account_type=acc.get('account_type'),
            account_position=acc.get('account_position'),
            payment_amount=acc.get('payment_amount'),
            payment_frequency=acc.get('payment_frequency'),
            finance_amount_or_credit_limit=acc.get('finance_amount_or_credit_limit'),
            outstanding_balance=acc.get('outstanding_balance'),
            relation_to_account=acc.get('relation_to_account', 'Owner')
        )

    return report

def extract_user_data_from_instance(user):
    return {
        "First Name": user.first_name_en,
        "Middle Name": user.middle_name2_en,
        "Gender": user.gender,
        "Nationality": user.nationality,
        "ID Number": user.id_number,
        "Occupation": user.occupation,
        "Employment Status": user.employment_status,
        "Employer": user.name_of_employer,
        "Marital Status": user.marital_status,
        "Phone": user.telephone_number,
        "DOB": user.date_of_birth,
        "Passport": user.passport_number,
    }

def process_dbr_for_report(report):
    """Rebuild structure from DB and calculate DBR."""
    accounts = BCRBAccount.objects.filter(report=report)
    account_detail = [
        {
            "account_type": acc.account_type,
            "account_position": acc.account_position,
            "payment_amount": acc.payment_amount,
            "payment_frequency": acc.payment_frequency,
            "finance_amount_or_credit_limit": acc.finance_amount_or_credit_limit,
            "outstanding_balance": acc.outstanding_balance,
            "relation_to_account": acc.relation_to_account,
        }
        for acc in accounts
    ]

    structured_input = {
        "reportId": report.report_id,
        "uid": report.uid,
        "response": {
            "gross_salary": report.gross_salary,
            "bcrb": {
                "accounts": {
                    "account_detail": account_detail
                }
            }
        }
    }

    dbr_percent, decision = calculate_dbr_from_json(structured_input)
    report.dbr_percent = dbr_percent
    report.decision = decision
    report.save()

    return {"DBR %": dbr_percent, "Decision": decision}


def json_upload_view(request):
    user_info = None
    dbr_info = None

    if request.method == "POST":
        form = JsonFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES["json_file"]
            try:
                json_data = json.load(uploaded_file)
                report_id = json_data.get("reportId")

                # Check for existing report
                if BCRBReport.objects.filter(report_id=report_id).exists():
                    report = BCRBReport.objects.get(report_id=report_id)
                    user = report.user
                    user_info = extract_user_data_from_instance(user)
                    dbr_info = {
                        "DBR %": report.dbr_percent,
                        "Decision": report.decision,
                        "Score": report.score_online,
                        "Gross Salary": report.gross_salary,
                    }
                    messages.info(request, "Report already exists. Loaded from database.")
                else:
                    # Save new user & report
                    user = save_user_from_json(json_data)
                    report = save_bcrb_report_from_json(json_data, user)
                    user_info = extract_user_data_from_instance(user)
                    dbr_info = {
                        "DBR %": report.dbr_percent,
                        "Decision": report.decision,
                        "Score": report.score_online,
                        "Gross Salary": report.gross_salary,
                    }
                    messages.success(request, "Data processed and saved successfully.")

            except json.JSONDecodeError as e:
                messages.error(request, f"Invalid JSON: {e}")
    else:
        form = JsonFileUploadForm()

    return render(request, "json_upload_file.html", {
        "form": form,
        "user_info": user_info,
        "dbr_info": dbr_info
    })
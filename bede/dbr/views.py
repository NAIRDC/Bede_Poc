from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import JsonFileUploadForm, LoginForm
from .models import BCRBReport
from .util.dbr_calculator import calculate_dbr_from_json
from .models import User, BCRBReport, BCRBAccount
from datetime import datetime
from django.utils import timezone

import json
from django.utils.dateparse import parse_datetime

MAX_FAILED_ATTEMPTS = 5
HARDCODED_USERNAME = "test1"
HARDCODED_PASSWORD = "nairdc123"

def login_view(request):
    """Simple hard-coded login with lockout after 5 failures."""
    template_name = "login.html"
    locked_template = "locked.html"

    # If we already locked this session, show the lock screen
    attempts = request.session.get("login_attempts", 0)
    if attempts >= MAX_FAILED_ATTEMPTS:
        return render(request, locked_template)

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            if username == HARDCODED_USERNAME and password == HARDCODED_PASSWORD:
                # Success
                request.session["login_attempts"] = 0
                request.session["user_authenticated"] = True
                request.session["username"] = username
                return redirect("login")          # URL-name shown below
            else:
                # Wrong credentials
                attempts += 1
                request.session["login_attempts"] = attempts
                form.add_error(None, "Invalid credentials. Please try again.")

                if attempts >= MAX_FAILED_ATTEMPTS:
                    return render(request, locked_template)
    else:
        form = LoginForm()

    return render(request, template_name, {"form": form})


def locked_view(request):
    return render(request, "locked.html")



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

# def extract_user_data_from_instance(user):
#     return {
#         "First Name": user.first_name_en,
#         "Middle Name": user.middle_name2_en,
#         "Gender": user.gender,
#         "Nationality": user.nationality,
#         "ID Number": user.id_number,
#         "Occupation": user.occupation,
#         "Employment Status": user.employment_status,
#         "Employer": user.name_of_employer,
#         "Marital Status": user.marital_status,
#         "Phone": user.telephone_number,
#         "DOB": user.date_of_birth,
#         "Passport": user.passport_number,
#     }

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


def _build_result_dict(report, user, status):          # ← extra arg
    """
    status = "new"       → file just stored in DB
           = "existing"  → file was already there
    """
    reasons = [
        r for r in (
            report.score_reason1,
            report.score_reason2,
            report.score_reason3
        ) if r                                # skip None / empty
    ]
    return {
        "file_name": f"{report.report_id}.json",
        "status": status,
        "reasons": reasons,
        "decision": report.decision,
        "dbr_percent": report.dbr_percent,
        "score": report.score_online,
        "gross_salary": report.gross_salary,
        "last_fetched": report.fetching_date.strftime("%Y-%m-%d %H:%M"),
        "user": {
            "full_name": f"{user.first_name_en} {user.middle_name2_en or ''}".strip(),
            "gender": user.gender,
            "nationality": user.nationality,
            "passport_number": user.passport_number,
            "date_of_birth": user.date_of_birth,
            "occupation": user.occupation,
            "employment_status": user.employment_status,
            "employer": user.name_of_employer,
            "marital_status": user.marital_status,
            "mobile": user.telephone_number,
        },
        "accounts": [
            {
                "type": a.account_type,
                "position": a.account_position,
                "outstanding": a.outstanding_balance or 0.0,
                "payment_type": a.payment_frequency,
            }
            for a in BCRBAccount.objects.filter(report=report)
        ],
    }

def json_upload_view(request):
    if request.method == "GET":
        return render(request, "upload_page.html", {"form": JsonFileUploadForm()})

    results, errors = [], []
    files = request.FILES.getlist("files")

    for f in files:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append({"file": f.name, "error": str(exc)})
            continue

        user = save_user_from_json(data)
        report_id = data.get("reportId")

        # check for duplicates
        if BCRBReport.objects.filter(report_id=report_id).exists():
            report  = BCRBReport.objects.get(report_id=report_id)
            status  = "existing"
        else:
            report  = save_bcrb_report_from_json(data, user)
            status  = "new"

        results.append(_build_result_dict(report, user, status))

    return JsonResponse({"results": results, "errors": errors})

def api_users(request):
    # Return a list of all users
    users = User.objects.all().values(
        'id',
        'id_number',
        'first_name_en','middle_name1_en','middle_name2_en','middle_name3_en','last_name_en',
        'first_name_ar','middle_name1_ar','middle_name2_ar','middle_name3_ar','last_name_ar',
        'gender','nationality','date_of_birth',
        'marital_status','occupation','employment_status','name_of_employer','place_of_birth',
        'email','telephone_number','home_tel_number','work_tel_number','mobile','po_box',
        'address','address_type','flat_number','building_number','building_alpha','road_number','block_number',
        'passport_number','passport_expiry_date'
    )
    return JsonResponse(list(users), safe=False)

def api_reports(request, user_id):
    # Return all reports for a given user
    reports = BCRBReport.objects.filter(user_id=user_id).values(
        'report_id', 'uid',
        'score_online','score_reason1','score_reason2','score_reason3',
        'gross_salary','fetching_date','decision','dbr_percent'
    )
    return JsonResponse(list(reports), safe=False)

def api_accounts(request, report_id):
    # Return all account-details for a given report
    accounts = BCRBAccount.objects.filter(report_id=report_id).values(
        'account_type','account_position',
        'payment_amount','payment_frequency',
        'finance_amount_or_credit_limit','outstanding_balance',
        'relation_to_account'
    )
    return JsonResponse(list(accounts), safe=False)

# def json_upload_view(request):
#     user_info = None
#     dbr_info = None

#     if request.method == "POST":
#         form = JsonFileUploadForm(request.POST, request.FILES)
#         if form.is_valid():
#             uploaded_file = request.FILES["json_file"]
#             try:
#                 json_data = json.load(uploaded_file)
#                 report_id = json_data.get("reportId")

#                 # Check for existing report
#                 if BCRBReport.objects.filter(report_id=report_id).exists():
#                     report = BCRBReport.objects.get(report_id=report_id)
#                     user = report.user
#                     user_info = extract_user_data_from_instance(user)
#                     dbr_info = {
#                         "DBR %": report.dbr_percent,
#                         "Decision": report.decision,
#                         "Score": report.score_online,
#                         "Gross Salary": report.gross_salary,
#                     }
#                     messages.info(request, "Report already exists. Loaded from database.")
#                 else:
#                     # Save new user & report
#                     user = save_user_from_json(json_data)
#                     report = save_bcrb_report_from_json(json_data, user)
#                     user_info = extract_user_data_from_instance(user)
#                     dbr_info = {
#                         "DBR %": report.dbr_percent,
#                         "Decision": report.decision,
#                         "Score": report.score_online,
#                         "Gross Salary": report.gross_salary,
#                     }
#                     messages.success(request, "Data processed and saved successfully.")

#             except json.JSONDecodeError as e:
#                 messages.error(request, f"Invalid JSON: {e}")
#     else:
#         form = JsonFileUploadForm()

#     return render(request, "json_upload_file.html", {
#         "form": form,
#         "user_info": user_info,
#         "dbr_info": dbr_info
#     })
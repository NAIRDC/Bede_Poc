from django.http import JsonResponse
from django.shortcuts import render, redirect
from dbr.util.json_process import save_bcrb_report_from_json, save_user_from_json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import JsonFileUploadForm, LoginForm
from .models import BCRBReport
from .models import Customer, BCRBReport, BCRBAccount,UserActivity,CustomUser
import json
from django.utils import timezone # Import timezone

MAX_FAILED_ATTEMPTS = 5
HARDCODED_USERNAME = "test1"
HARDCODED_PASSWORD = "nairdc123"

def login_view(request):
    """
    Handles user login, with a specific check to redirect locked accounts
    to a dedicated "locked" page.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            # --- NEW LOGIC: CHECK FOR LOCKOUT FIRST ---
            try:
                user_account = CustomUser.objects.get(username__iexact=username)
                # Check if the account is locked
                if user_account.lockout_until and user_account.lockout_until > timezone.now():
                    # Store the lockout time in the session to display on the locked page
                    request.session['lockout_until'] = user_account.lockout_until.isoformat()
                    return redirect('locked') # Redirect to the new locked_view
            except CustomUser.DoesNotExist:
                # User does not exist, fall through to the normal authentication failure
                pass
            # --- END OF NEW LOGIC ---

            # If the account wasn't locked, proceed with authentication
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                UserActivity.objects.create(user=user, activity="Logged In")
                # Clear any old lockout time from the session on successful login
                if 'lockout_until' in request.session:
                    del request.session['lockout_until']
                return redirect("dashboard")
            else:
                form.add_error(None, "Invalid credentials. Please try again.")
    else:
        form = LoginForm()

    return render(request, "login.html", {"form": form})

# This is your new view for handling the locked page
def locked_view(request):
    lockout_until_str = request.session.get('lockout_until')

    # If someone accesses this page directly without being locked out, redirect them
    if not lockout_until_str:
        return redirect('login')
    
    # Convert the string from the session back to a datetime object
    lockout_until = timezone.datetime.fromisoformat(lockout_until_str)
    
    # If the lockout time has passed, redirect to login
    if lockout_until < timezone.now():
         return redirect('login')

    context = {
        'lockout_until': lockout_until
    }
    return render(request, "locked.html", context)

# 3. USE the standard Django logout view for simplicity, or keep your custom one
def logout_view(request):
    """Logs the user out and records the activity."""
    if request.user.is_authenticated:
        UserActivity.objects.create(user=request.user, activity="Logged Out")
    logout(request)
    return redirect('login')

# 4. PROTECT your dashboard view
@login_required(login_url='login')
def dashboard(request):
    # Renders your dashboard.html
    # You can add context here, like user activities
    activities = UserActivity.objects.filter(user=request.user).order_by('-timestamp')[:10]
    return render(request, 'dashboard.html', {'activities': activities})



def _build_result_dict(report, user, status):
    """
    Builds a dictionary with processed report data for the frontend.
    status = "new"      → file just stored in DB
           = "existing"  → file was already there
    """
    reasons = [
        r for r in (
            report.score_reason1,
            report.score_reason2,
            report.score_reason3
        ) if r  # skip None / empty
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
@login_required(login_url='login')
def json_upload_view(request):
    if request.method == "GET":
        return render(request, "upload_page.html", {"form": JsonFileUploadForm()})

    results, errors = [], []
    files = request.FILES.getlist("files")

    for f in files:
        try:
            # Ensure the file pointer is at the beginning
            f.seek(0)
            # Decode assuming UTF-8 and load JSON
            data = json.loads(f.read().decode('utf-8'))

            # --- Data Validation and Processing ---
            # Check for essential top-level key
            report_id = data.get("reportId")
            if not report_id:
                raise KeyError("The 'reportId' key is missing from the JSON file.")

            # Check for duplicates
            if BCRBReport.objects.filter(report_id=report_id).exists():
                report = BCRBReport.objects.get(report_id=report_id)
                user = report.user # Assuming a ForeignKey from report to user
                status = "existing"
            else:
                # Process and save new data
                user = save_user_from_json(data)
                report = save_bcrb_report_from_json(data, user)
                status = "new"

            results.append(_build_result_dict(report, user, status))

        except json.JSONDecodeError:
            errors.append({"file": f.name, "error": "Invalid JSON format. The file is corrupted or not a valid JSON."})
        except (KeyError, TypeError, AttributeError) as exc:
            errors.append({"file": f.name, "error": f"JSON structure mismatch or missing data: {str(exc)}"})
        except Exception as exc:
            # Catch any other unexpected errors
            errors.append({"file": f.name, "error": f"An unexpected error occurred: {str(exc)}"})
    
    return JsonResponse({"results": results, "errors": errors})

def api_users(request):
    # Return a list of all users
    users = Customer.objects.all().values(
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

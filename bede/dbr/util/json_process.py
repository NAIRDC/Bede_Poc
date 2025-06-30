


from dbr.models import BCRBAccount, BCRBReport, Customer
from datetime import datetime
from django.utils import timezone

from dbr.util.dbr_calculator import calculate_dbr_from_json

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


def save_user_from_json(json_data):
    """Creates or updates a user based on KYC fields."""
    kyc = json_data["response"]["kyc"]["iga_fields"]
    id_number = kyc.get("id_number")

    # Prepare a dictionary with default values for all fields
    # to handle cases where a key might be missing in the JSON.
    defaults = {
        "first_name_en": kyc.get("first_name_en", ""),
        "middle_name1_en": kyc.get("middle_name1_en", ""),
        "middle_name2_en": kyc.get("middle_name2_en", ""),
        "middle_name3_en": kyc.get("middle_name3_en", ""),
        "last_name_en": kyc.get("last_name_en", ""),
        "first_name_ar": kyc.get("first_name_ar", ""),
        "middle_name1_ar": kyc.get("middle_name1_ar", ""),
        "middle_name2_ar": kyc.get("middle_name2_ar", ""),
        "middle_name3_ar": kyc.get("middle_name3_ar", ""),
        "last_name_ar": kyc.get("last_name_ar", ""),
        "gender": kyc.get("gender", ""),
        "nationality": kyc.get("nationality", ""),
        "date_of_birth": kyc.get("date_of_birth", ""),
        "occupation": kyc.get("occupation", ""),
        "employment_status": kyc.get("employment_status", ""),
        "name_of_employer": kyc.get("name_of_employer", ""),
        "marital_status": kyc.get("marital_status", ""),
        "place_of_birth": kyc.get("place_of_birth", ""),
        "email": kyc.get("email", ""),
        "telephone_number": kyc.get("telephone_number", ""),
        "address_type": kyc.get("address_type", ""),
        "flat_number": kyc.get("flat_number"),
        "building_number": kyc.get("building_number"),
        "building_alpha": kyc.get("building_alpha", ""),
        "road_number": kyc.get("road_number"),
        "block_number": kyc.get("block_number"),
        "passport_number": kyc.get("passport_number", ""),
        "passport_expiry_date": kyc.get("passport_expiry_date", ""),
    }

    # Use update_or_create to either create a new customer or update an existing one
    user, created = Customer.objects.update_or_create(
        id_number=id_number,
        defaults=defaults
    )

    return user


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
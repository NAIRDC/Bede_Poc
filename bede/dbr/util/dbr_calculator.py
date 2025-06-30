

from dbr.models import BCRBAccount


def calculate_dbr_from_json(data):
    gross_salary = data['response']['gross_salary']
    if gross_salary in [None, 0]:
        return None, "Rejected"

    accounts = data['response']['bcrb']['accounts']['account_detail']
    included_products = {
        'Consumer Loan', 'Housing Loan', 'Corporate loans', 'Mazaya Loan', 'BNPL (Buy Now Pay Latter)'
    }
    frequency_map = {
        'Monthly': 1, 'Fortnightly': 2, 'Bimonthly': 2, 'Weekly': 4,
        'Quarterly': 1/3, 'Annually': 0, 'Semi Annually': 0, 'On Demand': 0,
        'Differed Payments': 0, 'Bullets Payments': 0, 'Ballon Payments': 0
    }
    relation_weight = {
        'Owner': 1.0,
        'Joint holder': 0.5,
        'Guarantor': 0.0
    }

    total_commitment = 0
    total_credit_card_limit = 0
    has_housing_loan = False

    for account in accounts:
        if account['account_position'] != 'Open':
            continue

        relation = account.get('relation_to_account', 'Owner')
        weight = relation_weight.get(relation, 0)

        acc_type = account['account_type']
        freq = account['payment_frequency']
        amount = account.get('payment_amount', 0) or 0
        limit = account.get('finance_amount_or_credit_limit', 0) or 0

        if acc_type == 'Credit Card':
            total_credit_card_limit += limit * weight
        elif acc_type in included_products:
            total_commitment += (amount * frequency_map.get(freq, 0)) * weight

        if acc_type == 'Housing Loan':
            has_housing_loan = True

    total_burden = total_commitment + (total_credit_card_limit * 0.05)
    dbr = total_burden / gross_salary
    dbr_percent = round(dbr * 100, 2)

    # DBR Acceptance Logic
    if gross_salary <= 3000:
        limit = 0.50 if has_housing_loan else 0.65
    else:
        limit = 0.70

    decision = "Accepted" if dbr <= limit else "Rejected"
    return dbr_percent, decision


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
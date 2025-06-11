import calendar
import logging
from datetime import datetime, timedelta  # noqa
from enum import Enum

from httpx import Client

from app.clinics_card.entities import Patient, Plan
from app.clinics_card.invoices import ClinicsCardInvoice
from app.clinics_card.patients import ClinicsCardPatient
from app.clinics_card.payments import ClinicsCardPayment
from app.clinics_card.plans import ClinicsCardPlan
from app.clinics_card.visits import ClinicsCardVisit
from app.config import settings
from app.excel import GoogleSheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PAYMENT_DATE_INDEXES: dict[datetime, tuple[int, int]] = {}
# CURRENT_DATE = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # noqa
CURRENT_DATE = datetime(year=2025, month=5, day=26)  # noqa


class ColumnElementId(Enum):
    TREATMENT_PLAN = 10
    VISITS_COUNT = 7
    FULL_NAME = 3


class RowElementId(Enum):
    MONTH_COUNT = 4


def get_day_month_string(date: datetime) -> str:
    return date.strftime("%d.%m")


def get_current_date_iso_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_month_name(date: datetime) -> str:
    MONTH_NAMES_RU = [
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    ]
    return MONTH_NAMES_RU[date.month - 1]


def days_in_half_year_up_to(year, half, up_to_month, up_to_day):
    start_month = 1 if half == 1 else 7

    total_days = 0
    for month in range(start_month, up_to_month + 1):
        days_in_month = calendar.monthrange(year, month)[1] + 1
        if month == up_to_month:
            if up_to_day >= days_in_month:
                raise ValueError("Указанный день превышает количество дней в месяце.")
            total_days += up_to_day + 1
        else:
            total_days += days_in_month

    return total_days


def get_half_year(target_date: datetime) -> int:
    half = 1 if target_date.month <= 6 else 2
    return half


def get_half_year_str(target_date: datetime) -> str:
    year = target_date.year
    half = 1 if target_date.month <= 6 else 2
    return f"{half} полугодие {year}"


def get_payment_date_position(date: datetime, google_sheet_client: GoogleSheetsClient):
    global PAYMENT_DATE_INDEXES

    if date not in PAYMENT_DATE_INDEXES:
        half = get_half_year(date)
        half_str = get_half_year_str(date)
        half_str_position = google_sheet_client.find(half_str)
        d_index = days_in_half_year_up_to(date.year, half, date.month, date.day)
        payment_date_position = (half_str_position[0] + d_index - 1, 3)
        PAYMENT_DATE_INDEXES[date] = payment_date_position

    return PAYMENT_DATE_INDEXES[date]


def get_all_patient_data() -> list[Patient]:
    patient_client = ClinicsCardPatient(
        http_client=Client(base_url="https://cliniccards.com/api"),
        api_key=settings.CLINICS_CARD_API_KEY,
    )
    visits_client = ClinicsCardVisit(
        http_client=Client(base_url="https://cliniccards.com/api"),
        api_key=settings.CLINICS_CARD_API_KEY,
    )
    payment_client = ClinicsCardPayment(
        http_client=Client(base_url="https://cliniccards.com/api"),
        api_key=settings.CLINICS_CARD_API_KEY,
    )
    plans_client = ClinicsCardPlan(
        http_client=Client(base_url="https://cliniccards.com/api"),
        api_key=settings.CLINICS_CARD_API_KEY,
    )
    invoices_client = ClinicsCardInvoice(
        http_client=Client(base_url="https://cliniccards.com/api"),
        api_key=settings.CLINICS_CARD_API_KEY,
    )

    patients = patient_client.get_all_patients()
    visits = visits_client.get_visits_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())
    payments = payment_client.get_payments_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())
    plans = plans_client.get_plans_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())
    invoices = invoices_client.get_invoices_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())

    plan_map: dict[str, Plan] = {plan.id: plan for plan in plans}

    patient_map: dict[str, Patient] = {}

    for patient in patients:
        patient.main_plans = plan_map.get(patient.main_plans_id)
        patient_map[patient.id] = patient

    for visit in visits:
        if visit.patient_id not in patient_map:
            logger.warning("Patient %s does not exist", visit.patient_id)
            continue

        patient_map[visit.patient_id].visits.append(visit)

    for payment in payments:
        if payment.patient_id not in patient_map:
            logger.warning("Patient %s does not exist", payment.patient_id)
            continue

        patient_map[payment.patient_id].payments.append(payment)

    for invoice in invoices:
        if invoice.patient_id not in patient_map:
            logger.warning("Patient %s does not exist", invoice.patient_id)
            continue

        patient_map[invoice.patient_id].invoices.append(invoice)

    patients = patient_map.values()
    patients = sorted(patients, key=lambda x: int(x.code))

    return patients


def get_inisert_patient_values(patient: Patient):
    full_name = f"{patient.last_name} {patient.first_name}"
    first_doctor = patient.visits[0].doctor if patient.visits else ""
    visits_count = len([visit for visit in patient.visits if visit.status == "VISITED"])
    visits_count = visits_count if visits_count else ""
    treatment_plan = patient.main_plans.plan_total_with_discount if patient.main_plans else ""
    treatment_plan = int(float(treatment_plan)) if treatment_plan else 0

    return [
        "",
        "",
        full_name,
        patient.code,
        patient.curator,
        first_doctor,
        visits_count,
        "",
        "",
        treatment_plan,
    ]


def update_patient_data(patient: Patient, google_sheet_client: GoogleSheetsClient):
    full_name = f"{patient.last_name} {patient.first_name}"

    treatment_plan = patient.main_plans.plan_total_with_discount if patient.main_plans else ""
    treatment_plan = int(float(treatment_plan)) if treatment_plan else ""

    visits_count = len([visit for visit in patient.visits if visit.status == "VISITED"])
    visits_count = visits_count if visits_count else ""

    updates = [
        (patient.row_position, ColumnElementId.FULL_NAME.value, full_name),
        (patient.row_position, ColumnElementId.TREATMENT_PLAN.value, treatment_plan),
        (patient.row_position, ColumnElementId.VISITS_COUNT.value, visits_count),
    ]

    google_sheet_client.update_cells(updates)

    logger.info("Updated patient %s: treatment plan=%s, visits count=%s", patient.code, treatment_plan, visits_count)


def update_patient_invoices(patient: Patient, google_sheet_client: GoogleSheetsClient):
    patient_invoice_sums = get_patient_invoice_sums_grouped_by_datetime(patient=patient)
    updates = []
    dates_and_sums = []

    for patient_invoice_date_created, invoice_sum in patient_invoice_sums.items():
        invoice_date_position = get_payment_date_position(
            patient_invoice_date_created, google_sheet_client=google_sheet_client
        )

        patient_invoice_date_position = (patient.row_position, invoice_date_position[0])

        updates.append(
            (patient_invoice_date_position[0], patient_invoice_date_position[1], invoice_sum)  # row  # col  # value
        )
        dates_and_sums.append(
            (
                patient_invoice_date_created,
                invoice_sum,
                (patient_invoice_date_position[0], patient_invoice_date_position[1]),
            )
        )

    if updates:
        google_sheet_client.update_cells(updates)
        for date_created, invoice_sum, position in dates_and_sums:
            logger.info(
                "Insert patient %s invoice %s by the date: %s at the position: %s",
                patient.code,
                invoice_sum,
                date_created,
                position,
            )


def set_patient_row_position(
    patient: Patient,
    google_sheet_client: GoogleSheetsClient,
) -> bool:
    """
    Returns:
        bool: return True if patient is exist
    """
    is_patient_exist = False
    try:
        patient.row_position = google_sheet_client.find(patient.code, in_column=4)[1]

        is_patient_exist = True
    except ValueError:
        patient.row_position = None

    return is_patient_exist


def insert_new_patient(patient: Patient, nearest_patient: Patient | None, google_sheet_client: GoogleSheetsClient):
    inser_patint_values = get_inisert_patient_values(patient=patient)
    previous_patient_position_id = nearest_patient.row_position if nearest_patient else 7
    google_sheet_client.write_row(inser_patint_values, position=previous_patient_position_id + 1)
    logger.info("Insert new patient %s values %s", patient.code, inser_patint_values)


def get_patient_invoice_sums_grouped_by_datetime(patient: Patient) -> dict[datetime, int]:
    patient_invoice_sums: dict[datetime, int] = {}

    for invoice in patient.invoices:

        if invoice.date_created < CURRENT_DATE:
            continue

        if invoice.date_created not in patient_invoice_sums:
            patient_invoice_sums[invoice.date_created] = 0

        patient_invoice_sums[invoice.date_created] += int(float(invoice.amount))

    return patient_invoice_sums


def insert_patient_payment_count(
    patient: Patient,
    patients_payments_count_grouped_by_date: dict[datetime, list[Patient]],
):
    for invoce in patient.invoices:
        if invoce.date_created < CURRENT_DATE:
            continue

        if invoce.date_created not in patients_payments_count_grouped_by_date:
            patients_payments_count_grouped_by_date[invoce.date_created] = []

        if patient not in patients_payments_count_grouped_by_date[invoce.date_created]:
            patients_payments_count_grouped_by_date[invoce.date_created].append(patient)

            logger.debug("Added patient payment count to patient: %s", patient.code)


def get_payment_count_position(
    date: datetime,
    google_sheet_client: GoogleSheetsClient,
) -> tuple[int, int]:
    date_month = get_month_name(date)
    position = google_sheet_client.find_last(date_month)
    position = (position[0], RowElementId.MONTH_COUNT.value)
    return position


def update_patients_payments_count(
    patients_payments_count_grouped_by_date: dict[datetime, list[Patient]],
    google_sheet_client: GoogleSheetsClient,
):
    updates = []
    for payment_count_date, patients in patients_payments_count_grouped_by_date.items():
        payments_count = len(patients)

        payment_count_position = get_payment_date_position(
            date=payment_count_date, google_sheet_client=google_sheet_client
        )
        row = RowElementId.MONTH_COUNT.value
        col = payment_count_position[0]

        updates.append((row, col, payments_count))

    if updates:
        google_sheet_client.update_cells(updates)

        for row, col, count in updates:
            logger.info("Inserted %s payments count at position row=%s, col=%s", count, row, col)


def get_nearest_lover_patient_by_id(patients: list[Patient], target_id: int) -> Patient | None:
    if not patients:
        return None

    sorted_patients = sorted(patients, key=lambda x: x.code)

    if target_id <= sorted_patients[0].code:
        return None

    nearest_patient = None
    for patient in sorted_patients:
        if patient.code < target_id:
            nearest_patient = patient
        else:
            break

    return nearest_patient


def inser_not_exist_patients_excel(patients: list[Patient]):
    google_sheet_client = GoogleSheetsClient(
        google_sheets_key=settings.GOOGLE_SPREADSHEET_KEY,
        worksheet_name=settings.GOOGLE_WORKSHEET_NAME,
        token_path="data/token.json",
    )

    patients_payments_count_grouped_by_date: dict[datetime, list[Patient]] = {}
    previous_patients = []

    for patient in patients:
        if len(patient.visits) == 0:
            logger.info("Patient %s has no visits", patient.code)
            continue

        is_patient_exist = set_patient_row_position(
            patient=patient,
            google_sheet_client=google_sheet_client,
        )

        if not is_patient_exist:
            # nearest_patient = get_nearest_lover_patient_by_id(patients=previous_patients, target_id=patient.code)
            previous_patient = previous_patients[-1]
            insert_new_patient(
                patient=patient, nearest_patient=previous_patient, google_sheet_client=google_sheet_client
            )
            set_patient_row_position(
                patient=patient,
                google_sheet_client=google_sheet_client,
            )
        else:
            update_patient_data(patient=patient, google_sheet_client=google_sheet_client)

        update_patient_invoices(patient=patient, google_sheet_client=google_sheet_client)

        insert_patient_payment_count(
            patient=patient,
            patients_payments_count_grouped_by_date=patients_payments_count_grouped_by_date,
        )

        previous_patients.append(patient)

    update_patients_payments_count(
        patients_payments_count_grouped_by_date=patients_payments_count_grouped_by_date,
        google_sheet_client=google_sheet_client,
    )


def main():
    patients = get_all_patient_data()
    inser_not_exist_patients_excel(patients=patients)


if __name__ == "__main__":
    main()

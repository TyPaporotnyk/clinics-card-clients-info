import calendar
import logging
from datetime import datetime, timedelta
from enum import Enum

from httpx import Client

from app.clinics_card.entities import Patient, Plan
from app.clinics_card.patients import ClinicsCardPatient
from app.clinics_card.payments import ClinicsCardPayment
from app.clinics_card.plans import ClinicsCardPlan
from app.clinics_card.visits import ClinicsCardVisit
from app.config import settings
from app.excel import GoogleSheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# START_ROW_INDEX_INSERT = 8
PAYMENT_DATE_INDEXES: dict[str, tuple[int, int]] = {}
# CURRENT_DATE = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
CURRENT_DATE = datetime(year=2023, month=1, day=1)


class ColumnElementId(Enum):
    TREATMENT_PLAN = 10
    VISITS_COUNT = 7


class RowElementId(Enum):
    MONTH_COUNT = 4


def get_day_month_string(date: datetime) -> str:
    return date.strftime("%d.%m")


def get_current_date_iso_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_month_name(date: datetime) -> str:
    MONTH_NAMES_RU = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
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
    if date not in PAYMENT_DATE_INDEXES:
        half = get_half_year(date)
        half_str = get_half_year_str(date)
        half_str_position = google_sheet_client.find(half_str)
        d_index = days_in_half_year_up_to(
            date.year, half, 
            date.month, 
            date.day
        )
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

    patients = patient_client.get_all_patients()
    visits = visits_client.get_visits_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())
    payments = payment_client.get_payments_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())
    plans = plans_client.get_plans_by_period(date_from="2023-01-01", date_to=get_current_date_iso_string())

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

    patients = patient_map.values()
    patients = sorted(patients, key=lambda x: int(x.code))

    return patients


def get_inisert_patient_values(patient: Patient):
    full_name = f"{patient.last_name} {patient.first_name}"
    first_doctor = patient.visits[0].doctor if patient.visits else ""
    visits_count = len([visit for visit in patient.visits if visit.status == "VISITED"])
    visits_count = visits_count if visits_count else ""
    treatment_plan = patient.main_plans.plan_total_with_discount if patient.main_plans else ""
    treatment_plan = int(float(treatment_plan)) if treatment_plan else ""

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


def update_patient_treatment_plan(patient: Patient, google_sheet_client: GoogleSheetsClient):
    treatment_plan = patient.main_plans.plan_total_with_discount if patient.main_plans else ""
    treatment_plan = int(float(treatment_plan)) if treatment_plan else ""

    google_sheet_client.update_element_at(
        ColumnElementId.TREATMENT_PLAN.value,
        patient.row_position,
        treatment_plan,
    )

    logger.info("Update patient %s treatment plan to: %s", patient.code, treatment_plan)


def update_patient_visits_count(patient: Patient, google_sheet_client: GoogleSheetsClient):
    visits_count = len([visit for visit in patient.visits if visit.status == "VISITED"])
    visits_count = visits_count if visits_count else ""

    google_sheet_client.update_element_at(
        ColumnElementId.VISITS_COUNT.value,
        patient.row_position,
        visits_count,
    )

    logger.info("Update patient %s visits count to: %s", patient.code, visits_count)


def update_patient_payments(
    patient: Patient,
    google_sheet_client: GoogleSheetsClient,
):
    patient_payment_sums = get_patient_payment_sums_grouped_by_datetime(patient=patient)
    for patient_payment_date_created, payment_sum in patient_payment_sums.items():
        payment_date_position = get_payment_date_position(
            patient_payment_date_created, google_sheet_client=google_sheet_client
        )

        patient_payment_date_position = (
            payment_date_position[0],
            patient.row_position,
        )

        google_sheet_client.update_element_at(*patient_payment_date_position, payment_sum)
        logger.info(
            "Insert patient %s payment %s by the date: %s at the place %s",
            patient.code,
            payment_sum,
            patient_payment_date_created,
            patient_payment_date_position
        )


def set_patient_row_position(
    patient: Patient,
    google_sheet_client: GoogleSheetsClient,
) -> bool:
    """
    Returns:
        bool: return True if patient is exist
    """
    full_name = f"{patient.last_name} {patient.first_name}"
    is_patient_exist = False
    try:
        patient.row_position = google_sheet_client.find(full_name)[1]

        is_patient_exist = True
    except ValueError:
        patient.row_position = None

    return is_patient_exist


def insert_new_patient(patient: Patient, google_sheet_client: GoogleSheetsClient):
    inser_patint_values = get_inisert_patient_values(patient=patient)
    google_sheet_client.write_row(inser_patint_values)
    logger.info("Insert new patient %s values %s", patient.code, inser_patint_values)


def get_patient_payment_sums_grouped_by_datetime(patient: Patient) -> dict[datetime, int]:
    patient_payment_sums: dict[datetime, int] = {}

    for patient_payment in patient.payments:

        if patient_payment.date_created < CURRENT_DATE:
            continue

        if patient_payment.date_created not in patient_payment_sums:
            patient_payment_sums[patient_payment.date_created] = 0

        patient_payment_sums[patient_payment.date_created] += int(float(patient_payment.amount))

    return patient_payment_sums


def insert_patient_payment_count(
    patient: Patient,
    patients_payments_count_grouped_by_date: dict[datetime, list[Patient]],
):
    for payment in patient.payments:
        if payment.date_created < CURRENT_DATE:
            continue
        
        if payment.date_created not in patients_payments_count_grouped_by_date:
            patients_payments_count_grouped_by_date[payment.date_created] = []

        if patient not in patients_payments_count_grouped_by_date[payment.date_created]:
            patients_payments_count_grouped_by_date[payment.date_created].append(patient)

            logger.debug("Added patient payment count to patient: %s", patient.code)


def get_payment_count_position(date: datetime, google_sheet_client: GoogleSheetsClient,) -> tuple[int, int]:
    date_month = get_month_name(date)
    position = google_sheet_client.find_last(date_month)
    position = (position[0], RowElementId.MONTH_COUNT.value)
    return position


def update_patients_payments_count(
    patients_payments_count_grouped_by_date: dict[datetime, list[Patient]],
    google_sheet_client: GoogleSheetsClient,
):
    for payment_count_date, patients in patients_payments_count_grouped_by_date.items():
        payments_count = len(patients)
        
        payment_count_position = get_payment_date_position(
            date=payment_count_date, google_sheet_client=google_sheet_client
        )
        payment_count_position = (payment_count_position[0], RowElementId.MONTH_COUNT.value)
        google_sheet_client.update_element_at(*payment_count_position, payments_count)

        logger.info("Inserted %s payments count by the date: %s", payments_count, payment_count_date)


def inser_not_exist_patients_excel(patients: list[Patient]):
    google_sheet_client = GoogleSheetsClient(
        google_sheets_key=settings.GOOGLE_SPREADSHEET_KEY,
        worksheet_name=settings.GOOGLE_WORKSHEET_NAME,
        token_path="data/token.json",
    )

    patients_payments_count_grouped_by_date: dict[datetime, list[Patient]] = {}

    for patient in patients:
        is_patient_exist = set_patient_row_position(
            patient=patient, google_sheet_client=google_sheet_client,
        )

        if not is_patient_exist:
            insert_new_patient(patient=patient, google_sheet_client=google_sheet_client)
            set_patient_row_position(
                patient=patient, google_sheet_client=google_sheet_client,
            )
        else:
            update_patient_treatment_plan(patient=patient, google_sheet_client=google_sheet_client)
            update_patient_visits_count(patient=patient, google_sheet_client=google_sheet_client)

        update_patient_payments(patient=patient, google_sheet_client=google_sheet_client)
        
        insert_patient_payment_count(
            patient=patient,
            patients_payments_count_grouped_by_date=patients_payments_count_grouped_by_date,
        )

    update_patients_payments_count(
        patients_payments_count_grouped_by_date=patients_payments_count_grouped_by_date,
        google_sheet_client=google_sheet_client,
    )


def main():
    patients = get_all_patient_data()
    inser_not_exist_patients_excel(patients=patients)


if __name__ == "__main__":
    main()

import logging
import time
from datetime import datetime
from enum import Enum

from httpx import Client

from app.clinics_card.entities import Patient, Payment, Plan
from app.clinics_card.patients import ClinicsCardPatient
from app.clinics_card.payments import ClinicsCardPayment
from app.clinics_card.plans import ClinicsCardPlan
from app.clinics_card.visits import ClinicsCardVisit
from app.config import settings
from app.excel import GoogleSheetsClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


START_ROW_INDEX_INSERT = 10
PAYMENT_DATE_INDEXES: dict[str, tuple[int, int]] = {}


class ColumnElementId(Enum):
    TREATMENT_PLAN = 8
    VISITS_COUNT = 6


def get_day_month_string(date: datetime) -> str:
    return date.strftime("%d.%m")


def get_current_date_iso_string() -> str:
    now = datetime.now()
    return now.strftime("%Y-%m-%d")


def get_payment_date_position(
    date: datetime, *, google_sheet_client: GoogleSheetsClient
):
    date_iso_string = get_day_month_string(date=date)
    payment_date_position = PAYMENT_DATE_INDEXES.get(date_iso_string)

    if not payment_date_position:
        payment_date_position = google_sheet_client.find_last(date_iso_string)
        PAYMENT_DATE_INDEXES[date_iso_string] = payment_date_position

    return payment_date_position


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
    visits = visits_client.get_visits_by_period(
        date_from="2020-01-01", date_to=get_current_date_iso_string()
    )
    payments = payment_client.get_payments_by_period(
        date_from="2020-01-01", date_to=get_current_date_iso_string()
    )
    plans = plans_client.get_plans_by_period(
        date_from="2020-01-01", date_to=get_current_date_iso_string()
    )

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


def inser_not_exist_patients_excel(patients: list[Patient]):
    google_sheet_client = GoogleSheetsClient(
        google_sheets_key=settings.GOOGLE_SPREADSHEET_KEY,
        worksheet_name=settings.GOOGLE_WORKSHEET_NAME,
        token_path="data/token.json",
    )

    previous_patient_row_position = None
    # current_date = datetime.now()
    # current_date = datetime(current_date.year, current_date.month, current_date.day)
    # payment_date_position = get_payment_date_position(current_date)

    current_date = datetime(year=2024, month=7, day=1)

    for patient in patients:
        is_patient_exist = False
        full_name = f"{patient.last_name} {patient.first_name}"

        try:
            patient_row_position = google_sheet_client.find(full_name)[1]
            time.sleep(1)

            is_patient_exist = True
        except ValueError:
            if not previous_patient_row_position:
                patient_row_position = START_ROW_INDEX_INSERT
            else:
                patient_row_position = previous_patient_row_position + 1

        def get_inisert_patient_values(patient: Patient):
            full_name = f"{patient.last_name} {patient.first_name}"
            first_doctor = patient.visits[0].doctor if patient.visits else ""
            visits_count = len(
                [visit for visit in patient.visits if visit.status == "VISITED"]
            )
            treatment_plan = (
                patient.main_plans.plan_total_with_discount
                if patient.main_plans
                else ""
            )
            treatment_plan = int(float(treatment_plan)) if treatment_plan else ""

            return [
                "",
                full_name,
                patient.code,
                patient.curator,
                first_doctor,
                visits_count,
                "",
                treatment_plan,
            ]

        if not is_patient_exist:
            inser_patint_values = get_inisert_patient_values(patient=patient)
            google_sheet_client.write_row(
                row_index=patient_row_position, values=inser_patint_values
            )
            logger.info(
                "Insert new patient %s position %s", patient.code, patient_row_position
            )
            logger.info(
                "Insert new patient %s values %s", patient.code, inser_patint_values
            )

        else:
            treatment_plan = (
                patient.main_plans.plan_total_with_discount
                if patient.main_plans
                else ""
            )
            treatment_plan = int(float(treatment_plan)) if treatment_plan else ""
            
            visits_count = len(
                [visit for visit in patient.visits if visit.status == "VISITED"]
            )
            visits_count = visits_count if visits_count else ""
            
            google_sheet_client.update_element_at(
                ColumnElementId.TREATMENT_PLAN.value,
                patient_row_position,
                treatment_plan,
            )
            google_sheet_client.update_element_at(
                ColumnElementId.VISITS_COUNT.value,
                patient_row_position,
                visits_count,
            )
            
            logger.info(
                "Update patient %s treatment plan to: %s", patient.code, treatment_plan
            )
            logger.info(
                "Update patient %s visits count to: %s", patient.code, visits_count
            )
            time.sleep(1)

        time.sleep(1)

        # Часть функционала для загрузки всех оплат пациента за опереденный промежуток
        patient_payment_sums: dict[Payment, int] = {}

        # Получаем оплаты пациента групируем их по датам, складывая их суммы если дата создания больше или равна указанной
        for patient_payment in patient.payments:

            if patient_payment.date_created < current_date:
                continue

            if not patient_payment_sums.get(patient_payment):
                patient_payment_sums[patient_payment] = 0

            patient_payment_sums[patient_payment] += int(float(patient_payment.amount))

        # Обновляем поля оплат пациента
        for patient_payment, payment_sum in patient_payment_sums.items():
            payment_date_position = get_payment_date_position(
                patient_payment.date_created, google_sheet_client=google_sheet_client
            )
            patient_payment_date_position = (
                payment_date_position[0],
                patient_row_position,
            )

            google_sheet_client.update_element_at(
                *patient_payment_date_position, payment_sum
            )
            logger.info(
                "Insert patient %s payment %s by the date: %s",
                patient.code,
                payment_sum,
                patient_payment_date_position,
            )
            time.sleep(1)

        previous_patient_row_position = patient_row_position


def main():
    patients = get_all_patient_data()

    inser_not_exist_patients_excel(patients=patients)


if __name__ == "__main__":
    main()

from datetime import datetime

from app.clinics_card.base import ClinicsCard
from app.clinics_card.entities import Patient, Plan


class ClinicsCardPlan(ClinicsCard):

    def get_plans_by_period(
        self, date_from: str | datetime, date_to: str | datetime
    ):
        params = {"from": date_from, "to": date_to}
        response = self.http_client.get(
            url="/plans", headers=self.headers, params=params
        )
        raw_payments = response.json()["data"]

        payments = [
            Plan(
                id=raw_payment["plan_id"],
                name=raw_payment["plan_name"],
                doctor_id=raw_payment["doctor_id"],
                plan_total=raw_payment["plan_total"],
                plan_total_with_discount=raw_payment["plan_total_with_discount"],
            )
            for raw_payment in raw_payments
        ]
        return payments

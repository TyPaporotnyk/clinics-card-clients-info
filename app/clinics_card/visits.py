from datetime import datetime

from app.clinics_card.base import ClinicsCard
from app.clinics_card.entities import Payment, Visit


class ClinicsCardVisit(ClinicsCard):

    def get_visits_by_period(self, date_from: str | datetime, date_to: str | datetime):
        params = {"from": date_from, "to": date_to}
        response = self.http_client.get(url="/visits", headers=self.headers, params=params)

        raw_payments = response.json()["data"]

        payments = [
            Visit(
                id=raw_payment["visit_id"],
                patient_id=raw_payment["patient_id"],
                status=raw_payment["status"],
                doctor=raw_payment["doctor"],
                date_created=raw_payment["date_created"],
                visit_start=raw_payment["visit_start"],
                visit_end=raw_payment["visit_end"],
            )
            for raw_payment in raw_payments
        ]
        return payments

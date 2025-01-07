from datetime import datetime

from app.clinics_card.base import ClinicsCard
from app.clinics_card.entities import Payment


class ClinicsCardPayment(ClinicsCard):

    def get_payments_by_period(self, date_from: str | datetime, date_to: str | datetime):
        params = {"from": date_from, "to": date_to}
        response = self.http_client.get(url="/payments", headers=self.headers, params=params)
        raw_payments = response.json()["data"]

        payments = [
            Payment(
                id=raw_payment["payment_id"],
                patient_id=raw_payment["patient_id"],
                amount=raw_payment["amount"],
                type=raw_payment["type"],
                date_created=datetime.strptime(raw_payment["date_created"], "%Y-%m-%d %H:%M:%S").replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
                currency=(raw_payment["cash_desk"]["currency"] if raw_payment["cash_desk"] is not None else None),
                status=(raw_payment["cash_desk"]["status"] if raw_payment["cash_desk"] is not None else None),
            )
            for raw_payment in raw_payments
        ]

        return payments

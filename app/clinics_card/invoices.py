from datetime import datetime

from app.clinics_card.base import ClinicsCard
from app.clinics_card.entities import Invoice


class ClinicsCardInvoice(ClinicsCard):

    def get_invoices_by_period(self, date_from: str | datetime, date_to: str | datetime):
        params = {"from": date_from, "to": date_to}
        response = self.http_client.get(url="/invoices", headers=self.headers, params=params)
        raw_invoices = response.json()["data"]

        invoices = [
            Invoice(
                id=raw_invoice["id"],
                patient_id=str(raw_invoice["patient_id"]),
                amount=raw_invoice["amount"],
                date_created=datetime.strptime(raw_invoice["date_created"], "%Y-%m-%d"),
            )
            for raw_invoice in raw_invoices
        ]

        return invoices

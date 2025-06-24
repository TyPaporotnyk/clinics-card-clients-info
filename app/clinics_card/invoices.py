from datetime import datetime

from app.clinics_card.base import ClinicsCard
from app.clinics_card.entities import Invoice

BAN_INVOICE_TYPES = ["PREINVOICE", "INSURANCE"]


class ClinicsCardInvoice(ClinicsCard):

    def _get_invoice_amount(self, invocie_items: list) -> float:
        amount = 0

        for invocie_item in invocie_items:
            price = invocie_item["price"]
            quantity = invocie_item["quantity"]

            item_amount = price * quantity

            amount += item_amount

        return amount

    def get_invoices_by_period(self, date_from: str | datetime, date_to: str | datetime):
        params = {"from": date_from, "to": date_to}
        response = self.http_client.get(url="/invoices", headers=self.headers, params=params)
        raw_invoices = response.json()["data"]

        invoices = [
            Invoice(
                id=raw_invoice["id"],
                patient_id=str(raw_invoice["patient_id"]),
                purpose=raw_invoice["purpose"],
                amount=raw_invoice["amount"],
                date_created=datetime.strptime(raw_invoice["date_created"], "%Y-%m-%d"),
            )
            for raw_invoice in raw_invoices
            if raw_invoice["purpose"] not in BAN_INVOICE_TYPES
        ]

        return invoices

from app.clinics_card.base import ClinicsCard
from app.clinics_card.entities import Patient


class ClinicsCardPatient(ClinicsCard):

    def get_all_patients(self) -> list[Patient]:
        response = self.http_client.get(url="/patients", headers=self.headers)

        raw_patients = response.json()["data"]
        data = [
            Patient(
                id=raw_patient["patient_id"],
                first_name=raw_patient["firstname"],
                last_name=raw_patient["lastname"],
                first_visit_date=raw_patient["first_visit_date"],
                last_visit_date=raw_patient["last_visit_date"],
                code=raw_patient["code"],
                curator=raw_patient["curator"],
                main_plans_id=raw_patient["main_plans_id"]
            )
            for raw_patient in raw_patients
        ]

        return data

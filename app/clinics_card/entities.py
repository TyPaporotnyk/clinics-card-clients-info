from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Payment:
    id: str
    patient_id: str
    amount: str
    type: str
    currency: str | None
    status: str | None
    date_created: datetime

    def __hash__(self):
        return int(self.id)


@dataclass
class Plan:
    id: str
    name: str
    doctor_id: str
    plan_total: str
    plan_total_with_discount: str


@dataclass
class Visit:
    id: str
    patient_id: str
    status: str
    doctor: str
    date_created: str
    visit_start: str | None
    visit_end: str | None


@dataclass
class Invoice:
    id: str
    patient_id: str
    date_created: datetime
    amount: str


@dataclass
class Patient:
    id: str
    first_name: str
    last_name: str
    code: str
    curator: str
    first_visit_date: str | None
    last_visit_date: str | None
    main_plans_id: str | None
    row_position: int | None = field(default=None)
    main_plans: Plan | None = field(default=None)
    payments: list[Payment] = field(default_factory=list, kw_only=True)
    visits: list[Visit] = field(default_factory=list, kw_only=True)
    invoices: list[Invoice] = field(default_factory=list, kw_only=True)

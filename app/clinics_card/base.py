from dataclasses import dataclass

from httpx import Client


@dataclass
class ClinicsCard:
    http_client: Client
    api_key: str

    @property
    def headers(self):
        return {"Token": self.api_key, "Content-Type": "application/json"}

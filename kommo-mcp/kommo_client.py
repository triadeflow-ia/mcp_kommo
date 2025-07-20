import os
import httpx

class KommoClient:
    def __init__(self):
        self.base_url = os.environ["KOMMO_DOMAIN"] + "/api/v4"
        self.headers = {
            "Authorization": f"Bearer {os.environ['KOMMO_API_TOKEN']}"
        }

    def get_leads(self, limit=10):
        url = f"{self.base_url}/leads?limit={limit}"
        response = httpx.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

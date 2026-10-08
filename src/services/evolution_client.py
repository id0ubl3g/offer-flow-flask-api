import httpx

DEFAULT_TIMEOUT = 15
GROUPS_TIMEOUT = 120

class EvolutionError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

class EvolutionClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"apikey": api_key},
            timeout=DEFAULT_TIMEOUT
        )

    def _request(self, method: str, path: str, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> dict | list:
        try:
            response = self.http.request(method, path, timeout=timeout, **kwargs)

        except httpx.TimeoutException:
            raise EvolutionError(504, "WhatsApp service timed out")

        except httpx.HTTPError:
            raise EvolutionError(502, "WhatsApp service is unavailable")

        if response.is_error:
            raise EvolutionError(response.status_code, self._error_message(response))

        return response.json()

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            message = response.json().get("response", {}).get("message")

        except Exception:
            return response.text[:200]

        if isinstance(message, list):
            return "; ".join(str(item) for item in message)

        return str(message)

    def create_instance(self, instance_name: str, webhook_url: str, webhook_secret: str) -> dict:
        return self._request("POST", "/instance/create", json={
            "instanceName": instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
            "groupsIgnore": True,
            "webhook": {
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "headers": {"x-webhook-secret": webhook_secret},
                "events": ["QRCODE_UPDATED", "CONNECTION_UPDATE"]
            }
        })

    def connect(self, instance_name: str) -> dict:
        return self._request("GET", f"/instance/connect/{instance_name}")

    def connection_state(self, instance_name: str) -> str:
        return self._request("GET", f"/instance/connectionState/{instance_name}")["instance"]["state"]

    def fetch_instance(self, instance_name: str) -> dict | None:
        try:
            instances = self._request("GET", "/instance/fetchInstances", params={"instanceName": instance_name})

        except EvolutionError as e:
            if e.status_code == 404:
                return None

            raise

        return instances[0] if instances else None

    def logout(self, instance_name: str) -> None:
        self._request("DELETE", f"/instance/logout/{instance_name}")

    def delete_instance(self, instance_name: str) -> None:
        self._request("DELETE", f"/instance/delete/{instance_name}")

    def fetch_groups(self, instance_name: str) -> list[dict]:
        return self._request(
            "GET",
            f"/group/fetchAllGroups/{instance_name}",
            timeout=GROUPS_TIMEOUT,
            params={"getParticipants": "true"}
        )

    def send_text(self, instance_name: str, jid: str, text: str) -> dict:
        return self._request("POST", f"/message/sendText/{instance_name}", json={
            "number": jid,
            "text": text,
            "linkPreview": True
        })

    def send_image(self, instance_name: str, jid: str, image_url: str, mimetype: str, caption: str) -> dict:
        return self._request("POST", f"/message/sendMedia/{instance_name}", json={
            "number": jid,
            "mediatype": "image",
            "mimetype": mimetype,
            "media": image_url,
            "caption": caption,
            "fileName": image_url.rsplit("/", 1)[-1]
        })
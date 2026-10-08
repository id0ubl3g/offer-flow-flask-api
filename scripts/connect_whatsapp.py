from getpass import getpass
import subprocess
import tempfile
import base64
import httpx
import time
import sys
import os

API_URL = os.getenv("API_URL", "http://localhost:5000")
CONNECT_TIMEOUT = 180
POLL_INTERVAL = 3

def save_qrcode(qrcode: str) -> str:
    path = os.path.join(tempfile.gettempdir(), "offer-flow-whatsapp-qr.png")

    with open(path, "wb") as file:
        file.write(base64.b64decode(qrcode.split(",", 1)[-1]))

    return path

def fail(response: httpx.Response) -> None:
    print(f"Erro {response.status_code}: {response.json().get('error', response.text)}")
    sys.exit(1)

def main() -> None:
    client = httpx.Client(base_url=API_URL, timeout=150)

    email = input("E-mail: ").strip()
    password = getpass("Senha: ")

    response = client.post("/auth/login", json={"email": email, "password": password})

    if response.status_code != 200:
        fail(response)

    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"

    status = client.get("/whatsapp")

    if status.status_code == 200 and status.json()["instance"]["status"] == "open":
        print("WhatsApp já está conectado.")

    else:
        response = client.post("/whatsapp/connect")

        if response.status_code != 200:
            fail(response)

        qrcode = response.json()["qrcode"]
        path = save_qrcode(qrcode)

        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"QR code salvo em {path}")
        print("No celular: WhatsApp > Aparelhos conectados > Conectar um aparelho")

        deadline = time.time() + CONNECT_TIMEOUT

        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)

            data = client.get("/whatsapp").json()

            if data["instance"]["status"] == "open":
                print(f"Conectado: {data['instance']['phone']}")
                break

            if data.get("qrcode") and data["qrcode"] != qrcode:
                qrcode = data["qrcode"]
                save_qrcode(qrcode)
                print("QR code atualizado, reabra a imagem se o visualizador não recarregar.")

        else:
            print("Tempo esgotado sem conexão. Rode o script de novo.")
            sys.exit(1)

    print("Sincronizando grupos...")

    response = client.post("/whatsapp/groups/sync")

    if response.status_code != 200:
        fail(response)

    groups = response.json()["groups"]

    print(f"{len(groups)} grupos sincronizados:")

    for group in groups:
        permission = "pode enviar" if group["can_send"] else "só admins enviam"
        print(f"  - {group['name'] or '(sem nome)'} | {group['participants_count']} membros | {permission}")

if __name__ == "__main__":
    main()
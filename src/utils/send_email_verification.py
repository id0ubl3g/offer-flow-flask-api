from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import smtplib
import os

load_dotenv()

class SendEmailVerification:
    def __init__(self) -> None:
        self.sender_email:str = os.getenv('sender_email')
        self.sender_password:str = os.getenv('sender_password')
        
    def send_verification_email(self, recipient_email: str, verification_code_or_link: str, type_email: str) -> None:
        match type_email:
            case 'reset_password':
                subject = "Password reset"
                text = f"{verification_code_or_link}"
            case _:
                raise ValueError(f"Unsupported email type: {type_email}")

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = recipient_email

        part = MIMEText(text, "plain")
        message.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, recipient_email, message.as_string())
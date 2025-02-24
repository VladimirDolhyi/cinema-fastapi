import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from jinja2 import Environment, FileSystemLoader

from src.exceptions import BaseEmailError
from src.notifications.interfaces import EmailSenderInterface


class EmailSender(EmailSenderInterface):
    def __init__(
            self,
            hostname: str,
            port: int,
            email: str,
            password: str,
            use_tls: bool,
            template_dir: str,
            activation_email_template_name: str,
            password_reset_template_name: str,
            password_change_name: str
    ):
        self._hostname = hostname
        self._port = port
        self._email = email
        self._password = password
        self._use_tls = use_tls
        self._activation_email_template_name = activation_email_template_name
        self._password_reset_template_name = password_reset_template_name
        self._password_change = password_change_name

        self._env = Environment(loader=FileSystemLoader(template_dir))

    def _send_email(self, email: str, subject: str, html_content: str) -> None:
        message = MIMEMultipart()
        message["From"] = self._email
        message["To"] = email
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP(self._hostname, self._port) as server:
                if self._use_tls:
                    server.starttls()
                server.login(self._email, self._password)
                server.sendmail(self._email, email, message.as_string())
        except smtplib.SMTPException as error:
            logging.error(f"Failed to send email to {email}: {error}")
            raise BaseEmailError(f"Failed to send email to {email}: {error}")

    def send_activation_email(self, email: str, activation_link: str) -> None:
        template = self._env.get_template(self._activation_email_template_name)
        html_content = template.render(email=email, activation_link=activation_link)

        subject = "Registration"
        self._send_email(email, subject, html_content)

    def send_password_reset_email(self, email: str, reset_link: str) -> None:
        template = self._env.get_template(self._password_reset_template_name)
        html_content = template.render(email=email, reset_link=reset_link)

        subject = "Password Reset Request"
        self._send_email(email, subject, html_content)

    def send_password_change(self, email: str) -> None:
        template = self._env.get_template(self._password_change)
        html_content = template.render(email=email)

        subject = "Password Successfully Changed"
        self._send_email(email, subject, html_content)

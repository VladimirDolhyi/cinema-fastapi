from abc import ABC, abstractmethod


class EmailSenderInterface(ABC):

    @abstractmethod
    def send_activation_email(self, email: str, activation_link: str) -> None:
        pass

    @abstractmethod
    def send_password_reset_email(self, email: str, reset_link: str) -> None:
        pass

    @abstractmethod
    def send_password_change(self, email: str) -> None:
        pass

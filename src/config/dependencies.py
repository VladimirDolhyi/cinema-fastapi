import os

from fastapi import Depends, status, HTTPException

from src.config.settings import TestingSettings, Settings, BaseAppSettings
from src.exceptions import BaseSecurityError
from src.notifications.emails import EmailSender
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface
from src.security.token_manager import JWTAuthManager
from src.storages.interfaces import S3StorageInterface
from src.storages.s3 import S3StorageClient


def get_settings() -> BaseAppSettings:
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "testing":
        return TestingSettings()
    return Settings()


def get_jwt_auth_manager(settings: Settings = Depends(get_settings)) -> JWTAuthManagerInterface:
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


def get_accounts_email_notificator(settings: BaseAppSettings = Depends(get_settings)) -> EmailSender:
    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_USERNAME,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        from_name=settings.EMAIL_FROM_NAME,
        use_tls=settings.EMAIL_USE_TLS,
    )


def get_current_user_id(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> int:
    """
    Extracts the user ID from the provided JWT token.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        return payload.get("user_id")
    except BaseSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )


def get_s3_storage_client(settings: BaseAppSettings = Depends(get_settings)) -> S3StorageInterface:
    return S3StorageClient(
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        access_key=settings.S3_STORAGE_ACCESS_KEY,
        secret_key=settings.S3_STORAGE_SECRET_KEY,
        bucket_name=settings.S3_BUCKET_NAME
    )

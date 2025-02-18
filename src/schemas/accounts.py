from pydantic import BaseModel, EmailStr, field_validator

from src.database.validators import accounts as accounts_validators


class BaseEmailPasswordSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {
        "from_attributes": True
    }

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return accounts_validators.validate_password_strength(value)


class UserRegistrationRequestSchema(BaseEmailPasswordSchema):
    pass


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {
        "from_attributes": True
    }


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class MessageResponseSchema(BaseModel):
    message: str


class UserLoginRequestSchema(BaseEmailPasswordSchema):
    pass


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequestSchema(BaseEmailPasswordSchema):
    token: str


class PasswordChangeRequestSchema(UserRegistrationRequestSchema):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str):
        return accounts_validators.validate_password_strength(value)


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"

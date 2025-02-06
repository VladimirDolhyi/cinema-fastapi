import enum
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional

from sqlalchemy import (
    ForeignKey,
    String,
    Boolean,
    DateTime,
    Enum,
    Integer,
    func,
    Text,
    Date,
    UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates
)

from base import Base
# from database.validators import accounts as validators
# from security.passwords import hash_password, verify_password
# from security.utils import generate_secure_token


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroup(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[UserGroupEnum] = mapped_column(Enum(UserGroupEnum), nullable=False, unique=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="group")

    def __repr__(self):
        return f"<UserGroup(id={self.id}, name={self.name})>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    _hashed_password: Mapped[str] = mapped_column("hashed_password", String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False)
    group: Mapped["UserGroup"] = relationship("UserGroup", back_populates="users")

    activation_token: Mapped[Optional["ActivationToken"]] = relationship(
        "ActivationToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    password_reset_token: Mapped[Optional["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<UserModel(id={self.id}, email={self.email}, is_active={self.is_active})>"

    # def has_group(self, group_name: UserGroupEnum) -> bool:
    #     return self.group.name == group_name
    #
    # @classmethod
    # def create(cls, email: str, raw_password: str, group_id: int | Mapped[int]) -> "UserModel":
    #     """
    #     Factory method to create a new UserModel instance.
    #
    #     This method simplifies the creation of a new user by handling
    #     password hashing and setting required attributes.
    #     """
    #     user = cls(email=email, group_id=group_id)
    #     user.password = raw_password
    #     return user
    #
    # @property
    # def password(self) -> None:
    #     raise AttributeError("Password is write-only. Use the setter to set the password.")
    #
    # @password.setter
    # def password(self, raw_password: str) -> None:
    #     """
    #     Set the user's password after validating its strength and hashing it.
    #     """
    #     validators.validate_password_strength(raw_password)
    #     self._hashed_password = hash_password(raw_password)
    #
    # def verify_password(self, raw_password: str) -> bool:
    #     """
    #     Verify the provided password against the stored hashed password.
    #     """
    #     return verify_password(raw_password, self._hashed_password)
    #
    # @validates("email")
    # def validate_email(self, key, value):
    #     return validators.validate_email(value.lower())

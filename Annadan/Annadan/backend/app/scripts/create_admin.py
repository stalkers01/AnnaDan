"""Create the first administrator interactively; admin is never a public signup role."""

from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Donation, FoodRequest, Rating, RequestEvent, User  # noqa: F401
from app.models.entities import User
from app.models.enums import UserRole


def main() -> None:
    print("Create an Annadan administrator account")
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    phone = input("Phone: ").strip()
    password = getpass("Password (minimum 10 characters): ")
    confirmation = getpass("Confirm password: ")

    if len(full_name) < 2 or "@" not in email or len(phone) < 7:
        raise SystemExit("Please enter a valid name, email address, and phone number.")
    if len(password) < 10:
        raise SystemExit("Password must contain at least 10 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.email == email))
        if exists:
            raise SystemExit("An account with this email already exists.")

        admin = User(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            email_verified=True,
            phone_verified=True,
            settings={"email_updates": True, "sms_updates": False},
        )
        db.add(admin)
        db.commit()

    print(f"Administrator created: {email}")


if __name__ == "__main__":
    main()

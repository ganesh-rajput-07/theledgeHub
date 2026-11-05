"""Admin accounts from the command line:  python -m app.cli create-admin you@example.com "Your Name"."""

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import AdminUser
from app.security import MIN_PASSWORD_LENGTH, hash_password
from app.services import audit


def _password() -> str:
    while True:
        first = getpass.getpass(f"Password (at least {MIN_PASSWORD_LENGTH} characters): ")
        if len(first) < MIN_PASSWORD_LENGTH:
            print("Too short.")
        elif first != getpass.getpass("Repeat password: "):
            print("Passwords don't match.")
        else:
            return first


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="create an admin, or reset an existing admin's password")
    create.add_argument("email")
    create.add_argument("name", nargs="?", default="Admin")
    args = parser.parse_args()

    with SessionLocal() as db:
        admin = db.scalar(select(AdminUser).where(func.lower(AdminUser.email) == args.email.lower()))
        password = _password()
        if admin:
            admin.password_hash, admin.failed_logins, admin.locked_until, admin.is_active = (
                hash_password(password),
                0,
                None,
                True,
            )
            audit(db, admin, "admin.password", f"Password reset from the command line for {admin.email}")
            print(f"Password reset for {admin.email}.")
        else:
            admin = AdminUser(email=args.email.lower(), name=args.name, password_hash=hash_password(password))
            db.add(admin)
            db.flush()
            audit(db, admin, "admin.create", f"Admin {admin.email} created from the command line")
            print(f"Admin {admin.email} created.")
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())

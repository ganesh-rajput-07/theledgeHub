"""Command line tools.

python -m app.cli create-admin you@example.com "Your Name"   create an admin, or reset their password
python -m app.cli generate-keys                              create the lease signing key (once)
"""

import argparse
import getpass
import sys
from pathlib import Path

from sqlalchemy import func, select

from app import lease
from app.config import get_settings
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
    sub.add_parser("generate-keys", help="create the Ed25519 key that signs licence leases")
    args = parser.parse_args()

    if args.command == "generate-keys":
        path = Path(get_settings().lease_private_key_file)
        if path.exists():
            print(f"{path} already exists. Replacing it would log out every desktop app; refusing.")
            return 1
        public = lease.generate_keypair(path)
        print(f"Private key written to {path} (keep it secret and backed up).\nPublic key for the desktop app:\n")
        print(public)
        return 0

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

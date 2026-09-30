"""Trusted local operator commands. No public role-promotion endpoint."""

import argparse

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import make_engine, make_session_factory
from app.models.auth_session import AuthSession
from app.models.user import Role, User
from app.schemas.auth import Credentials


def main():
    parser = argparse.ArgumentParser(description="StreamDoctor local account administration")
    sub = parser.add_subparsers(dest="command", required=True)
    role = sub.add_parser("set-role", help="Assign a role to an existing registered account")
    role.add_argument("email")
    role.add_argument("role", choices=[r.value for r in Role])
    disable = sub.add_parser("disable-user", help="Disable an account and revoke all its sessions")
    disable.add_argument("email")
    args = parser.parse_args()
    email = str(Credentials(email=args.email, password="validation-only").email)
    engine = make_engine(get_settings().database_url)
    with make_session_factory(engine)() as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            parser.exit(1, "Account not found. Register the account first.\n")
        if args.command == "set-role":
            user.role = Role(args.role)
        else:
            user.is_active = False
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        db.commit()
    engine.dispose()
    print("Account updated; existing sessions revoked. Sign in again if active.")


if __name__ == "__main__":
    main()

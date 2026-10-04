"""Admin foydalanuvchi yaratish yoki parolini almashtirish.

    python -m scripts.create_admin LOGIN
"""

import getpass
import sys

from sqlalchemy import select

from app.admin.auth import hash_password
from app.db import SessionLocal
from app.models import AdminUser


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    username = sys.argv[1].strip()
    password = getpass.getpass("Parol (kamida 10 belgi): ")
    if len(password) < 10:
        sys.exit("Parol juda qisqa.")
    if password != getpass.getpass("Parolni takrorlang: "):
        sys.exit("Parollar mos emas.")

    with SessionLocal() as db:
        user = db.scalars(select(AdminUser).where(AdminUser.username == username)).first()
        if user:
            user.password_hash = hash_password(password)
            user.is_active = True
            print(f"'{username}' paroli yangilandi.")
        else:
            db.add(AdminUser(username=username, password_hash=hash_password(password)))
            print(f"'{username}' admin yaratildi.")
        db.commit()


if __name__ == "__main__":
    main()

"""Configure book public key and local service credentials without printing them."""

import secrets
from pathlib import Path

from dotenv import dotenv_values


def replace_values(path, replacements):
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.partition("=")[0] not in replacements
    ]
    for key, value in replacements.items():
        escaped = value.replace("\n", "\\n")
        lines.append(f'{key}="{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def configured(value):
    return bool(value and not value.startswith("CHANGE_ME"))


def main():
    root = Path(__file__).resolve().parent.parent
    user_path = root / "services/user-service/.env"
    book_path = root / "services/book-service/.env"
    if not user_path.exists() or not book_path.exists():
        raise SystemExit("Run setup_dev_env.py and setup_user_jwt.py first.")
    user, book = dotenv_values(user_path), dotenv_values(book_path)
    public = user.get("JWT_PUBLIC_KEY", "")
    if not public.startswith("-----BEGIN PUBLIC KEY-----"):
        raise SystemExit("User JWT public key missing; configure it first.")
    if (
        configured(book.get("JWT_PUBLIC_KEY"))
        and book["JWT_PUBLIC_KEY"] != public
    ):
        raise SystemExit(
            "Existing book public key differs; existing files preserved."
        )
    left, right = user.get("BOOK_SERVICE_TOKEN", ""), book.get(
        "BOOK_SERVICE_TOKEN", ""
    )
    if configured(left) and configured(right) and left != right:
        raise SystemExit(
            "Existing book service credentials differ; preserved."
        )
    credential = (
        left
        if configured(left)
        else right if configured(right) else secrets.token_hex(32)
    )
    borrow_credential = book.get("BORROW_SERVICE_TOKEN", "")
    if not configured(borrow_credential):
        borrow_credential = secrets.token_hex(32)
    replace_values(user_path, {"BOOK_SERVICE_TOKEN": credential})
    replace_values(
        book_path,
        {
            "JWT_PUBLIC_KEY": public,
            "BOOK_SERVICE_TOKEN": credential,
            "BORROW_SERVICE_TOKEN": borrow_credential,
        },
    )
    print(
        "Book public key and service credentials configured; private key not copied."
    )


if __name__ == "__main__":
    main()

"""Match local service credentials and copy only the user public key."""

import secrets
from pathlib import Path

from dotenv import dotenv_values

from setup_book_auth import configured, replace_values


def main():
    root = Path(__file__).resolve().parent.parent
    paths = {
        name: root / "services" / name / ".env"
        for name in ("user-service", "book-service", "borrow-service")
    }
    if any(not path.exists() for path in paths.values()):
        raise SystemExit(
            "Run setup_dev_env.py, setup_user_jwt.py and setup_book_auth.py first."
        )
    values = {name: dotenv_values(path) for name, path in paths.items()}
    public = values["user-service"].get("JWT_PUBLIC_KEY", "")
    if not public.startswith("-----BEGIN PUBLIC KEY-----"):
        raise SystemExit("User JWT public key missing.")
    existing_public = values["borrow-service"].get("JWT_PUBLIC_KEY", "")
    if configured(existing_public) and existing_public != public:
        raise SystemExit("Existing borrow public key differs; preserved.")
    existing = [values[name].get("BORROW_SERVICE_TOKEN", "") for name in paths]
    configured_values = {item for item in existing if configured(item)}
    if len(configured_values) > 1:
        raise SystemExit("Existing borrow service credentials differ; preserved.")
    credential = next(iter(configured_values), secrets.token_hex(32))
    for name, path in paths.items():
        replacements = {"BORROW_SERVICE_TOKEN": credential}
        if name == "borrow-service":
            replacements["JWT_PUBLIC_KEY"] = public
        replace_values(path, replacements)
    print(
        "Borrow public key and matching service credential configured; no private key copied."
    )


if __name__ == "__main__":
    main()

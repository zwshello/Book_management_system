"""Configure one independent statistics service credential and JWT public key."""

import secrets
from pathlib import Path

from dotenv import dotenv_values

from setup_book_auth import configured, replace_values


def main():
    root = Path(__file__).resolve().parent.parent
    names = ("user-service", "book-service", "borrow-service", "statistics-service")
    paths = {name: root / "services" / name / ".env" for name in names}
    if any(not path.exists() for path in paths.values()):
        raise SystemExit("Generate local service .env files first.")
    values = {name: dotenv_values(path) for name, path in paths.items()}
    public = values["user-service"].get("JWT_PUBLIC_KEY", "")
    if not public.startswith("-----BEGIN PUBLIC KEY-----"):
        raise SystemExit("User JWT public key missing.")
    existing_public = values["statistics-service"].get("JWT_PUBLIC_KEY", "")
    if configured(existing_public) and existing_public != public:
        raise SystemExit("Existing statistics public key differs; preserved.")
    credentials = {values[name].get("STATISTICS_SERVICE_TOKEN", "") for name in names}
    credentials = {value for value in credentials if configured(value)}
    if len(credentials) > 1:
        raise SystemExit("Existing statistics credentials differ; preserved.")
    credential = next(iter(credentials), secrets.token_hex(32))
    for name, path in paths.items():
        updates = {"STATISTICS_SERVICE_TOKEN": credential}
        if name == "statistics-service":
            updates["JWT_PUBLIC_KEY"] = public
        replace_values(path, updates)
    print("Statistics credential and public key configured; no private key copied.")


if __name__ == "__main__":
    main()

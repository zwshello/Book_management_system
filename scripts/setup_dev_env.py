"""Generate stage-2 local configuration; never overwrite an existing .env."""

import re
import secrets
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent.parent
PASSWORD_KEYS = (
    "MYSQL_ROOT_PASSWORD",
    "USER_MYSQL_PASSWORD",
    "BOOK_MYSQL_PASSWORD",
    "BORROW_MYSQL_PASSWORD",
)
SERVICE_DATABASES = {
    "user-service": ("user_db", "user_app", "USER_MYSQL_PASSWORD"),
    "book-service": ("book_db", "book_app", "BOOK_MYSQL_PASSWORD"),
    "borrow-service": ("borrow_db", "borrow_app", "BORROW_MYSQL_PASSWORD"),
}


def render_template(template: Path, replacements: dict[str, str]) -> str:
    lines = []
    for line in template.read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        if key in replacements:
            line = f"{key}={replacements[key]}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> None:
    root_env = ROOT / ".env"
    planned_files = {}
    if root_env.exists():
        values = dotenv_values(root_env)
    else:
        values = dict(dotenv_values(ROOT / ".env.example"))
        values.update({key: secrets.token_hex(24) for key in PASSWORD_KEYS})
        planned_files[root_env] = render_template(
            ROOT / ".env.example", {key: values[key] for key in PASSWORD_KEYS}
        )

    for key in PASSWORD_KEYS:
        if not re.fullmatch(r"[0-9a-f]{32,128}", values.get(key) or ""):
            raise SystemExit(f"Invalid {key} in root .env; existing files preserved.")
    port = values.get("MYSQL_PORT") or "3306"
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise SystemExit("Invalid MYSQL_PORT; existing files preserved.")

    for service in (*SERVICE_DATABASES, "statistics-service"):
        directory = ROOT / "services" / service
        env_file = directory / ".env"
        replacements = {"DJANGO_SECRET_KEY": secrets.token_hex(32)}
        if service in SERVICE_DATABASES:
            database, username, password_key = SERVICE_DATABASES[service]
            replacements.update({
                "MYSQL_HOST": "127.0.0.1",
                "MYSQL_PORT": port,
                "MYSQL_DATABASE": database,
                "MYSQL_USER": username,
                "MYSQL_PASSWORD": values[password_key],
            })
        if env_file.exists():
            existing = dotenv_values(env_file)
            if not existing.get("DJANGO_SECRET_KEY") or existing[
                "DJANGO_SECRET_KEY"
            ].startswith("CHANGE_ME"):
                raise SystemExit(f"Configure {service} DJANGO_SECRET_KEY manually.")
            for key, value in replacements.items():
                if key.startswith("MYSQL_") and existing.get(key) != value:
                    raise SystemExit(
                        f"{service} {key} differs from Compose; "
                        "existing files preserved."
                    )
            continue
        planned_files[env_file] = render_template(
            directory / ".env.example", replacements
        )

    for path, content in planned_files.items():
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        print(f"Created {path.relative_to(ROOT)} (secrets hidden)")
    print("Local configuration ready; no existing files overwritten.")


if __name__ == "__main__":
    main()

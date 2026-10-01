"""Generate local RSA PEM environment values without printing private keys."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parent.parent
    env_file = root / "services" / "user-service" / ".env"
    if not env_file.exists():
        raise SystemExit("Run setup_dev_env.py first.")
    values = dotenv_values(env_file)
    keys = [
        values.get(name, "") for name in ("JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY")
    ]
    configured = [
        bool(key and not key.startswith("CHANGE_ME")) for key in keys
    ]
    if all(configured):
        private = serialization.load_pem_private_key(
            keys[0].replace("\\n", "\n").encode(), None
        )
        public = serialization.load_pem_public_key(
            keys[1].replace("\\n", "\n").encode()
        )
        if private.public_key().public_numbers() != public.public_numbers():
            raise SystemExit(
                "Existing JWT key pair does not match; preserved."
            )
        print("Existing JWT key pair valid; preserved.")
        return
    if any(configured):
        raise SystemExit(
            "Incomplete existing JWT key pair; preserved for manual repair."
        )
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    replacements = {
        "JWT_PRIVATE_KEY": private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "JWT_PUBLIC_KEY": private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    }
    lines = [
        line
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line.partition("=")[0] not in replacements
    ]
    for name, value in replacements.items():
        escaped = value.replace("\n", "\\n")
        lines.append(f'{name}="{escaped}"')
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "Generated local RSA key pair in ignored user-service .env (keys hidden)."
    )


if __name__ == "__main__":
    main()

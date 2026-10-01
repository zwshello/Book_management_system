"""Verify real MySQL connections, isolated migrations and standard runserver."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
SERVICES = {
    "user-service": (8001, "user_db", "book_db"),
    "book-service": (8002, "book_db", "borrow_db"),
    "borrow-service": (8003, "borrow_db", "user_db"),
    "statistics-service": (8004, None, None),
}


def manage(service: str, *arguments: str, database: str | None = None) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if database:
        environment["MYSQL_DATABASE"] = database
    result = subprocess.run(
        [sys.executable, "manage.py", *arguments],
        cwd=ROOT / "services" / service,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    print(f"[{service}] {' '.join(arguments[:1])}")
    print(result.stdout.strip())
    if result.returncode:
        print(result.stderr.strip())
        raise RuntimeError(f"{service}: management command failed")


def verify_databases() -> None:
    for service, (_, database, other_database) in SERVICES.items():
        manage(service, "check")
        if database is None:
            manage(
                service, "shell", "-c",
                "from django.conf import settings; "
                "assert settings.DATABASES['default']['ENGINE'] == "
                "'django.db.backends.dummy'; print('No business DB: migration N/A')",
            )
            continue
        code = f"""
from django.db import connection, DatabaseError
assert connection.settings_dict['ENGINE'] == 'django.db.backends.mysql'
with connection.cursor() as cursor:
    cursor.execute('SELECT DATABASE(), VERSION(), 1')
    result = cursor.fetchone()
    assert result[0] == {database!r} and result[2] == 1
    print('Connected:', result)
    cursor.execute('SHOW TABLES')
    tables = cursor.fetchall()
    print('Development DB table count:', len(tables))
    if {service!r} == 'user-service':
        assert not tables, 'user_db must remain empty before custom user model'
    try:
        cursor.execute('USE ' + {other_database!r})
    except DatabaseError as error:
        assert error.args[0] == 1044, 'Unexpected cross-service access error'
        print('Cross-service DB access correctly denied (1044)')
    else:
        raise AssertionError('Cross-service database access was allowed')
"""
        manage(service, "shell", "-c", code)
        validation_database = database + "_migration_check"
        manage(service, "migrate", "--noinput", database=validation_database)
        manage(
            service, "shell", "-c",
            "from django.db import connection; "
            "from django.db.migrations.executor import MigrationExecutor; "
            "executor = MigrationExecutor(connection); "
            "assert not executor.migration_plan(executor.loader.graph.leaf_nodes()); "
            "print('Applied migrations:', len(executor.loader.applied_migrations))",
            database=validation_database,
        )
        manage(service, "migrate", "--noinput", database=validation_database)


def verify_runservers() -> None:
    log_directory = ROOT / "tmp" / "stage2-runserver"
    log_directory.mkdir(parents=True, exist_ok=True)
    processes = []
    try:
        for service, (port, _, _) in SERVICES.items():
            log_path = log_directory / f"{service}.log"
            stream = log_path.open("w", encoding="utf-8")
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONUNBUFFERED"] = "1"
            process = subprocess.Popen(
                [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}",
                 "--noreload"],
                cwd=ROOT / "services" / service,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append((service, port, process, stream, log_path))

        for service, port, process, _, log_path in processes:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(log_path.read_text(encoding="utf-8"))
                try:
                    url = f"http://127.0.0.1:{port}/health/live"
                    with urlopen(url, timeout=2) as response:
                        data = json.load(response)
                        assert response.status == 200
                        assert data == {"service": service, "status": "live"}
                    print(f"[{service}] standard runserver :{port}: HTTP 200 {data}")
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() > deadline:
                        raise RuntimeError(log_path.read_text(encoding="utf-8"))
                    time.sleep(0.25)
    finally:
        for _, _, process, stream, _ in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
            stream.close()
        print("Verification runservers stopped; MySQL is kept running.")


if __name__ == "__main__":
    verify_databases()
    verify_runservers()
    print("Stage 2 MySQL verification passed (business migrations not performed).")

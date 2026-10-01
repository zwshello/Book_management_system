#!/bin/bash
# Works both sourced and executable, including Windows bind mounts.
set -e

# Restrict passwords to generated hex to keep SQL interpolation unambiguous.
for password in "$USER_MYSQL_PASSWORD" "$BOOK_MYSQL_PASSWORD" "$BORROW_MYSQL_PASSWORD"; do
    if [[ ! "$password" =~ ^[0-9a-f]{32,128}$ ]]; then
        echo "Use scripts/setup_dev_env.py to generate local hex passwords." >&2
        exit 1
    fi
done

MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
CREATE DATABASE IF NOT EXISTS user_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Isolated user-service test database. Never run tests against user_db.
CREATE DATABASE IF NOT EXISTS user_db_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS book_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS book_db_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS borrow_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS borrow_db_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Disposable stage-2 migration validation schemas; never used by runserver.
CREATE DATABASE IF NOT EXISTS user_db_migration_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS book_db_migration_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS borrow_db_migration_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'user_app'@'%' IDENTIFIED BY '$USER_MYSQL_PASSWORD';
CREATE USER IF NOT EXISTS 'book_app'@'%' IDENTIFIED BY '$BOOK_MYSQL_PASSWORD';
CREATE USER IF NOT EXISTS 'borrow_app'@'%' IDENTIFIED BY '$BORROW_MYSQL_PASSWORD';
GRANT ALL PRIVILEGES ON user_db.* TO 'user_app'@'%';
GRANT ALL PRIVILEGES ON user_db_test.* TO 'user_app'@'%';
GRANT ALL PRIVILEGES ON book_db.* TO 'book_app'@'%';
GRANT ALL PRIVILEGES ON book_db_test.* TO 'book_app'@'%';
GRANT ALL PRIVILEGES ON borrow_db.* TO 'borrow_app'@'%';
GRANT ALL PRIVILEGES ON borrow_db_test.* TO 'borrow_app'@'%';
GRANT ALL PRIVILEGES ON user_db_migration_check.* TO 'user_app'@'%';
GRANT ALL PRIVILEGES ON book_db_migration_check.* TO 'book_app'@'%';
GRANT ALL PRIVILEGES ON borrow_db_migration_check.* TO 'borrow_app'@'%';
SQL

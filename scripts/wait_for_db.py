#!/usr/bin/env python

import os
import sys
import time

import psycopg2

MAX_RETRIES = 30
RETRY_INTERVAL = 2


def main():
    if os.getenv("DB_ENGINE", "").endswith("sqlite3"):
        print("SQLite mode — skipping DB wait.")
        return

    db_name = os.getenv("DB_NAME", "supportai")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
            )
            conn.close()
            print("Database is ready!")
            return
        except psycopg2.OperationalError:
            print(f"Database not ready (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(RETRY_INTERVAL)

    print("Could not connect to database.")
    sys.exit(1)


if __name__ == "__main__":
    main()

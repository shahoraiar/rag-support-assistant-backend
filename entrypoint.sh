#!/bin/bash
set -e

echo "==> Waiting for database..."
python scripts/wait_for_db.py

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

# if [ "${SEED_DEMO_DATA}" = "true" ]; then
#     echo "==> Seeding demo data..."
#     python manage.py seed_demo_data
# fi

echo "==> Starting application..."
exec "$@"

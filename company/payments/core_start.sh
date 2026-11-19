#!/bin/bash
# Starts the API: its own database, its signing key (kept for the container's life), migration, sample data, server.
set -e
service postgresql start >/dev/null 2>&1
su postgres -c "psql -qc \"CREATE ROLE saleor SUPERUSER LOGIN PASSWORD 'saleor'\" -c 'CREATE DATABASE saleor OWNER saleor'" >/dev/null 2>&1 || true
mkdir -p /var/lib/seedco
[ -f /var/lib/seedco/rsa.pem ] || openssl genrsa -out /var/lib/seedco/rsa.pem 2048 2>/dev/null
export RSA_PRIVATE_KEY="$(cat /var/lib/seedco/rsa.pem)"
cd /srv/core
python manage.py migrate > /var/log/core-migrate.log 2>&1
if [ ! -f /var/lib/seedco/populated ]; then
  python manage.py populatedb --createsuperuser > /var/log/core-populate.log 2>&1 && touch /var/lib/seedco/populated
fi
exec python manage.py runserver 0.0.0.0:8000 --noreload

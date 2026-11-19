#!/bin/bash
# Starts the payment provider's stand-in as https://api.stripe.com: makes a certificate authority and a certificate
# for that name (the authority's certificate goes to /certs, which the payment app's container trusts), then serves.
set -e
mkdir -p /var/lib/provider && cd /var/lib/provider
if [ ! -f ca.pem ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=SeedCo test authority" -keyout ca.key -out ca.pem 2>/dev/null
  openssl req -newkey rsa:2048 -nodes -subj "/CN=api.stripe.com" -keyout api.key -out api.csr 2>/dev/null
  printf 'subjectAltName=DNS:api.stripe.com,DNS:provider\n' > san.cnf
  openssl x509 -req -in api.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 3650 -extfile san.cnf -out api.pem 2>/dev/null
fi
cp ca.pem /certs/ca.pem && chmod 644 /certs/ca.pem
exec env TLS_CERT=/var/lib/provider/api.pem TLS_KEY=/var/lib/provider/api.key python3 /opt/seedco/stripe_mock.py

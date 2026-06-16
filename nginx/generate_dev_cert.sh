#!/usr/bin/env bash
# Generates a self-signed TLS cert for local/dev use.
# Run once before first `docker-compose up`:
#   bash nginx/generate_dev_cert.sh
set -e

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out    "$CERT_DIR/server.crt" \
  -subj   "/C=US/ST=Dev/L=Dev/O=RMM/CN=localhost"

echo "Dev cert generated at $CERT_DIR/"
echo "For production: replace with a real cert from Let's Encrypt or your CA."

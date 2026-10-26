#!/bin/sh
# Self-signed certificate for local HTTPS. For a trusted local cert use mkcert:
#   mkcert -cert-file docker/nginx/certs/tls.crt -key-file docker/nginx/certs/tls.key localhost
set -e
DIR="$(dirname "$0")/certs"
mkdir -p "$DIR"
[ -f "$DIR/tls.crt" ] && exit 0
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost" -keyout "$DIR/tls.key" -out "$DIR/tls.crt"

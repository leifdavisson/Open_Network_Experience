#!/bin/bash
set -e

mkdir -p server/deploy/certs
cd server/deploy/certs

# 1. Generate Root CA
echo "Generating Root CA..."
openssl genrsa -out rootCA.key 4096
openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 3650 -out rootCA.crt -subj "/C=US/ST=CA/O=Open Network Experience/CN=ONE Root CA"

# 2. Generate Server Certificate
echo "Generating Server Certificate..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=CA/O=Open Network Experience/CN=cmp-server"

cat > extfile.cnf << 'EXT'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
DNS.2 = cmp-server
IP.1 = 127.0.0.1
IP.2 = 10.98.2.125
EXT

openssl x509 -req -in server.csr -CA rootCA.crt -CAkey rootCA.key -CAcreateserial -out server.crt -days 825 -sha256 -extfile extfile.cnf

# 3. Generate Client Certificate for Sensors
echo "Generating Client Certificate..."
openssl genrsa -out sensor-client.key 2048
openssl req -new -key sensor-client.key -out sensor-client.csr -subj "/C=US/ST=CA/O=Open Network Experience/CN=sensor-client"
openssl x509 -req -in sensor-client.csr -CA rootCA.crt -CAkey rootCA.key -CAcreateserial -out sensor-client.crt -days 825 -sha256

echo "Certs generated successfully."

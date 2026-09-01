#!/usr/bin/env python3
"""
Genera certificados SSL autofirmados para uso en red local (LAN).
Windows / PowerShell 7:

  python scripts\\generate_ssl_certs.py

Luego en config.ini:

  [server]
  force_https = true
  ssl_certfile = certs/cert.pem
  ssl_keyfile = certs/key.pem

El navegador mostrará aviso de certificado no confiable: es normal en LAN.
Puedes aceptar la excepción una vez por equipo.
"""
from __future__ import annotations

import datetime
import ipaddress
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "certs"


def main() -> int:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        print("Instala cryptography:\n  pip install cryptography")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    key_path = OUT / "key.pem"
    cert_path = OUT / "cert.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "MX"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fajos Piteados Central"),
            x509.NameAttribute(NameOID.COMMON_NAME, "fajos-local"),
        ]
    )

    alt_names = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    try:
        alt_names.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
    except Exception:
        pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Certificado: {cert_path}")
    print(f"Clave:       {key_path}")
    print(f"Host/IP:     {hostname} / {local_ip}")
    print()
    print("Activa en config.ini:")
    print("  [server]")
    print("  force_https = true")
    print("  ssl_certfile = certs/cert.pem")
    print("  ssl_keyfile = certs/key.pem")
    print()
    print("Reinicia el servidor desde el launcher.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

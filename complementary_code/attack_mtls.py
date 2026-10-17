#!/usr/bin/env python3
"""
Test di robustezza dello Scenario C (mTLS): un attaccante tenta di collegarsi
al router con un certificato NON firmato dalla CA del progetto, in due varianti:

  1. "selfsigned" : certificato autofirmato, nessuna CA dietro.
  2. "fake-ca"     : certificato valido ma firmato da una CA diversa
                     (simula un attaccante che si e' creato una propria CA).

In entrambi i casi il router deve rifiutare la connessione: se cosi' non
fosse, chiunque potrebbe impersonare un nodo legittimo (robot o stazione).

Uso:
    python3 attack_fake_cert.py selfsigned
    python3 attack_fake_cert.py fake-ca
    python3 attack_fake_cert.py selfsigned --endpoint tls/192.168.1.10:7447

Richiede la CA del progetto solo per verificare che il router sia quello
giusto: l'attaccante, nella realta', non ne avrebbe comunque bisogno per
TENTARE la connessione (gli serve solo per generare i propri certificati).
"""
import argparse
import os
import subprocess
import sys
import tempfile

import zenoh

CERTS = "/home/simone/iot_zenoh_project/zenoh_certs"
ENDPOINT = "tls/127.0.0.1:7447"


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_selfsigned(tmp):
    """Certificato autofirmato: nessuna CA lo garantisce."""
    key = os.path.join(tmp, "attacker.key")
    crt = os.path.join(tmp, "attacker.crt")
    run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key, "-out", crt, "-days", "1",
        "-subj", "/CN=AttackerSelfSigned"])
    return crt, key


def make_fake_ca_signed(tmp):
    """Certificato valido, ma firmato da una CA creata al momento dall'attaccante."""
    ca_key = os.path.join(tmp, "fake_ca.key")
    ca_crt = os.path.join(tmp, "fake_ca.crt")
    run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", ca_key, "-out", ca_crt, "-days", "1",
        "-subj", "/CN=AttackerCA",
        "-addext", "basicConstraints=critical,CA:TRUE"])

    key = os.path.join(tmp, "attacker.key")
    csr = os.path.join(tmp, "attacker.csr")
    crt = os.path.join(tmp, "attacker.crt")
    run(["openssl", "req", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key, "-out", csr, "-subj", "/CN=AttackerClient"])

    ext = os.path.join(tmp, "attacker.ext")
    with open(ext, "w") as f:
        f.write("basicConstraints=CA:FALSE\nextendedKeyUsage=clientAuth\n")
    run(["openssl", "x509", "-req", "-in", csr, "-CA", ca_crt, "-CAkey", ca_key,
        "-CAcreateserial", "-out", crt, "-days", "1", "-extfile", ext])
    return crt, key


def try_connect(endpoint, root_ca, client_crt, client_key):
    conf = zenoh.Config()
    conf.insert_json5("mode", '"client"')
    conf.insert_json5("connect/endpoints", f'["{endpoint}"]')
    conf.insert_json5("scouting/multicast/enabled", "false")
    # l'attaccante punta comunque alla CA "ufficiale" per verificare il router:
    # e' il proprio certificato CLIENT a non essere firmato da quella CA.
    conf.insert_json5("transport/link/tls/root_ca_certificate", f'"{root_ca}"')
    conf.insert_json5("transport/link/tls/client_auth", "true")
    conf.insert_json5("transport/link/tls/client_certificate", f'"{client_crt}"')
    conf.insert_json5("transport/link/tls/client_private_key", f'"{client_key}"')
    return zenoh.open(conf)   # solleva un'eccezione se il router rifiuta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variante", choices=["selfsigned", "fake-ca"])
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--ca", default=f"{CERTS}/ca.crt", help="CA per verificare il router")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        if args.variante == "selfsigned":
            crt, key = make_selfsigned(tmp)
            print("Certificato: autofirmato (nessuna CA)", flush=True)
        else:
            crt, key = make_fake_ca_signed(tmp)
            print("Certificato: firmato da una CA creata dall'attaccante", flush=True)

        print(f"Tentativo di connessione mTLS a {args.endpoint} ...", flush=True)
        try:
            session = try_connect(args.endpoint, args.ca, crt, key)
            print("\n❌ ATTACCO RIUSCITO: il router ha accettato un certificato non autorizzato!")
            print("   Verificare la configurazione 'client_auth' e la CA del router.")
            session.close()
            sys.exit(1)
        except Exception as e:
            print(f"\n✅ ATTACCO RESPINTO: connessione rifiutata.\n   Dettaglio: {e}")
            print("   Conferma attesa nel log del router: 'UnknownIssuer' o")
            print("   'invalid peer certificate' (vedi RUST_LOG=zenoh_link_tls=debug).")
            sys.exit(0)


if __name__ == "__main__":
    main()

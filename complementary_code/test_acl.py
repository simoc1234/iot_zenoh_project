#!/usr/bin/env python3
"""
Test di robustezza dello Scenario D (mTLS + ACL): privilege escalation.

Un nodo si connette con un certificato VALIDO la cui policy ACL lo autorizza
SOLO a sottoscrivere "odom" (lettura), non a pubblicarci. Lo script tenta di
scrivere lo stesso un valore anomalo e riconoscibile:
    position.x = 999999.0   (impossibile per un robot reale)

La verifica si fa da fuori, in un altro terminale, durante o dopo l'esecuzione:
    ros2 topic echo /odom
Se tra i messaggi veri compare position.x: 999999.0, la scrittura e' passata
e l'ACL non ha bloccato nulla. Se non compare mai, la scrittura e' stata
scartata dal router.

NOTA SUL FORMATO DEL PAYLOAD
Il payload deve essere un vero messaggio nav_msgs/Odometry in CDR, non una
stringa qualsiasi: un payload non valido verrebbe scartato dal plugin
ros2dds alla decodifica, PRIMA ancora di arrivare all'ACL, rendendo il test
inconcludente (non si saprebbe se a bloccarlo e' stata l'ACL o il formato).
Per questo la serializzazione si fa con rclpy, non a mano.

ESECUZIONE
Serve un ambiente in cui siano importabili sia "rclpy" sia "zenoh" (0.11.0).
Se usi il venv zenoh011_env creato finora, ricrealo con accesso ai pacchetti
di sistema (ti servira' una sola volta):
    deactivate
    rm -rf ~/zenoh011_env
    python3 -m venv --system-site-packages ~/zenoh011_env
    source ~/zenoh011_env/bin/activate
    pip install eclipse-zenoh==0.11.0
    python3 -c "import rclpy, zenoh; print('OK')"
Poi, con il router (ACL su 'odom' in sola lettura) e motor_controller_node
gia' attivi:
    python3 attack_privilege_escalation.py
"""
import sys

import rclpy.serialization
from nav_msgs.msg import Odometry

import zenoh

CERTS = "/home/simone/iot_zenoh_project/zenoh_certs"
ENDPOINT = "tls/127.0.0.1:7447"
KEY = "odom"
X_SPIA = 999999.0   # valore impossibile per un robot reale: riconoscibile a colpo d'occhio


def fake_odometry_bytes():
    msg = Odometry()
    msg.header.frame_id = "odom"
    msg.child_frame_id = "base_link"
    msg.pose.pose.position.x = X_SPIA
    msg.pose.pose.orientation.w = 1.0
    return rclpy.serialization.serialize_message(msg)


def open_session():
    conf = zenoh.Config()
    conf.insert_json5("mode", '"client"')
    conf.insert_json5("connect/endpoints", f'["{ENDPOINT}"]')
    conf.insert_json5("scouting/multicast/enabled", "false")
    conf.insert_json5("transport/link/tls/root_ca_certificate", f'"{CERTS}/ca.crt"')
    conf.insert_json5("transport/link/tls/client_auth", "true")
    conf.insert_json5("transport/link/tls/client_certificate", f'"{CERTS}/client.crt"')
    conf.insert_json5("transport/link/tls/client_private_key", f'"{CERTS}/client.key"')
    return zenoh.open(conf)


def main():
    print("Connessione mTLS...", flush=True)
    try:
        session = open_session()
    except Exception as e:
        print(f"❌ Connessione fallita: {e}")
        sys.exit(1)
    print("✅ Connesso (identita' autorizzata SOLO alla lettura di 'odom')", flush=True)

    print(f"\nPubblico su '{KEY}' un Odometry con position.x = {X_SPIA} "
          "(privilege escalation: da subscriber a publisher)...", flush=True)
    session.put(KEY, fake_odometry_bytes())
    # nota: put() non solleva eccezioni neanche se il router nega l'azione;
    # il controllo e' silenzioso e va verificato dall'esterno.
    print("put() inviato senza errori lato client (il controllo e' silenzioso).", flush=True)

    print("\nControlla ORA, in un altro terminale:", flush=True)
    print("    ros2 topic echo /odom", flush=True)
    print(f"Se non compare mai 'x: {X_SPIA}', l'ACL ha bloccato la scrittura "
          "(🟢 privilege escalation respinta).", flush=True)
    print(f"Se compare, la scrittura e' passata (🔴 privilege escalation riuscita).", flush=True)

    session.close()


if __name__ == "__main__":
    main()

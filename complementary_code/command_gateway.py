"""
Gateway comandi: Node-RED (HTTP locale) -> Zenoh -> router -> ROS2.

Node-RED invia un JSON a http://127.0.0.1:5050/cmd_vel, ad esempio
    {"linear": 0.2, "angular": 0.5}
Il gateway lo converte in un messaggio geometry_msgs/Twist serializzato in CDR
(il formato che si aspetta zenoh-plugin-ros2dds) e lo pubblica sulla key "cmd_vel".

Uso:
    python3 command_gateway.py              # in chiaro (tcp), scenario senza cifratura
    python3 command_gateway.py --tls        # mTLS, per gli scenari con certificati
    python3 command_gateway.py --endpoint tcp/192.168.1.10:7447   # router su un altro host
"""
import argparse
import json
import math
import struct
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import zenoh

CERTS = "/home/simone/iot_zenoh_project/zenoh_certs"
KEY = "cmd_vel"                 # topic ROS2 /cmd_vel
HOST, PORT = "127.0.0.1", 5050  # il gateway HTTP ascolta solo in locale
MAX_LIN, MAX_ANG = 1.0, 2.0     # limiti di sicurezza (m/s, rad/s)


def open_session(endpoint, use_tls):
    conf = zenoh.Config()
    conf.insert_json5("mode", '"client"')
    conf.insert_json5("connect/endpoints", f'["{endpoint}"]')
    conf.insert_json5("scouting/multicast/enabled", "false")
    if use_tls:
        conf.insert_json5("transport/link/tls/root_ca_certificate", f'"{CERTS}/ca.crt"')
        conf.insert_json5("transport/link/tls/client_auth", "true")
        conf.insert_json5("transport/link/tls/client_certificate", f'"{CERTS}/client.crt"')
        conf.insert_json5("transport/link/tls/client_private_key", f'"{CERTS}/client.key"')
    return zenoh.open(conf)


def twist_cdr(linear_x, angular_z):
    """geometry_msgs/Twist in CDR little-endian: header di 4 byte + 6 double."""
    return struct.pack("<4B6d", 0, 1, 0, 0, linear_x, 0.0, 0.0, 0.0, 0.0, angular_z)


def clamp(v, lim):
    return max(-lim, min(lim, v))


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/cmd_vel":
            return self._reply(404, {"ok": False, "error": "usa POST /cmd_vel"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n))
            lin = float(body.get("linear", 0.0))
            ang = float(body.get("angular", 0.0))
            if not (math.isfinite(lin) and math.isfinite(ang)):
                raise ValueError("valori non finiti")
        except Exception as e:
            return self._reply(400, {"ok": False, "error": f"JSON non valido: {e}"})

        lin, ang = clamp(lin, MAX_LIN), clamp(ang, MAX_ANG)
        session.put(KEY, twist_cdr(lin, ang))
        print(f"-> cmd_vel: linear={lin:.2f} m/s, angular={ang:.2f} rad/s", flush=True)
        self._reply(200, {"ok": True, "linear": lin, "angular": ang})

    def log_message(self, *args):   # niente log HTTP di default
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tls", action="store_true", help="usa mTLS (scenari con certificati)")
    ap.add_argument("--endpoint", default=None, help="endpoint del router Zenoh")
    args = ap.parse_args()
    endpoint = args.endpoint or ("tls/127.0.0.1:7447" if args.tls else "tcp/127.0.0.1:7447")

    print(f"Connessione a {endpoint} ({'mTLS' if args.tls else 'in chiaro'})...", flush=True)
    try:
        session = open_session(endpoint, args.tls)
    except Exception as e:
        print(f"❌ Connessione fallita: {e}")
        sys.exit(1)
    print("✅ Connesso al router Zenoh", flush=True)
    print(f"In ascolto su http://{HOST}:{PORT}/cmd_vel", flush=True)
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        session.close()

import zenoh
import time
import sys
 
CERTS = "/home/simone/iot_zenoh_project/zenoh_certs"
DURATA = 8   # secondi di osservazione
 
conf = zenoh.Config()
conf.insert_json5("mode", '"client"')
conf.insert_json5("connect/endpoints", '["tls/127.0.0.1:7447"]')
conf.insert_json5("scouting/multicast/enabled", 'false')
conf.insert_json5("transport/link/tls/root_ca_certificate", f'"{CERTS}/ca.crt"')
conf.insert_json5("transport/link/tls/client_auth", 'true')
conf.insert_json5("transport/link/tls/client_certificate", f'"{CERTS}/client.crt"')
conf.insert_json5("transport/link/tls/client_private_key", f'"{CERTS}/client.key"')
 
print("Avvio connessione mTLS per test ACL...", flush=True)
try:
    session = zenoh.open(conf)
except Exception as e:
    print(f"❌ Connessione fallita: {e}")
    sys.exit(1)
print("✅ Connessione mTLS stabilita!", flush=True)
 
counts = {"odom": 0, "imu/data": 0}
 
def make_listener(name):
    def listener(sample):
        counts[name] += 1
    return listener
 
# nota: la dichiarazione NON solleva errori nemmeno se il router la nega
subs = [session.declare_subscriber(k, make_listener(k)) for k in counts]
 
print(f"⏳ Osservazione per {DURATA} secondi...", flush=True)
time.sleep(DURATA)
 
print(f"\nodom: {counts['odom']} messaggi | imu/data: {counts['imu/data']} messaggi")
if counts["odom"] == 0:
    print("⚠️ Test non valido: nessun dato su 'odom' (sensore fermo o regola ACL su odom errata).")
elif counts["imu/data"] > 0:
    print("🔴 imu/data RICEVUTO: l'ACL non sta bloccando questa risorsa.")
else:
    print("🟢 odom ricevuto, imu/data NO: comportamento compatibile con l'ACL.")
session.close()

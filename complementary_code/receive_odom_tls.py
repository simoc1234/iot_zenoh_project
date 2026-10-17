import zenoh
import time

conf = zenoh.Config()
conf.insert_json5("mode", '"client"')
conf.insert_json5("connect/endpoints", '["tls/127.0.0.1:7447"]')
conf.insert_json5("scouting/multicast/enabled", 'false')
conf.insert_json5("transport/link/tls/root_ca_certificate",
                  '"/home/simone/iot_zenoh_project/zenoh_certs/ca.crt"')

print("Avvio connessione TLS...", flush=True)
session = zenoh.open(conf)          # in client mode fallisce se TLS non va
print("✅ Connessione TLS stabilita!", flush=True)

def listener(sample):
    print(f"🔒 {sample.key_expr}: {len(sample.payload)} bytes", flush=True)

sub = session.declare_subscriber("odom", listener)   

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    session.close()

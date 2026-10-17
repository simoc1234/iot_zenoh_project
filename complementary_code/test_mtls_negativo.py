import zenoh
import sys

conf = zenoh.Config()
conf.insert_json5("mode", '"client"')
conf.insert_json5("connect/endpoints", '["tls/127.0.0.1:7447"]')
conf.insert_json5("scouting/multicast/enabled", 'false')

# Il client conosce la CA del server (quindi tenta una normale connessione TLS)
conf.insert_json5("transport/link/tls/root_ca_certificate", '"/home/simone/iot_zenoh_project/zenoh_certs/ca.crt"')

# =====================================================================
# TEST NEGATIVO: NON INSERIAMO IL CERTIFICATO E LA CHIAVE DEL CLIENT!
# =====================================================================
# conf.insert_json5("transport/link/tls/client_certificate", ...)
# conf.insert_json5("transport/link/tls/client_private_key", ...)
# conf.insert_json5("transport/link/tls/client_auth", 'true')

print("Avvio connessione TLS (SENZA certificato client) per test negativo mTLS...", flush=True)

try:
    # Cerchiamo di aprire la sessione. Se l'mTLS sul router è attivo (client_auth: true), 
    # questa operazione DEVE fallire e lanciare un'eccezione.
    session = zenoh.open(conf)
    
    # Se arriviamo a questa riga, significa che c'è un problema di sicurezza
    print("\n❌ FALLIMENTO DI SICUREZZA: Connessione stabilita! Il router non ha richiesto il certificato client (mTLS disattivo).", flush=True)
    session.close()
    sys.exit(1)

except Exception as e:
    # Questo è il risultato desiderato!
    print(f"\n✅ TEST SUPERATO! Connessione respinta dal router (mTLS funzionante).")
    print(f"Motivo del blocco nativo di Zenoh: {e}\n", flush=True)
    sys.exit(0)

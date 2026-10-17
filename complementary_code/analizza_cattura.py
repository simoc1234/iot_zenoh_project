#!/usr/bin/env python3
"""
Analisi offline di una cattura del traffico Zenoh (.pcapng / .pcap).

La cattura si fa a parte, PRIMA di avviare il client (altrimenti si perde l'handshake):
    sudo tshark -i lo -f "tcp port 7447" -w scenario_B.pcapng
oppure
    sudo tcpdump -i lo -s 0 -w scenario_B.pcap "tcp port 7447"

Poi:
    python3 analizza_cattura.py scenario_B.pcapng --label B
    python3 analizza_cattura.py scenario_A.pcapng --label A --csv risultati.csv

Lo script riassembla i flussi TCP e misura:
  - quanta parte dei byte e' contenuta in record TLS validi;
  - versione TLS e cipher suite (dal ServerHello);
  - entropia dei byte;
  - presenza di firme note (nomi di topic) in chiaro.
"""
import argparse
import csv
import math
import os
import sys
from collections import Counter, defaultdict

try:
    from scapy.utils import PcapReader
    from scapy.layers.inet import IP, TCP
    from scapy.layers.inet6 import IPv6
except ImportError:
    sys.exit("Errore: scapy non installato. Esegui: pip install scapy")

TLS_VERSIONS = {0x0301: "TLS 1.0", 0x0302: "TLS 1.1", 0x0303: "TLS 1.2", 0x0304: "TLS 1.3"}
TLS13_SUITES = {0x1301: "TLS_AES_128_GCM_SHA256",
                0x1302: "TLS_AES_256_GCM_SHA384",
                0x1303: "TLS_CHACHA20_POLY1305_SHA256"}
MAX_RECORD = 16640          # 2^14 + 256, lunghezza massima di un record TLS 1.3
MIN_SIG_LEN = 6             # sotto questa lunghezza i falsi positivi sono probabili
SOGLIA_TLS = 0.99           # quota minima di byte in record TLS validi


# ---------------------------------------------------------------- lettura cattura
def read_streams(path, port):
    """Riassembla i flussi TCP (per direzione) della porta indicata."""
    flows = defaultdict(dict)       # (src, sport, dst, dport) -> {seq: payload}
    n_tcp = 0
    rd = PcapReader(path)
    try:
        for pkt in rd:
            if TCP not in pkt:
                continue
            tcp = pkt[TCP]
            if port not in (tcp.sport, tcp.dport):
                continue
            n_tcp += 1
            ip = pkt[IP] if IP in pkt else (pkt[IPv6] if IPv6 in pkt else None)
            payload = bytes(tcp.payload)
            if ip is None or not payload:
                continue
            flows[(ip.src, tcp.sport, ip.dst, tcp.dport)].setdefault(tcp.seq, payload)
    finally:
        rd.close()

    streams = {}
    for key, segs in flows.items():
        base = min(segs)
        out, nxt = bytearray(), None
        for seq in sorted(segs, key=lambda s: (s - base) & 0xFFFFFFFF):
            data, rel = segs[seq], (seq - base) & 0xFFFFFFFF
            if nxt is not None and rel < nxt:        # ritrasmissione parziale
                data = data[nxt - rel:]
                rel = nxt
                if not data:
                    continue
            out += data
            nxt = rel + len(data)
        streams[key] = bytes(out)
    return n_tcp, streams


# ---------------------------------------------------------------- analisi TLS
def parse_tls_records(buf):
    """Percorre i record TLS di un flusso. Ritorna (record, byte_validi)."""
    pos, valid, records = 0, 0, []
    while pos + 5 <= len(buf):
        ctype = buf[pos]
        ver = int.from_bytes(buf[pos + 1:pos + 3], "big")
        length = int.from_bytes(buf[pos + 3:pos + 5], "big")
        if ctype not in (20, 21, 22, 23) or (ver >> 8) != 3 or (ver & 0xFF) > 4 \
                or length == 0 or length > MAX_RECORD:
            break
        end = min(pos + 5 + length, len(buf))        # ultimo record puo' essere troncato
        records.append((ctype, buf[pos + 5:end]))
        valid += end - pos
        pos = end
    return records, valid


def parse_server_hello(body):
    """Ritorna (versione, cipher suite) da un messaggio handshake ServerHello."""
    try:
        if body[0] != 2:
            return None
        legacy = int.from_bytes(body[4:6], "big")
        sid_len = body[38]
        i = 39 + sid_len
        suite = int.from_bytes(body[i:i + 2], "big")
        i += 3                                        # cipher (2) + compressione (1)
        ext_end = i + 2 + int.from_bytes(body[i:i + 2], "big")
        i += 2
        version = legacy
        while i + 4 <= ext_end:
            etype = int.from_bytes(body[i:i + 2], "big")
            elen = int.from_bytes(body[i + 2:i + 4], "big")
            if etype == 0x002B and elen == 2:         # supported_versions
                version = int.from_bytes(body[i + 4:i + 6], "big")
            i += 4 + elen
        return version, suite
    except (IndexError, ValueError):
        return None


def entropy(data):
    if not data:
        return 0.0
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in Counter(data).values())


# ---------------------------------------------------------------- report
def analyze(path, port, sigs):
    n_tcp, streams = read_streams(path, port)
    total = sum(len(s) for s in streams.values())
    tls_valid, hello = 0, None
    for key, buf in streams.items():
        records, valid = parse_tls_records(buf)
        tls_valid += valid
        if hello is None:
            for ctype, body in records:
                if ctype == 22 and (h := parse_server_hello(body)):
                    hello = h
                    break
    coverage = tls_valid / total if total else 0.0
    hits = {s: sum(buf.count(s.encode()) for buf in streams.values()) for s in sigs}
    all_bytes = b"".join(streams.values())
    return {
        "tcp_packets": n_tcp, "payload_bytes": total, "coverage": coverage,
        "version": TLS_VERSIONS.get(hello[0], hex(hello[0])) if hello else "-",
        "cipher": TLS13_SUITES.get(hello[1], hex(hello[1])) if hello else "-",
        "entropy": entropy(all_bytes), "hits": hits, "n_hits": sum(hits.values()),
    }


def verdict(r):
    if r["payload_bytes"] < 200:
        return "DATI INSUFFICIENTI: cattura troppo corta o porta sbagliata"
    is_tls = r["coverage"] >= SOGLIA_TLS
    if is_tls and r["n_hits"] == 0:
        return f"CIFRATO: traffico {r['version']}, nessuna firma leggibile"
    if is_tls:
        return "ANOMALIA: record TLS validi ma firme trovate (falso positivo? firma corta?)"
    if r["n_hits"] > 0:
        return "IN CHIARO: nessun record TLS e firme leggibili nel payload"
    return "INCONCLUSIVO: non e' TLS ma nessuna firma trovata (cattura partita dopo la connessione?)"


def main():
    ap = argparse.ArgumentParser(description="Analisi di una cattura del traffico Zenoh")
    ap.add_argument("pcap", help="file .pcapng o .pcap")
    ap.add_argument("--port", type=int, default=7447)
    ap.add_argument("--sig", action="append",
                    help="firma da cercare in chiaro (ripetibile). Default: imu/data, cmd_vel, odom")
    ap.add_argument("--label", default="", help="etichetta dello scenario (A, B, C, D)")
    ap.add_argument("--csv", help="aggiunge una riga di risultati a questo file CSV")
    args = ap.parse_args()

    sigs = args.sig or ["imu/data", "cmd_vel", "odom"]
    for s in sigs:
        if len(s) < MIN_SIG_LEN:
            print(f"⚠️  Firma corta ({s!r}, {len(s)} byte): su traffico cifrato puo' comparire per caso.")

    r = analyze(args.pcap, args.port, sigs)
    v = verdict(r)

    print(f"\n=== Analisi di {os.path.basename(args.pcap)}"
          f"{' (scenario ' + args.label + ')' if args.label else ''} ===")
    print(f"Pacchetti TCP sulla porta {args.port} : {r['tcp_packets']}")
    print(f"Byte di payload riassemblati    : {r['payload_bytes']}")
    print(f"Byte in record TLS validi       : {r['coverage'] * 100:.1f}%")
    print(f"Versione / cipher suite         : {r['version']} / {r['cipher']}")
    print(f"Entropia del payload            : {r['entropy']:.3f} bit/byte"
          f"{'  (poco significativa: pochi dati)' if r['payload_bytes'] < 65536 else ''}")
    for s, n in r["hits"].items():
        print(f"Firma {s!r:12} in chiaro      : {n} occorrenze")
    print(f"\nVERDETTO: {v}\n")

    if args.csv:
        new = not os.path.exists(args.csv)
        with open(args.csv, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["scenario", "file", "pacchetti_tcp", "byte_payload", "quota_tls",
                            "versione", "cipher", "entropia", "firme_in_chiaro", "verdetto"])
            w.writerow([args.label, os.path.basename(args.pcap), r["tcp_packets"],
                        r["payload_bytes"], f"{r['coverage']:.4f}", r["version"], r["cipher"],
                        f"{r['entropy']:.3f}", r["n_hits"], v])


if __name__ == "__main__":
    main()

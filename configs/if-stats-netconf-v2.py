#!/usr/bin/env python3
"""
Script NETCONF optimizado para Arista EOS
Monitoreo periódico de estadísticas de interfaz (benchmark)
"""
from ncclient import manager
import time
import json
import sys
from datetime import datetime, timezone
import xml.dom.minidom as MD

# =========================
# Configuración
# =========================
HOST = "172.100.100.7"
PORT = 830
USER = "admin"
PASS = "admin"

INTERFACE_NAME = "Ethernet1"
POLL_INTERVAL = 5
OUTPUT_FILE = "if-stats-netconf-arista.json"


class AristaNETCONFMonitor:
    def __init__(self, interface_name):
        self.interface = interface_name
        self.manager = None
        self.prev_stats = {}
        self.prev_time = None

    # -------------------------
    # Conexión
    # -------------------------
    def connect(self):
        try:
            print(f"Conectando a Arista EOS {HOST}:{PORT}...")
            self.manager = manager.connect(
                host=HOST,
                port=PORT,
                username=USER,
                password=PASS,
                hostkey_verify=False,
                timeout=30,
                allow_agent=False,
                look_for_keys=False,
            )
            print("✅ Conexión NETCONF establecida")
            print(f"   Session ID: {self.manager.session_id}")
            return True
        except Exception as e:
            print(f"❌ Error de conexión NETCONF: {e}")
            return False

    # -------------------------
    # Obtención de estadísticas
    # -------------------------
    def get_interface_stats_openconfig(self):
        try:
            filter_xml = f"""
<filter>
  <interfaces xmlns="http://openconfig.net/yang/interfaces">
    <interface>
      <name>{self.interface}</name>
      <state>
        <counters/>
      </state>
    </interface>
  </interfaces>
</filter>
"""
            reply = self.manager.get(filter=filter_xml)
            return self.parse_openconfig_stats(reply.data_xml)

        except Exception as e:
            print(f"  ❌ Error OpenConfig: {e}")
            return None

    def get_interface_stats_ietf(self):
        try:
            filter_xml = f"""
<filter>
  <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{self.interface}</name>
    </interface>
  </interfaces-state>
</filter>
"""
            reply = self.manager.get(filter=filter_xml)
            return self.parse_ietf_stats(reply.data_xml)

        except Exception as e:
            print(f"  ❌ Error IETF: {e}")
            return None

    def get_interface_stats(self):
        stats = self.get_interface_stats_openconfig()
        if not stats:
            stats = self.get_interface_stats_ietf()

        if not stats:
            stats = {
                "interface-name": self.interface,
                "model": "no-data",
                "in-octets": "0",
                "out-octets": "0",
                "in-packets": "0",
                "out-packets": "0",
            }
        return stats

    # -------------------------
    # Parsing OpenConfig
    # -------------------------
    def parse_openconfig_stats(self, xml_data):
        try:
            dom = MD.parseString(xml_data)
            ns = "http://openconfig.net/yang/interfaces"

            iface = dom.getElementsByTagNameNS(ns, "interface")[0]
            counters = iface.getElementsByTagNameNS(ns, "counters")[0]

            def val(tag):
                elems = counters.getElementsByTagNameNS(ns, tag)
                return elems[0].firstChild.nodeValue if elems and elems[0].firstChild else "0"

            stats = {
                "interface-name": self.interface,
                "model": "openconfig",
                "in-octets": val("in-octets"),
                "out-octets": val("out-octets"),
                "in-unicast-pkts": val("in-unicast-pkts"),
                "out-unicast-pkts": val("out-unicast-pkts"),
                "in-multicast-pkts": val("in-multicast-pkts"),
                "out-multicast-pkts": val("out-multicast-pkts"),
                "in-broadcast-pkts": val("in-broadcast-pkts"),
                "out-broadcast-pkts": val("out-broadcast-pkts"),
                "in-errors": val("in-errors"),
                "out-errors": val("out-errors"),
                "in-discards": val("in-discards"),
                "out-discards": val("out-discards"),
            }

            stats["in-packets"] = str(
                int(stats["in-unicast-pkts"])
                + int(stats["in-multicast-pkts"])
                + int(stats["in-broadcast-pkts"])
            )
            stats["out-packets"] = str(
                int(stats["out-unicast-pkts"])
                + int(stats["out-multicast-pkts"])
                + int(stats["out-broadcast-pkts"])
            )

            return stats

        except Exception as e:
            print(f"  ❌ Error parseando OpenConfig: {e}")
            return None

    # -------------------------
    # Parsing IETF (fallback)
    # -------------------------
    def parse_ietf_stats(self, xml_data):
        try:
            dom = MD.parseString(xml_data)
            ns = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
            iface = dom.getElementsByTagNameNS(ns, "interface")[0]

            def val(tag):
                elems = iface.getElementsByTagNameNS(ns, tag)
                return elems[0].firstChild.nodeValue if elems and elems[0].firstChild else "0"

            stats = {
                "interface-name": self.interface,
                "model": "ietf",
                "in-octets": val("in-octets"),
                "out-octets": val("out-octets"),
                "in-packets": val("in-unicast-pkts"),
                "out-packets": val("out-unicast-pkts"),
            }
            return stats

        except Exception as e:
            print(f"  ❌ Error parseando IETF: {e}")
            return None

    # -------------------------
    # Rate calculation
    # -------------------------
    def calculate_traffic_rate(self, stats):
        now = time.time()
        rate = {"in-bps": "0", "out-bps": "0"}

        if self.prev_time:
            dt = now - self.prev_time
            if dt > 0:
                rate["in-bps"] = str(
                    int((int(stats["in-octets"]) - int(self.prev_stats["in-octets"])) * 8 / dt)
                )
                rate["out-bps"] = str(
                    int((int(stats["out-octets"]) - int(self.prev_stats["out-octets"])) * 8 / dt)
                )

        self.prev_stats = stats.copy()
        self.prev_time = now
        return rate

    # -------------------------
    # Monitor loop
    # -------------------------
    def monitor(self, interval):
        if not self.connect():
            return

        print(f"\n🎯 Interfaz monitoreada: {self.interface}")
        print(f"📊 Polling cada {interval} segundos\n")

        with open(OUTPUT_FILE, "w") as f:
            try:
                while True:
                    ts = time.time()
                    stats = self.get_interface_stats()
                    rate = self.calculate_traffic_rate(stats)

                    output = {
                        "timestamp": int(ts * 1e9),
                        "interface": self.interface,
                        "model": stats["model"],
                        "stats": stats,
                        "rate": rate,
                    }

                    json.dump(output, f)
                    f.write("\n")
                    f.flush()

                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"in={stats['in-octets']} out={stats['out-octets']} "
                        f"in-bps={rate['in-bps']} out-bps={rate['out-bps']}"
                    )

                    time.sleep(interval)

            except KeyboardInterrupt:
                print("\n⏹️  Monitoreo detenido")

        self.manager.close_session()


# =========================
# Main
# =========================
def main():
    print("=" * 60)
    print("NETCONF BENCHMARK MONITOR - Arista EOS")
    print("=" * 60)

    monitor = AristaNETCONFMonitor(INTERFACE_NAME)
    monitor.monitor(POLL_INTERVAL)

    print(f"\n💾 Datos guardados en {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

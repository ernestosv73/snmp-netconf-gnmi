#!/usr/bin/env python3
"""
Script SNMP para monitoreo de interfaces Cisco (benchmark)
Versión final:
- Índice fijo
- Métricas alineadas a gNMI / NETCONF
- Incluye errors, discards y carrier transitions
"""

import time
import json
import sys
from datetime import datetime, timezone
from easysnmp import Session, EasySNMPError

# =========================
# Configuración fija
# =========================
TARGET = '172.100.100.5'
COMMUNITY = 'public'
POLL_INTERVAL = 5  # segundos
OUTPUT_FILE = '/data/if-stats-snmp.json'

INTERFACE_NAME = "Ethernet0/1"
INTERFACE_INDEX = 2  # ifIndex confirmado

# ============================================================
# Clase Monitor SNMP
# ============================================================
class SNMPMonitorEasy:
    def __init__(self, target, community):
        self.target = target
        self.community = community
        self.interface_index = INTERFACE_INDEX
        self.interface_name = INTERFACE_NAME
        self.prev_stats = {}
        self.prev_timestamp = None
        self._init_session()

    def _init_session(self):
        try:
            print(f"Inicializando sesión SNMP con {self.target}...")
            self.session = Session(
                hostname=self.target,
                community=self.community,
                version=2,
                timeout=3,
                retries=2
            )
        except EasySNMPError as e:
            print(f"❌ Error inicializando sesión SNMP: {e}")
            sys.exit(1)

    def get_snmp_value(self, oid_base):
        """Obtiene valor SNMP para el ifIndex fijo"""
        try:
            oid = f"{oid_base}.{self.interface_index}"
            result = self.session.get(oid)
            if result and result.value not in ('NOSUCHINSTANCE', 'NOSUCHOBJECT'):
                return result.value
        except EasySNMPError:
            pass
        return "0"

    # ========================================================
    # Estadísticas de interfaz
    # ========================================================
    def get_interface_stats(self):
        stats = {}

        # ---------- 64 bits (HC) ----------
        hc_in = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.6')   # ifHCInOctets
        hc_out = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.10') # ifHCOutOctets

        if hc_in != "0" or hc_out != "0":
            stats['in-octets'] = hc_in
            stats['out-octets'] = hc_out

            stats['in-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.7')
            stats['in-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.8')
            stats['in-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.9')

            stats['out-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.11')
            stats['out-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.12')
            stats['out-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.13')

        # ---------- Fallback 32 bits ----------
        else:
            stats['in-octets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.10')
            stats['out-octets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.16')

            stats['in-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.11')
            stats['in-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.12')
            stats['in-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.13')

            stats['out-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.17')
            stats['out-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.18')
            stats['out-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.19')

        # ---------- Errors / Discards ----------
        stats['in-discarded-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.13')
        stats['in-error-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.14')
        stats['out-discarded-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.19')
        stats['out-error-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.20')

        # Proxy de carrier transitions
        stats['carrier-transitions'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.9')

        # ---------- Totales ----------
        stats['in-packets'] = str(
            int(stats.get('in-unicast-packets', 0)) +
            int(stats.get('in-multicast-packets', 0)) +
            int(stats.get('in-broadcast-packets', 0))
        )

        stats['out-packets'] = str(
            int(stats.get('out-unicast-packets', 0)) +
            int(stats.get('out-multicast-packets', 0)) +
            int(stats.get('out-broadcast-packets', 0))
        )

        return stats

    # ========================================================
    # Traffic rate
    # ========================================================
    def calculate_traffic_rate(self, stats, now):
        rate = {'in-bps': '0', 'out-bps': '0'}

        if self.prev_stats and self.prev_timestamp:
            dt = now - self.prev_timestamp
            if dt > 0:
                rate['in-bps'] = str(
                    int((int(stats['in-octets']) - int(self.prev_stats['in-octets'])) * 8 / dt)
                )
                rate['out-bps'] = str(
                    int((int(stats['out-octets']) - int(self.prev_stats['out-octets'])) * 8 / dt)
                )

        self.prev_stats = stats.copy()
        self.prev_timestamp = now
        return rate

    # ========================================================
    # Output JSON
    # ========================================================
    def format_output(self, block, data, ts):
        return {
            "source": self.target,
            "subscription-name": "snmp-if-stats",
            "timestamp": int(ts * 1e9),
            "time": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "updates": [{
                "Path": f"IF-MIB:interface[index={self.interface_index}]/{block}",
                "values": {
                    f"IF-MIB:interface/{block}": data
                }
            }]
        }

    # ========================================================
    # Loop principal
    # ========================================================
    def monitor(self):
        print("\n============================================================")
        print("SNMP MONITOR – BENCHMARK TELEMETRÍA")
        print("============================================================")
        print(f"Interfaz: {self.interface_name} (ifIndex {self.interface_index})")
        print("Ctrl+C para detener")
        print("------------------------------------------------------------")

        with open(OUTPUT_FILE, 'w') as f:
            iteration = 1
            while True:
                try:
                    now = time.time()
                    stats = self.get_interface_stats()
                    rate = self.calculate_traffic_rate(stats, now)

                    json.dump(self.format_output("statistics", stats, now), f)
                    f.write("\n")
                    json.dump(self.format_output("traffic-rate", rate, now), f)
                    f.write("\n")
                    f.flush()

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iter {iteration} "
                          f"in={stats['in-octets']} out={stats['out-octets']} "
                          f"in-bps={rate['in-bps']} out-bps={rate['out-bps']}")

                    iteration += 1
                    time.sleep(POLL_INTERVAL)

                except KeyboardInterrupt:
                    print("\n⏹️  Monitoreo detenido")
                    break

# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    monitor = SNMPMonitorEasy(TARGET, COMMUNITY)
    monitor.monitor()

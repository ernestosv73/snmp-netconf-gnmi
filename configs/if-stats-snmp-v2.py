#!/usr/bin/env python3
"""
Script SNMP para monitoreo de interfaces Cisco (benchmark)
Versión final optimizada:
- Sin descubrimiento de interfaces
- Índice fijo (Ethernet0/1 → ifIndex = 2)
- Salida equivalente a gNMI / NETCONF
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
INTERFACE_INDEX = 2  # confirmado experimentalmente

class SNMPMonitorEasy:
    def __init__(self, target, community):
        self.target = target
        self.community = community
        self.interface_index = INTERFACE_INDEX
        self.interface_name = INTERFACE_NAME
        self.prev_stats = {}
        self.prev_timestamp = None
        self.initialize_session()
    
    def initialize_session(self):
        """Inicializa la sesión SNMP"""
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
            print(f"Error inicializando sesión SNMP: {e}")
            sys.exit(1)
    
    def get_snmp_value(self, oid_base):
        """Obtiene un valor SNMP para la interfaz fija"""
        try:
            oid = f"{oid_base}.{self.interface_index}"
            result = self.session.get(oid)
            if result and hasattr(result, 'value') and result.value != 'NOSUCHINSTANCE':
                return result.value
        except EasySNMPError:
            pass
        except Exception as e:
            print(f"Error obteniendo {oid_base}: {e}")
        return "0"
    
    def get_interface_stats(self):
        """Obtiene estadísticas de la interfaz"""
        stats = {}

        # Contadores de 64 bits (preferidos)
        hc_in_octets = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.6')
        hc_out_octets = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.10')

        if hc_in_octets != "0" or hc_out_octets != "0":
            stats['in-octets'] = hc_in_octets
            stats['out-octets'] = hc_out_octets
            stats['in-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.7')
            stats['in-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.8')
            stats['in-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.9')
            stats['out-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.11')
            stats['out-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.12')
            stats['out-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.13')
        else:
            # Fallback 32 bits
            stats['in-octets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.10')
            stats['out-octets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.16')
            stats['in-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.11')
            stats['in-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.12')
            stats['in-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.13')
            stats['out-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.17')
            stats['out-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.18')
            stats['out-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.19')

        # Totales
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
    
    def calculate_traffic_rate(self, current_stats, current_time):
        """Calcula tasa de tráfico"""
        rate = {'in-bps': '0', 'out-bps': '0'}

        if self.prev_stats and self.prev_timestamp:
            delta_t = current_time - self.prev_timestamp
            if delta_t > 0:
                in_diff = int(current_stats['in-octets']) - int(self.prev_stats['in-octets'])
                out_diff = int(current_stats['out-octets']) - int(self.prev_stats['out-octets'])
                rate['in-bps'] = str(int((in_diff * 8) / delta_t))
                rate['out-bps'] = str(int((out_diff * 8) / delta_t))

        self.prev_stats = current_stats.copy()
        self.prev_timestamp = current_time
        return rate
    
    def format_output(self, stats_type, data, timestamp):
        """Formato equivalente a gNMI"""
        return {
            "source": self.target,
            "subscription-name": "snmp-if-stats",
            "timestamp": int(timestamp * 1e9),
            "time": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
            "updates": [{
                "Path": f"IF-MIB:interface[index={self.interface_index}]/{stats_type}",
                "values": {f"IF-MIB:interface/{stats_type}": data}
            }]
        }
    
    def monitor(self, interval):
        print("\n============================================================")
        print("MONITOR SNMP - ESTUDIO COMPARATIVO CON GNMI")
        print("============================================================")
        print(f"Interfaz fija: {self.interface_name} (ifIndex {self.interface_index})")
        print("Presiona Ctrl+C para detener")
        print("------------------------------------------------------------")

        with open(OUTPUT_FILE, 'w') as f:
            iteration = 0
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

                    iteration += 1
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteración {iteration}")
                    print(f"  Octets: in={stats['in-octets']}, out={stats['out-octets']}")
                    print(f"  Rate: in={rate['in-bps']} bps, out={rate['out-bps']} bps")

                    time.sleep(interval)

                except KeyboardInterrupt:
                    print("\nMonitoreo detenido")
                    break

if __name__ == "__main__":
    monitor = SNMPMonitorEasy(TARGET, COMMUNITY)
    monitor.monitor(POLL_INTERVAL)

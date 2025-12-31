#!/usr/bin/env python3
"""
Script SNMP simplificado - Especificar índice manualmente
"""

import time
import json
from datetime import datetime
from easysnmp import Session

# Configuración
TARGET = '172.100.100.5'
COMMUNITY = 'public'
INTERFACE_INDEX = 2  # Ethernet 0/1
POLL_INTERVAL = 5

# Crear sesión
session = Session(
    hostname=TARGET,
    community=COMMUNITY,
    version=2,
    timeout=2
)

def get_value(oid):
    """Obtiene valor SNMP"""
    try:
        result = session.get(f"{oid}.{INTERFACE_INDEX}")
        return result.value if result.value != 'NOSUCHINSTANCE' else "0"
    except:
        return "0"

def main():
    prev_stats = {}
    prev_time = None
    
    print(f"Monitoreando interfaz {INTERFACE_INDEX} cada {POLL_INTERVAL}s")
    print("Ctrl+C para detener\n")
    
    while True:
        try:
            current_time = time.time()
            
            # Obtener estadísticas
            stats = {
                'in-octets': get_value('.1.3.6.1.2.1.31.1.1.1.6'),
                'out-octets': get_value('.1.3.6.1.2.1.31.1.1.1.10'),
                'in-packets': get_value('.1.3.6.1.2.1.31.1.1.1.7'),
                'out-packets': get_value('.1.3.6.1.2.1.31.1.1.1.11'),
            }
            
            # Calcular tasa
            traffic = {'in-bps': '0', 'out-bps': '0'}
            if prev_stats and prev_time:
                time_diff = current_time - prev_time
                if time_diff > 0:
                    in_bps = (int(stats['in-octets']) - int(prev_stats['in-octets'])) * 8 / time_diff
                    out_bps = (int(stats['out-octets']) - int(prev_stats['out-octets'])) * 8 / time_diff
                    traffic = {'in-bps': str(int(in_bps)), 'out-bps': str(int(out_bps))}
            
            # Mostrar
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"in: {stats['in-octets']} octets ({traffic['in-bps']} bps) | "
                  f"out: {stats['out-octets']} octets ({traffic['out-bps']} bps)")
            
            # Guardar para siguiente
            prev_stats = stats.copy()
            prev_time = current_time
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nDetenido")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()

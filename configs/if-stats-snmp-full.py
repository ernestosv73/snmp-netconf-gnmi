#!/usr/bin/env python3
"""
Script SNMP para monitoreo de interfaces Cisco usando easysnmp
Versión corregida - Equivalente al script gNMI
"""

import time
import json
import sys
from datetime import datetime
from easysnmp import Session, EasySNMPError

# Configuración SNMP
TARGET = '172.100.100.5'
COMMUNITY = 'public'
POLL_INTERVAL = 5  # segundos
OUTPUT_FILE = 'if-stats-snmp.json'

class SNMPMonitorEasy:
    def __init__(self, target, community):
        self.target = target
        self.community = community
        self.session = None
        self.interface_index = None
        self.interface_name = "Ethernet0/1"
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
            
            # Descubrir índice de interfaz
            self.discover_and_set_interface()
            
        except EasySNMPError as e:
            print(f"Error inicializando sesión SNMP: {e}")
            sys.exit(1)
    
    def discover_and_set_interface(self):
        """Descubre y configura la interfaz Ethernet0/1"""
        print(f"\nBuscando interfaz {self.interface_name}...")
        
        # Método 1: Buscar por ifDescr
        try:
            # ifDescr da descripciones como "Ethernet0/1"
            if_descr_oids = self.session.walk('.1.3.6.1.2.1.2.2.1.2')
            
            for item in if_descr_oids:
                if self.interface_name.lower() in item.value.lower():
                    # Extraer índice del OID: .1.3.6.1.2.1.2.2.1.2.X
                    oid_parts = item.oid.split('.')
                    if len(oid_parts) > 0:
                        index = oid_parts[-1]
                        print(f"  Encontrada por descripción: {item.value} (índice: {index})")
                        self.interface_index = int(index)
                        return
            
            print(f"  No se encontró {self.interface_name} por descripción")
            
        except Exception as e:
            print(f"  Error buscando por descripción: {e}")
        
        # Método 2: Buscar por ifName (puede ser diferente en Cisco)
        try:
            if_name_oids = self.session.walk('.1.3.6.1.2.1.31.1.1.1.1')
            
            for item in if_name_oids:
                if self.interface_name.lower() in item.value.lower():
                    oid_parts = item.oid.split('.')
                    if len(oid_parts) > 0:
                        index = oid_parts[-1]
                        print(f"  Encontrada por nombre: {item.value} (índice: {index})")
                        self.interface_index = int(index)
                        return
            
            print(f"  No se encontró {self.interface_name} por nombre")
            
        except Exception as e:
            print(f"  Error buscando por nombre: {e}")
        
        # Método 3: Mostrar todas las interfaces y pedir índice manual
        print("\nListando todas las interfaces disponibles:")
        try:
            # Obtener ifIndex, ifDescr, ifName
            if_indices = self.session.walk('.1.3.6.1.2.1.2.2.1.1')
            if_descriptions = self.session.walk('.1.3.6.1.2.1.2.2.1.2')
            if_names = self.session.walk('.1.3.6.1.2.1.31.1.1.1.1')
            
            print(f"{'Índice':<8} {'Descripción':<20} {'Nombre':<20}")
            print("-" * 50)
            
            # Asumimos que todas las walk devuelven en mismo orden
            for idx_item, descr_item, name_item in zip(if_indices, if_descriptions, if_names):
                idx = idx_item.value
                descr = descr_item.value[:18] + "..." if len(descr_item.value) > 18 else descr_item.value
                name = name_item.value[:18] + "..." if len(name_item.value) > 18 else name_item.value
                print(f"{idx:<8} {descr:<20} {name:<20}")
            
            # Preguntar al usuario
            print(f"\nNo se pudo encontrar automáticamente {self.interface_name}")
            user_input = input("Ingresa el índice de la interfaz a monitorear (presiona Enter para usar 1): ").strip()
            
            if user_input and user_input.isdigit():
                self.interface_index = int(user_input)
            else:
                self.interface_index = 1
                print(f"Usando índice por defecto: {self.interface_index}")
                
        except Exception as e:
            print(f"  Error listando interfaces: {e}")
            self.interface_index = 1
            print(f"Usando índice por defecto: {self.interface_index}")
    
    def get_snmp_value(self, oid_base):
        """Obtiene un valor SNMP para la interfaz actual"""
        try:
            oid = f"{oid_base}.{self.interface_index}"
            result = self.session.get(oid)
            if result and hasattr(result, 'value') and result.value != 'NOSUCHINSTANCE':
                return result.value
        except EasySNMPError as e:
            # Silenciar errores de OIDs no existentes
            pass
        except Exception as e:
            print(f"  Error obteniendo {oid_base}: {e}")
        
        return "0"
    
    def get_interface_stats(self):
        """Obtiene estadísticas de la interfaz"""
        stats = {}
        
        # Contadores de octetos (64-bit primero, luego 32-bit)
        hc_in_octets = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.6')  # ifHCInOctets
        hc_out_octets = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.10')  # ifHCOutOctets
        
        if hc_in_octets != "0" or hc_out_octets != "0":
            # Usar contadores de alta capacidad
            stats['in-octets'] = hc_in_octets
            stats['out-octets'] = hc_out_octets
            stats['in-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.7')
            stats['in-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.8')
            stats['in-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.9')
            stats['out-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.11')
            stats['out-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.12')
            stats['out-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.13')
        else:
            # Fallback a contadores de 32-bit
            stats['in-octets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.10')
            stats['out-octets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.16')
            stats['in-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.11')
            stats['in-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.12')
            stats['in-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.13')
            stats['out-unicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.17')
            stats['out-multicast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.18')
            stats['out-broadcast-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.19')
        
        # Otras métricas
        stats['in-discarded-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.13')  # ifInDiscards
        stats['in-error-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.14')
        stats['out-discarded-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.19')  # ifOutDiscards
        stats['out-error-packets'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.20')
        stats['carrier-transitions'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.32')
        
        # Calcular paquetes totales
        try:
            in_total = (int(stats.get('in-unicast-packets', 0)) + 
                       int(stats.get('in-multicast-packets', 0)) + 
                       int(stats.get('in-broadcast-packets', 0)))
            stats['in-packets'] = str(in_total)
            
            out_total = (int(stats.get('out-unicast-packets', 0)) + 
                        int(stats.get('out-multicast-packets', 0)) + 
                        int(stats.get('out-broadcast-packets', 0)))
            stats['out-packets'] = str(out_total)
        except:
            stats['in-packets'] = '0'
            stats['out-packets'] = '0'
        
        # Obtener información de la interfaz
        stats['interface-name'] = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.1')
        stats['interface-description'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.2')
        stats['operational-status'] = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.8')
        
        return stats
    
    def calculate_traffic_rate(self, current_stats, current_time):
        """Calcula tasa de tráfico"""
        traffic_rate = {'in-bps': '0', 'out-bps': '0'}
        
        if self.prev_stats and self.prev_timestamp:
            time_diff = current_time - self.prev_timestamp
            if time_diff > 0:
                try:
                    # Calcular diferencia
                    in_diff = int(current_stats.get('in-octets', 0)) - int(self.prev_stats.get('in-octets', 0))
                    out_diff = int(current_stats.get('out-octets', 0)) - int(self.prev_stats.get('out-octets', 0))
                    
                    # Convertir a bits por segundo
                    in_bps = (in_diff * 8) / time_diff
                    out_bps = (out_diff * 8) / time_diff
                    
                    traffic_rate['in-bps'] = str(int(in_bps))
                    traffic_rate['out-bps'] = str(int(out_bps))
                    
                except Exception as e:
                    pass
        
        # Guardar para próxima iteración
        self.prev_stats = current_stats.copy()
        self.prev_timestamp = current_time
        
        return traffic_rate
    
    def format_output(self, stats_type, data, timestamp):
        """Formatea salida similar a gNMI"""
        output = {
            "source": self.target,
            "subscription-name": "snmp-if-stats",
            "timestamp": int(timestamp * 1000000000),
            "time": datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "updates": [
                {
                    "Path": f"IF-MIB:interface[index={self.interface_index}]/{stats_type}",
                    "values": {
                        f"IF-MIB:interface/{stats_type}": data
                    }
                }
            ]
        }
        return output
    
    def test_connection(self):
        """Prueba la conexión SNMP"""
        print("\nProbando conexión SNMP...")
        try:
            # sysDescr
            sys_descr = self.session.get('.1.3.6.1.2.1.1.1.0')
            print(f"  Sistema: {sys_descr.value[:80]}...")
            
            # sysUpTime
            sys_uptime = self.session.get('.1.3.6.1.2.1.1.3.0')
            print(f"  Uptime: {sys_uptime.value}")
            
            # Número de interfaces
            num_if = self.session.get('.1.3.6.1.2.1.2.1.0')
            print(f"  Interfaces: {num_if.value}")
            
            # Obtener info de la interfaz seleccionada
            if_name = self.get_snmp_value('.1.3.6.1.2.1.31.1.1.1.1')
            if_descr = self.get_snmp_value('.1.3.6.1.2.1.2.2.1.2')
            print(f"  Interfaz seleccionada: {if_name} ({if_descr})")
            
            return True
            
        except Exception as e:
            print(f"  Error de conexión: {e}")
            return False
    
    def monitor(self, interval=5, duration=None):
        """Monitorea la interfaz"""
        if not self.test_connection():
            print("\nNo se pudo establecer conexión SNMP.")
            return
        
        print(f"\nIniciando monitoreo cada {interval} segundos...")
        print(f"Interfaz: índice {self.interface_index}")
        print("Presiona Ctrl+C para detener")
        print("-" * 60)
        
        start_time = time.time()
        iteration = 0
        
        with open(OUTPUT_FILE, 'w') as f:
            while True:
                try:
                    current_time = time.time()
                    
                    # Obtener estadísticas
                    stats = self.get_interface_stats()
                    
                    if stats:
                        # Guardar estadísticas
                        stats_output = self.format_output("statistics", stats, current_time)
                        json.dump(stats_output, f)
                        f.write('\n')
                        
                        # Calcular y guardar tasa
                        traffic_rate = self.calculate_traffic_rate(stats, current_time)
                        traffic_output = self.format_output("traffic-rate", traffic_rate, current_time)
                        json.dump(traffic_output, f)
                        f.write('\n')
                        
                        # Mostrar en consola
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteración {iteration + 1}")
                        print(f"  Octets: in={stats.get('in-octets', '0')}, out={stats.get('out-octets', '0')}")
                        print(f"  Packets: in={stats.get('in-packets', '0')}, out={stats.get('out-packets', '0')}")
                        print(f"  Rate: in={traffic_rate['in-bps']} bps, out={traffic_rate['out-bps']} bps")
                    
                    f.flush()
                    iteration += 1
                    
                    # Verificar duración
                    if duration and (current_time - start_time) >= duration:
                        print(f"\nMonitoreo completado ({duration} segundos)")
                        break
                    
                    # Esperar
                    elapsed = time.time() - current_time
                    sleep_time = interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                except KeyboardInterrupt:
                    print("\n\nMonitoreo detenido")
                    break
                except Exception as e:
                    print(f"\nError: {e}")
                    time.sleep(interval)

def install_dependencies():
    """Instala easysnmp si no está disponible"""
    import subprocess
    
    print("Instalando easysnmp...")
    try:
        subprocess.check_call(['pip', 'install', 'easysnmp'])
        print("Instalación completada")
        return True
    except:
        print("Error instalando. Ejecuta manualmente: pip install easysnmp")
        return False

if __name__ == "__main__":
    # Verificar dependencias
    try:
        from easysnmp import Session
    except ImportError:
        if not install_dependencies():
            sys.exit(1)
        from easysnmp import Session
    
    # Crear monitor
    monitor = SNMPMonitorEasy(TARGET, COMMUNITY)
    
    # Monitorear (para prueba rápida: duration=30)
    print("\n" + "="*60)
    print("MONITOR SNMP - ESTUDIO COMPARATIVO CON GNMI")
    print("="*60)
    
    # Para monitoreo continuo:
    monitor.monitor(interval=POLL_INTERVAL)
    
    # Para prueba de 30 segundos:
    # monitor.monitor(interval=POLL_INTERVAL, duration=30)
    
    print(f"\nDatos guardados en: {OUTPUT_FILE}")
    print("Listo para comparación con datos gNMI")

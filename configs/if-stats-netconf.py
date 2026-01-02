#!/usr/bin/env python3
"""
Script NETCONF para Arista EOS - Monitoreo de estadísticas de interfaz
Equivalente funcional a scripts gNMI y SNMP para estudio comparativo
"""
from ncclient import manager
import time
import json
import sys
from datetime import datetime, timezone
import xml.dom.minidom as MD

# Configuración Arista EOS
HOST = "172.100.100.7"  # Cambia esto a tu IP de Arista
PORT = 830
USER = "admin"
PASS = "admin"
INTERFACE_NAME = "Ethernet1"  # Interfaz a monitorear en Arista
POLL_INTERVAL = 5
OUTPUT_FILE = "if-stats-netconf-arista.json"

class AristaNETCONFMonitor:
    def __init__(self, interface_name):
        self.interface = interface_name
        self.manager = None
        self.prev_stats = {}
        self.prev_time = None
        
    def connect(self):
        """Establece conexión NETCONF con Arista EOS"""
        try:
            print(f"Conectando a Arista EOS {HOST}:{PORT}...")
            self.manager = manager.connect(
                host=HOST,
                port=PORT,
                username=USER,
                password=PASS,
                hostkey_verify=False,
                timeout=30,
                device_params={'name': 'default'},
                allow_agent=False,
                look_for_keys=False
            )
            
            print(f"✅ Conexión exitosa")
            print(f"   Session ID: {self.manager.session_id}")
            print(f"   Timeout: {self.manager.timeout}")
            
            # Verificar capacidades RFC 6022
            if "urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring" in self.manager.server_capabilities:
                print(f"   ✅ Servidor cumple con RFC 6022")
            else:
                print(f"   ⚠️  Servidor no cumple con RFC 6022")
            
            return True
            
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False
    
    def get_interface_stats_openconfig(self):
        """Obtiene estadísticas usando OpenConfig (recomendado para Arista)"""
        try:
            # Filtro OpenConfig para estadísticas de interfaz
            filter_xml = f"""<?xml version="1.0"?>
<filter>
    <interfaces xmlns="http://openconfig.net/yang/interfaces">
        <interface>
            <name>{self.interface}</name>
            <state>
                <counters/>
            </state>
        </interface>
    </interfaces>
</filter>"""
            
            # Usar get para datos operacionales
            reply = self.manager.get(filter=filter_xml)
            
            # Guardar respuesta para debug
            with open(f'arista_{self.interface}_openconfig.xml', 'w', encoding='utf-8') as f:
                f.write(reply.data_xml)
            
            return self.parse_openconfig_stats(reply.data_xml)
            
        except Exception as e:
            print(f"  ❌ Error OpenConfig: {e}")
            return None
    
    def get_interface_stats_ietf(self):
        """Obtiene estadísticas usando IETF interfaces (alternativa)"""
        try:
            filter_xml = f"""<?xml version="1.0"?>
<filter>
    <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
            <name>{self.interface}</name>
        </interface>
    </interfaces-state>
</filter>"""
            
            reply = self.manager.get(filter=filter_xml)
            
            with open(f'arista_{self.interface}_ietf.xml', 'w', encoding='utf-8') as f:
                f.write(reply.data_xml)
            
            return self.parse_ietf_stats(reply.data_xml)
            
        except Exception as e:
            print(f"  ❌ Error IETF: {e}")
            return None
    
    def parse_openconfig_stats(self, xml_data):
        """Parsea estadísticas OpenConfig de Arista"""
        try:
            if '<data/>' in xml_data:
                print(f"  ⚠️  Respuesta vacía para {self.interface}")
                return None
            
            dom = MD.parseString(xml_data)
            ns = "http://openconfig.net/yang/interfaces"
            
            interface = dom.getElementsByTagNameNS(ns, "interface")
            if not interface:
                return None
            
            iface = interface[0]
            
            # Extraer nombre
            name_elem = iface.getElementsByTagNameNS(ns, "name")
            if not name_elem or not name_elem[0].firstChild:
                return None
            
            # Buscar contadores
            counters = iface.getElementsByTagNameNS(ns, "counters")
            if not counters:
                return None
            
            counter = counters[0]
            
            # Extraer estadísticas
            stats = {
                'interface-name': name_elem[0].firstChild.nodeValue,
                'model': 'openconfig',
                'in-octets': self.get_element_text(counter, ns, "in-octets") or "0",
                'out-octets': self.get_element_text(counter, ns, "out-octets") or "0",
                'in-unicast-pkts': self.get_element_text(counter, ns, "in-unicast-pkts") or "0",
                'out-unicast-pkts': self.get_element_text(counter, ns, "out-unicast-pkts") or "0",
                'in-broadcast-pkts': self.get_element_text(counter, ns, "in-broadcast-pkts") or "0",
                'out-broadcast-pkts': self.get_element_text(counter, ns, "out-broadcast-pkts") or "0",
                'in-multicast-pkts': self.get_element_text(counter, ns, "in-multicast-pkts") or "0",
                'out-multicast-pkts': self.get_element_text(counter, ns, "out-multicast-pkts") or "0",
                'in-discards': self.get_element_text(counter, ns, "in-discards") or "0",
                'out-discards': self.get_element_text(counter, ns, "out-discards") or "0",
                'in-errors': self.get_element_text(counter, ns, "in-errors") or "0",
                'out-errors': self.get_element_text(counter, ns, "out-errors") or "0",
            }
            
            # Calcular paquetes totales
            try:
                in_total = (int(stats['in-unicast-pkts']) + 
                           int(stats['in-multicast-pkts']) + 
                           int(stats['in-broadcast-pkts']))
                out_total = (int(stats['out-unicast-pkts']) + 
                            int(stats['out-multicast-pkts']) + 
                            int(stats['out-broadcast-pkts']))
                
                stats['in-packets'] = str(in_total)
                stats['out-packets'] = str(out_total)
            except:
                stats['in-packets'] = "0"
                stats['out-packets'] = "0"
            
            print(f"    ✅ OpenConfig: in-octets={stats['in-octets']}, out-octets={stats['out-octets']}")
            return stats
            
        except Exception as e:
            print(f"  ❌ Error parseando OpenConfig: {e}")
            return None
    
    def parse_ietf_stats(self, xml_data):
        """Parsea estadísticas IETF de Arista"""
        try:
            dom = MD.parseString(xml_data)
            ns = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
            
            interface = dom.getElementsByTagNameNS(ns, "interface")
            if not interface:
                return None
            
            iface = interface[0]
            
            stats = {
                'interface-name': self.get_element_text(iface, ns, "name") or self.interface,
                'model': 'ietf',
                'oper-status': self.get_element_text(iface, ns, "oper-status") or "unknown",
                'in-octets': self.get_element_text(iface, ns, "in-octets") or "0",
                'out-octets': self.get_element_text(iface, ns, "out-octets") or "0",
                'in-unicast-pkts': self.get_element_text(iface, ns, "in-unicast-pkts") or "0",
                'out-unicast-pkts': self.get_element_text(iface, ns, "out-unicast-pkts") or "0",
                'in-multicast-pkts': self.get_element_text(iface, ns, "in-multicast-pkts") or "0",
                'out-multicast-pkts': self.get_element_text(iface, ns, "out-multicast-pkts") or "0",
                'in-broadcast-pkts': self.get_element_text(iface, ns, "in-broadcast-pkts") or "0",
                'out-broadcast-pkts': self.get_element_text(iface, ns, "out-broadcast-pkts") or "0",
                'in-discards': self.get_element_text(iface, ns, "in-discards") or "0",
                'out-discards': self.get_element_text(iface, ns, "out-discards") or "0",
                'in-errors': self.get_element_text(iface, ns, "in-errors") or "0",
                'out-errors': self.get_element_text(iface, ns, "out-errors") or "0",
            }
            
            # Calcular paquetes totales
            try:
                in_total = (int(stats['in-unicast-pkts']) + 
                           int(stats['in-multicast-pkts']) + 
                           int(stats['in-broadcast-pkts']))
                out_total = (int(stats['out-unicast-pkts']) + 
                            int(stats['out-multicast-pkts']) + 
                            int(stats['out-broadcast-pkts']))
                
                stats['in-packets'] = str(in_total)
                stats['out-packets'] = str(out_total)
            except:
                stats['in-packets'] = "0"
                stats['out-packets'] = "0"
            
            print(f"    ✅ IETF: in-octets={stats['in-octets']}, out-octets={stats['out-octets']}")
            return stats
            
        except Exception as e:
            print(f"  ❌ Error parseando IETF: {e}")
            return None
    
    def get_element_text(self, parent, namespace, tag_name):
        """Obtiene texto de elemento XML"""
        try:
            elements = parent.getElementsByTagNameNS(namespace, tag_name)
            if elements and elements[0].firstChild:
                return elements[0].firstChild.nodeValue
        except:
            pass
        return ""
    
    def get_interface_stats(self):
        """Obtiene estadísticas usando el mejor método disponible"""
        # 1. Intentar OpenConfig primero (Arista lo soporta bien)
        stats = self.get_interface_stats_openconfig()
        
        # 2. Si falla, intentar IETF
        if not stats or int(stats.get('in-octets', 0)) == 0:
            stats = self.get_interface_stats_ietf()
        
        # 3. Si todo falla, crear stats vacías
        if not stats:
            stats = {
                'interface-name': self.interface,
                'model': 'no-data',
                'in-octets': '0',
                'out-octets': '0',
                'in-packets': '0',
                'out-packets': '0'
            }
        
        return stats
    
    def calculate_traffic_rate(self, stats):
        """Calcula tasa de tráfico basada en diferencia temporal"""
        current_time = time.time()
        traffic_rate = {'in-bps': '0', 'out-bps': '0'}
        
        if self.prev_stats and self.prev_time:
            time_diff = current_time - self.prev_time
            
            if time_diff > 0:
                try:
                    in_now = int(stats.get('in-octets', 0))
                    out_now = int(stats.get('out-octets', 0))
                    in_prev = int(self.prev_stats.get('in-octets', 0))
                    out_prev = int(self.prev_stats.get('out-octets', 0))
                    
                    in_bps = ((in_now - in_prev) * 8) / time_diff
                    out_bps = ((out_now - out_prev) * 8) / time_diff
                    
                    traffic_rate['in-bps'] = str(int(in_bps))
                    traffic_rate['out-bps'] = str(int(out_bps))
                    
                except (ValueError, TypeError):
                    pass
        
        # Guardar para próxima iteración
        self.prev_stats = stats.copy()
        self.prev_time = current_time
        
        return traffic_rate
    
    def format_output(self, stats, traffic_rate, timestamp):
        """Formatea salida JSON compatible con gNMI/SNMP"""
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        # Datos de estadísticas
        statistics_data = {
            "in-octets": stats.get('in-octets', '0'),
            "out-octets": stats.get('out-octets', '0'),
            "in-packets": stats.get('in-packets', '0'),
            "out-packets": stats.get('out-packets', '0'),
            "in-unicast-packets": stats.get('in-unicast-pkts', '0'),
            "out-unicast-packets": stats.get('out-unicast-pkts', '0'),
            "in-multicast-packets": stats.get('in-multicast-pkts', '0'),
            "out-multicast-packets": stats.get('out-multicast-pkts', '0'),
            "in-broadcast-packets": stats.get('in-broadcast-pkts', '0'),
            "out-broadcast-packets": stats.get('out-broadcast-pkts', '0'),
            "in-error-packets": stats.get('in-errors', '0'),
            "out-error-packets": stats.get('out-errors', '0'),
            "in-discarded-packets": stats.get('in-discards', '0'),
            "out-discarded-packets": stats.get('out-discards', '0'),
            "oper-status": stats.get('oper-status', 'unknown'),
            "model": stats.get('model', 'unknown')
        }
        
        # Datos de tasa de tráfico
        traffic_rate_data = {
            "in-bps": traffic_rate['in-bps'],
            "out-bps": traffic_rate['out-bps']
        }
        
        output = {
            "source": f"{HOST}:{PORT}",
            "subscription-name": "netconf-if-stats",
            "timestamp": int(timestamp * 1000000000),
            "time": dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "updates": [
                {
                    "Path": f"openconfig-interfaces:interface[name={self.interface}]/statistics",
                    "values": {
                        f"openconfig-interfaces:interface/statistics": statistics_data
                    }
                },
                {
                    "Path": f"openconfig-interfaces:interface[name={self.interface}]/traffic-rate",
                    "values": {
                        f"openconfig-interfaces:interface/traffic-rate": traffic_rate_data
                    }
                }
            ]
        }
        
        return output
    
    def list_capabilities(self):
        """Lista capacidades del servidor"""
        print("\n📋 Capacidades del servidor Arista:")
        print("-" * 60)
        
        cap_count = 0
        openconfig_caps = []
        
        for cap in sorted(self.manager.server_capabilities):
            cap_count += 1
            if 'openconfig' in cap.lower():
                openconfig_caps.append(cap)
        
        print(f"Total capacidades: {cap_count}")
        
        if openconfig_caps:
            print(f"\nCapacidades OpenConfig encontradas:")
            for cap in openconfig_caps[:10]:  # Mostrar primeras 10
                print(f"  • {cap}")
        
        # Buscar específicamente interfaces
        interface_caps = [c for c in self.manager.server_capabilities 
                         if 'interface' in c.lower()]
        
        if interface_caps:
            print(f"\nCapacidades de interfaces:")
            for cap in interface_caps:
                print(f"  • {cap}")
        
        print("-" * 60)
    
    def discover_interfaces(self):
        """Descubre interfaces disponibles"""
        print(f"\n🔍 Descubriendo interfaces en Arista...")
        
        try:
            # Obtener todas las interfaces
            filter_xml = """<?xml version="1.0"?>
<filter>
    <interfaces xmlns="http://openconfig.net/yang/interfaces">
        <interface>
            <name/>
            <state>
                <oper-status/>
            </state>
        </interface>
    </interfaces>
</filter>"""
            
            reply = self.manager.get(filter=filter_xml)
            
            # Parsear respuesta
            dom = MD.parseString(reply.data_xml)
            ns = "http://openconfig.net/yang/interfaces"
            
            interfaces = dom.getElementsByTagNameNS(ns, "interface")
            
            print(f"\n📋 Interfaces encontradas: {len(interfaces)}")
            print("=" * 50)
            
            interface_list = []
            for iface in interfaces:
                name_elem = iface.getElementsByTagNameNS(ns, "name")
                state_elem = iface.getElementsByTagNameNS(ns, "state")
                
                if name_elem and name_elem[0].firstChild:
                    if_name = name_elem[0].firstChild.nodeValue
                    if_state = "unknown"
                    
                    if state_elem and state_elem[0]:
                        oper_elem = state_elem[0].getElementsByTagNameNS(ns, "oper-status")
                        if oper_elem and oper_elem[0].firstChild:
                            if_state = oper_elem[0].firstChild.nodeValue
                    
                    interface_list.append(if_name)
                    
                    status_icon = "🟢" if if_state.upper() == "UP" else "🔴" if if_state.upper() == "DOWN" else "🟡"
                    print(f"  {status_icon} {if_name:20} | {if_state}")
            
            print("=" * 50)
            return interface_list
            
        except Exception as e:
            print(f"  ❌ Error descubriendo interfaces: {e}")
            return []
    
    def test_connection(self):
        """Prueba básica de configuración"""
        print(f"\n🧪 Probando operaciones NETCONF...")
        
        try:
            # Probar configuración simple
            test_config = '''<config>
    <system xmlns="http://openconfig.net/yang/system">
        <config>
            <domain-name>test.arista.com</domain-name>
        </config>
    </system>
</config>'''
            
            # Usar edit_config para configuración de prueba
            reply = self.manager.edit_config(
                target="running",
                config=test_config,
                default_operation="merge"
            )
            
            print(f"  ✅ Configuración de prueba aplicada")
            
            # Verificar configuración
            get_filter = '''<system xmlns="http://openconfig.net/yang/system">
    <config>
        <domain-name/>
    </config>
</system>'''
            
            reply = self.manager.get_config(
                source="running",
                filter=("subtree", get_filter)
            )
            
            print(f"  ✅ Lectura de configuración exitosa")
            return True
            
        except Exception as e:
            print(f"  ❌ Error en prueba: {e}")
            return False
    
    def monitor(self, interval=5, duration=None):
        """Monitoreo principal"""
        if not self.connect():
            return
        
        # Listar capacidades
        self.list_capabilities()
        
        # Probar conexión
        self.test_connection()
        
        # Descubrir interfaces
        interfaces = self.discover_interfaces()
        
        # Si nuestra interfaz no está en la lista, usar la primera
        if interfaces and self.interface not in interfaces:
            print(f"\n⚠️  {self.interface} no encontrada. Usando {interfaces[0]}")
            self.interface = interfaces[0]
        
        print(f"\n🎯 Interfaz seleccionada: {self.interface}")
        print(f"📊 Iniciando monitoreo cada {interval} segundos...")
        print("   Presiona Ctrl+C para detener")
        print("-" * 60)
        
        start_time = time.time()
        iteration = 0
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            try:
                while True:
                    current_time = time.time()
                    
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteración {iteration + 1}")
                    
                    # Obtener estadísticas
                    stats = self.get_interface_stats()
                    
                    if stats:
                        # Calcular tasa de tráfico
                        traffic_rate = self.calculate_traffic_rate(stats)
                        
                        # Formatear y guardar
                        output = self.format_output(stats, traffic_rate, current_time)
                        json.dump(output, f, ensure_ascii=False)
                        f.write('\n')
                        f.flush()
                        
                        # Mostrar en consola
                        in_octets = int(stats.get('in-octets', 0))
                        out_octets = int(stats.get('out-octets', 0))
                        
                        print(f"  Modelo: {stats.get('model', 'unknown')}")
                        print(f"  Octetos: in={in_octets:,}, out={out_octets:,}")
                        print(f"  Paquetes: in={stats.get('in-packets', '0')}, out={stats.get('out-packets', '0')}")
                        print(f"  Tasa: in={traffic_rate['in-bps']} bps, out={traffic_rate['out-bps']} bps")
                    else:
                        print(f"  ⚠️  Sin datos de estadísticas")
                    
                    iteration += 1
                    
                    # Verificar duración
                    if duration and (current_time - start_time) >= duration:
                        print(f"\n✅ Monitoreo completado ({duration} segundos)")
                        break
                    
                    # Esperar para próxima iteración
                    elapsed = time.time() - current_time
                    sleep_time = interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        print(f"  ⚠️  Polling tardó {elapsed:.2f}s")
                        
            except KeyboardInterrupt:
                print("\n\n⏹️  Monitoreo detenido")
            except Exception as e:
                print(f"\n❌ Error: {e}")
        
        # Cerrar sesión
        if self.manager:
            self.manager.close_session()
            print("\n🔌 Sesión NETCONF cerrada")

def main():
    print("\n" + "="*60)
    print("NETCONF MONITOR - Arista EOS")
    print("="*60)
    print(f"Host: {HOST}:{PORT}")
    print(f"Usuario: {USER}")
    print(f"Salida: {OUTPUT_FILE}")
    print(f"Intervalo: {POLL_INTERVAL} segundos")
    print("="*60)
    
    # Preguntar interfaz
    default_if = "Ethernet1"
    interface_name = input(f"Ingresa nombre de interfaz [{default_if}]: ").strip()
    if not interface_name:
        interface_name = default_if
    
    # Crear monitor
    monitor = AristaNETCONFMonitor(interface_name)
    
    # Para prueba rápida de 30 segundos (ideal para estudio):
    # monitor.monitor(interval=POLL_INTERVAL, duration=30)
    
    # Para monitoreo continuo:
    monitor.monitor(interval=POLL_INTERVAL)
    
    print(f"\n💾 Datos guardados en: {OUTPUT_FILE}")
    print("📈 Listo para comparación con gNMI y SNMP")

if __name__ == "__main__":
    # Instalar dependencias si es necesario
    try:
        from ncclient import manager
    except ImportError:
        print("❌ ncclient no instalado.")
        print("   Instala con: pip install ncclient")
        sys.exit(1)
    
    main()

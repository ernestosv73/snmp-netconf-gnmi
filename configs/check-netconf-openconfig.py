#!/usr/bin/env python3
"""
NETCONF simple para Huawei - Solo obtiene y muestra datos
"""
from ncclient import manager
import xml.dom.minidom as MD

HOST = '172.100.100.7'
PORT = 830
USER = 'admin'
PASS = 'admin'

def test_huawei_ifm():
    """Prueba directa del modelo Huawei IFM"""
    with manager.connect(
        host=HOST, port=PORT, username=USER, password=PASS,
        hostkey_verify=False, device_params={'name': "huaweiyang"},
        timeout=10
    ) as m:
        
        print("1. Probando Huawei IFM...")
        filter_xml = """
        <filter>
            <ifm xmlns="http://www.huawei.com/netconf/vrp/huawei-ifm">
                <interfaces>
                    <interface>
                        <ifName>Ethernet0/1</ifName>
                        <ifStatistics/>
                    </interface>
                </interfaces>
            </ifm>
        </filter>
        """
        
        try:
            reply = m.get(filter=filter_xml)
            xml_pretty = MD.parseString(reply.data_xml).toprettyxml()
            print("Respuesta XML:")
            print(xml_pretty[:2000])  # Mostrar primeros 2000 chars
        except Exception as e:
            print(f"Error: {e}")

def test_openconfig():
    """Prueba modelo OpenConfig"""
    with manager.connect(
        host=HOST, port=PORT, username=USER, password=PASS,
        hostkey_verify=False, device_params={'name': "huaweiyang"},
        timeout=10
    ) as m:
        
        print("\n2. Probando OpenConfig...")
        filter_xml = """
        <filter>
            <interfaces xmlns="http://openconfig.net/yang/interfaces">
                <interface>
                    <name>Ethernet0/1</name>
                    <state>
                        <counters/>
                    </state>
                </interface>
            </interfaces>
        </filter>
        """
        
        try:
            reply = m.get(filter=filter_xml)
            xml_pretty = MD.parseString(reply.data_xml).toprettyxml()
            print("Respuesta XML:")
            print(xml_pretty[:2000])
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_huawei_ifm()
    test_openconfig()

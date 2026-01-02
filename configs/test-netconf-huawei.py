# -*- coding: utf-8 -*-
from ncclient import manager

HOST = '172.100.100.7'  # IP of your NE40 router
PORT = 830            # Default NETCONF port
USER = 'admin'
PASSWORD = 'admin'

try:
    with manager.connect(
        host=HOST,
        port=PORT,
        username=USER,
        password=PASSWORD,
        hostkey_verify=False,  # Set to True in production after adding host key
        device_params={'name': "huaweiyang"}, # Crucial for Huawei devices!
        allow_agent=False,
        look_for_keys=False
    ) as m:
        print(f"Successfully connected to {HOST}!")
        # Example: Get device info
        # reply = m.get(filter='<system-description/>')
        # print(reply.data_xml)
        print("Session ID:", m._session.id)

except Exception as e:
    print(f"Failed to connect: {e}")

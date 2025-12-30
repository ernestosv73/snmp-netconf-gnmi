apt install curl -y
sleep 1
pip install ncclient
sleep 1
bash -c "$(curl -sL https://get-gnmic.openconfig.net)"
sleep 1
apt install snmp snmp-mibs-downloader -y 
sleep 1
download-mibs
sleep 1

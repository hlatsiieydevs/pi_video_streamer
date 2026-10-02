import socket
import struct
import threading
import uuid
import logging
from flask import request, Response
from rtsp_server import rtsp_manager
from camera_manager import camera_manager

logger = logging.getLogger("ONVIFServer")

mac_int = uuid.getnode()
MAC_HEX = f'{mac_int:012x}'.upper()
MAC_ADDR = ':'.join(MAC_HEX[i:i+2] for i in range(0, 12, 2))

WSD_MCAST_GRP = '239.255.255.250'
WSD_MCAST_PORT = 3702

def build_probe_match(message_id, host_ip, port):
    """Builds a WS-Discovery ProbeMatch SOAP response"""
    my_uuid = str(uuid.uuid4())
    xaddr = f"http://{host_ip}:{port}/onvif/device_service"
    
    return f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
    xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
    xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
    xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
    <SOAP-ENV:Header>
        <wsa:MessageID>urn:uuid:{my_uuid}</wsa:MessageID>
        <wsa:RelatesTo>{message_id}</wsa:RelatesTo>
        <wsa:To>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</wsa:Action>
    </SOAP-ENV:Header>
    <SOAP-ENV:Body>
        <wsd:ProbeMatches>
            <wsd:ProbeMatch>
                <wsa:EndpointReference>
                    <wsa:Address>urn:uuid:{my_uuid}</wsa:Address>
                </wsa:EndpointReference>
                <wsd:Types>dn:NetworkVideoTransmitter</wsd:Types>
                <wsd:Scopes>onvif://www.onvif.org/type/video_encoder onvif://www.onvif.org/mac/{MAC_HEX}</wsd:Scopes>
                <wsd:XAddrs>{xaddr}</wsd:XAddrs>
                <wsd:MetadataVersion>1</wsd:MetadataVersion>
            </wsd:ProbeMatch>
        </wsd:ProbeMatches>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

class WSDiscoveryServer(threading.Thread):
    """UDP Multicast Server for WS-Discovery"""
    def __init__(self, host_ip, http_port=5000):
        super().__init__(daemon=True)
        self.host_ip = host_ip
        self.http_port = http_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', WSD_MCAST_PORT))
        
        mreq = struct.pack("4sl", socket.inet_aton(WSD_MCAST_GRP), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def run(self):
        logger.info(f"WS-Discovery Server listening on {WSD_MCAST_GRP}:{WSD_MCAST_PORT}")
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                msg = data.decode('utf-8', errors='ignore')
                
                if "Probe" in msg and "MessageID" in msg:
                    # Extract MessageID to set as RelatesTo
                    msg_id = ""
                    for line in msg.split('<'):
                        if "MessageID>" in line:
                            msg_id = line.split('>')[1].split('<')[0]
                            break
                            
                    logger.info(f"Received WS-Discovery Probe from {addr}, replying with ProbeMatch")
                    response = build_probe_match(msg_id, self.host_ip, self.http_port)
                    self.sock.sendto(response.encode('utf-8'), addr)
            except Exception as e:
                logger.error(f"WS-Discovery error: {e}")

def init_onvif(app):
    """Registers ONVIF SOAP routes to the Flask app and starts WS-Discovery"""
    
    host_ip = rtsp_manager.host_ip
    wsd = WSDiscoveryServer(host_ip, http_port=5000)
    wsd.start()

    @app.route('/onvif/device_service', methods=['POST'])
    def onvif_device_service():
        data = request.data.decode('utf-8', errors='ignore')
        
        if "GetDeviceInformation" in data:
            resp = f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
    <SOAP-ENV:Body>
        <tds:GetDeviceInformationResponse>
            <tds:Manufacturer>RPi BVS Emu</tds:Manufacturer>
            <tds:Model>BasicVideoStreamer</tds:Model>
            <tds:FirmwareVersion>1.0.0</tds:FirmwareVersion>
            <tds:SerialNumber>{MAC_HEX}</tds:SerialNumber>
            <tds:HardwareId>{MAC_ADDR}</tds:HardwareId>
        </tds:GetDeviceInformationResponse>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
            return Response(resp, mimetype='application/soap+xml')
            
        elif "GetCapabilities" in data or "GetServices" in data:
            # Tell the client where the media service is
            resp = f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
    <SOAP-ENV:Body>
        <tds:GetCapabilitiesResponse>
            <tds:Capabilities>
                <tt:Media>
                    <tt:XAddr>http://{host_ip}:5000/onvif/media_service</tt:XAddr>
                    <tt:StreamingCapabilities>
                        <tt:RTPMulticast>false</tt:RTPMulticast>
                        <tt:RTP_TCP>true</tt:RTP_TCP>
                        <tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>
                    </tt:StreamingCapabilities>
                </tt:Media>
            </tds:Capabilities>
        </tds:GetCapabilitiesResponse>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
            return Response(resp, mimetype='application/soap+xml')

        # Fallback for other device service commands
        return Response('<?xml version="1.0" encoding="utf-8"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"><SOAP-ENV:Body/></SOAP-ENV:Envelope>', mimetype='application/soap+xml')

    @app.route('/onvif/media_service', methods=['POST'])
    def onvif_media_service():
        data = request.data.decode('utf-8', errors='ignore')
        
        if "GetProfiles" in data:
            resp = f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" xmlns:trt="http://www.onvif.org/ver10/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
    <SOAP-ENV:Body>
        <trt:GetProfilesResponse>
            <trt:Profiles token="profile0">
                <tt:Name>MainProfile</tt:Name>
            </trt:Profiles>
        </trt:GetProfilesResponse>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
            return Response(resp, mimetype='application/soap+xml')

        elif "GetStreamUri" in data:
            # We will use cam0 as the default ONVIF profile stream
            cam_id = 0
            if camera_manager.cameras:
                cam_id = list(camera_manager.cameras.keys())[0]
            
            rtsp_url = rtsp_manager.get_rtsp_url(cam_id)
            resp = f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" xmlns:trt="http://www.onvif.org/ver10/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
    <SOAP-ENV:Body>
        <trt:GetStreamUriResponse>
            <trt:MediaUri>
                <tt:Uri>{rtsp_url}</tt:Uri>
                <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
                <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
                <tt:Timeout>PT60S</tt:Timeout>
            </trt:MediaUri>
        </trt:GetStreamUriResponse>
    </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
            return Response(resp, mimetype='application/soap+xml')

        return Response('<?xml version="1.0" encoding="utf-8"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"><SOAP-ENV:Body/></SOAP-ENV:Envelope>', mimetype='application/soap+xml')

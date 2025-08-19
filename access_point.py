# access_point.py

import network

def start_access_point(ssid="ESP32_LAB", password="hacktheplanet"):
    """
    Initializes the ESP32 as a Wi-Fi Access Point.
    Args:
        ssid (str): Name of the Wi-Fi network.
        password (str): WPA2 password for the network.
    """
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA2_PSK)
    
    while not ap.active():
        pass  # Wait until AP is active

    print("Access Point started")
    print("Network config:", ap.ifconfig())
    return ap

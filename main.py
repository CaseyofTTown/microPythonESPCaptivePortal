# main.py
# ESP32 Wi-Fi Provisioning with Captive Portal, Access Point & DNS Hijack

import network
import time
import sys
import _thread        # For running DNS server alongside HTTP server
import machine        # Optional LED indicators
import webserver
import accessPoint
import dns_hijack

# ---------- CONFIG ----------
WIFI_TIMEOUT = 10               # Seconds to try connecting before fallback
CREDS_FILE = "wifi_credentials.txt"
AP_SSID = "ESP32_LAB"            # AP name during provisioning
AP_PASSWORD = "hacktheplanet"    # WPA2 password for AP

# ---------- LED HELPERS ----------
from neopixel import NeoPixel

NEOPIXEL_PIN = 48       # GPIO pin connected to NeoPixel
NEOPIXEL_COUNT = 1      # Number of LEDs in strip
np = None

try:
    pin = machine.Pin(NEOPIXEL_PIN, machine.Pin.OUT)
    np = NeoPixel(pin, NEOPIXEL_COUNT)
except Exception as e:
    print("[LED] NeoPixel init failed:", e)

def set_color(r, g, b):
    if np:
        np[0] = (r, g, b)
        np.write()

def pulse_color(r, g, b, times=3, delay=0.2):
    if np:
        for _ in range(times):
            np[0] = (r, g, b)
            np.write()
            time.sleep(delay)
            np[0] = (0, 0, 0)
            np.write()
            time.sleep(delay)

def status_connecting():
    pulse_color(0, 0, 255, times=10, delay=0.1)  # Blue pulse

def status_success():
    set_color(0, 255, 0)  # Solid green

def status_error():
    pulse_color(255, 0, 0, times=6, delay=0.15)  # Red pulse



# ---------- FILE HELPERS ----------
def load_credentials():
    """
    Reads stored Wi-Fi credentials from file.
    Returns (ssid, password) or (None, None) if not found/invalid.
    """
    try:
        creds = {}
        with open(CREDS_FILE, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    creds[k] = v
        ssid = creds.get("SSID")
        password = creds.get("PASSWORD")
        if ssid and password:
            return ssid, password
        else:
            print("[BOOT] Credentials file incomplete.")
    except OSError:
        print("[BOOT] No saved credentials file.")
    except Exception as e:
        print("[BOOT] Failed to load credentials:", e)
    return None, None

# ---------- WIFI CONNECTION ----------

def connect_to_wifi(ssid, password, timeout=WIFI_TIMEOUT):
    """
    Attempts to connect to a Wi-Fi network.
    Returns True if connected, False otherwise.
    """
    print(f"[WIFI] Connecting to SSID: {ssid}")

    # Explicit STA/AP references
    wlan_sta = network.WLAN(network.STA_IF)
    wlan_ap = network.WLAN(network.AP_IF)

    # Clear any previous state
    wlan_sta.active(False)
    wlan_ap.active(False)
    time.sleep(0.5)

    # Activate station mode only
    wlan_sta.active(True)
    wlan_sta.connect(ssid, password)

    for _ in range(timeout * 2):  # check every 0.5s
        if wlan_sta.isconnected():
            print("[WIFI] Connected! IP config:", wlan_sta.ifconfig())
            led_on()
            return True
        time.sleep(0.5)

    print("[WIFI] Connection failed.")
    wlan_sta.disconnect()
    led_blink(5, 0.1)
    return False

# ---------- PROVISIONING FLOW ----------
def start_provisioning():
    """
    Enables AP mode, starts DNS hijack & HTTP server for captive portal.
    Blocks until device is provisioned or reset.
    """
    ap = accessPoint.start_access_point(AP_SSID, AP_PASSWORD)

    # Start DNS hijack server in a separate thread
    try:
        _thread.start_new_thread(dns_hijack.start_dns_server, ())
    except Exception as e:
        print("[DNS] Could not start in new thread:", e)

    print("[PORTAL] Starting HTTP captive portal...")
    webserver.start_http(provision_callback=provision_and_connect)

def provision_and_connect(ssid=None, password=None):
    if ssid and password:
        if connect_to_wifi(ssid, password):
            shutdown_captive_portal()
            print("[STA-SERVER] Starting post-provisioning server...")
            _thread.start_new_thread(webserver.start_sta_server, ())
            return
        else:
            print("[PROVISION] Saved creds failed; reopening portal.")
    start_provisioning()

    
def shutdown_captive_portal():
    import gc
    wlan_ap = network.WLAN(network.AP_IF)
    wlan_ap.active(False)
    print("[PORTAL] Captive portal disabled")

    # Optional: stop DNS and HTTP servers if you have handles
    # e.g., dns_hijack.stop(), webserver.stop()

    gc.collect()


# ---------- BOOT SEQUENCE ----------
def main():
    ssid, password = load_credentials()
    if ssid:
        print(f"[BOOT] Found saved creds for {ssid}. Trying to connect...")
        if not connect_to_wifi(ssid, password):
            start_provisioning()
    else:
        start_provisioning()

# ---------- ENTRY POINT ----------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[SYS] Interrupted by user.")
        sys.exit()
    except Exception as e:
        print("[SYS] Unhandled error:", e)
        start_provisioning()

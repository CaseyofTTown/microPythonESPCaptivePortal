# webserver.py
# MicroPython HTTP server for captive portal
# Serves index.html and handles Wi-Fi provisioning POST
# Designed for ESP32 with modular callback architecture

import socket
import ure  # MicroPython regex, lighter than CPython's re

http_running = True

def stop_http():
    global http_running
    http_running = False
    print("[HTTP] Stop signal received.")

def load_html():
    # Load index.html from filesystem
    try:
        with open("index.html", "r") as f:
            html = f.read()
        # Wrap with HTTP headers
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
        return response
    except Exception as e:
        print("[HTTP] Failed to load index.html:", e)
        return "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError loading portal page."

def url_decode(s):
    # Replace '+' with space
    s = s.replace('+', ' ')
    
    # Decode %xx hex codes manually
    i = 0
    result = ''
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            hex_value = s[i+1:i+3]
            try:
                result += chr(int(hex_value, 16))
                i += 3
            except ValueError:
                result += '%'  # Leave as-is if invalid
                i += 1
        else:
            result += s[i]
            i += 1
    return result


def parse_post_data(request):
    # Extract POST body from HTTP request
    try:
        body = request.split("\r\n\r\n", 1)[1]
        params = {}
        for pair in body.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = url_decode(key)
                value = url_decode(value)
                params[key] = value
        return params
    except Exception as e:
        print("[HTTP] Failed to parse POST data:", e)
        return {}


def save_credentials(ssid, password):
    # Save credentials to a file for later use
    try:
        with open("wifi_credentials.txt", "w") as f:
            f.write("SSID=" + ssid + "\n")
            f.write("PASSWORD=" + password + "\n")
        print("[HTTP] Credentials saved to wifi_credentials.txt")
    except Exception as e:
        print("[HTTP] Failed to save credentials:", e)

def start_http(provision_callback=None):
    global http_running
    http_running = True

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 80))
    s.listen(5)
    s.settimeout(5)

    print("[HTTP] Web server started on port 80")

    while http_running:
        try:
            conn, addr = s.accept()
            request = conn.recv(1024).decode()

            if "POST /provision" in request:
                data = parse_post_data(request)
                ssid = data.get("ssid", "")
                password = data.get("password", "")
                save_credentials(ssid, password)
                if provision_callback:
                    provision_callback(ssid, password)
                response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nProvisioning received. Attempting connection..."
            else:
                response = load_html()

            conn.sendall(response.encode())
            conn.close()
        except OSError as e:
            if e.args[0] != 116:
                print("[HTTP] Socket error:", e)

    s.close()
    print("[HTTP] Server stopped.")


# ----------------------------------------------
#After successful connection we will host a page on a server so we can verify connectivity
def start_sta_server(preferred_port=80, fallback_port=8080):
    # Try binding to preferred port, fallback if needed
    try:
        addr = socket.getaddrinfo('0.0.0.0', preferred_port)[0][-1]
        s = socket.socket()
        s.bind(addr)
        active_port = preferred_port
    except OSError as e:
        print(f"[STA-SERVER] Port {preferred_port} in use. Falling back to {fallback_port}...")
        addr = socket.getaddrinfo('0.0.0.0', fallback_port)[0][-1]
        s = socket.socket()
        s.bind(addr)
        active_port = fallback_port

    s.listen(1)
    print(f"[STA-SERVER] Listening on port {active_port}...")

    while True:
        cl, addr = s.accept()
        print('[STA-SERVER] Client connected from', addr)
        try:
            cl_file = cl.makefile('rwb', 0)
            while True:
                line = cl_file.readline()
                if not line or line == b'\r\n':
                    break

            with open("success.html", "r") as f:
                html = f.read()

            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            cl.send(response)
        except Exception as e:
            print('[STA-SERVER] Error:', e)
        finally:
            cl.close()

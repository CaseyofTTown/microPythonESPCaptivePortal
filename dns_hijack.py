# dns_hijack.py
# MicroPython DNS Hijack Server for Captive Portal
# Author: Casey (with Copilot support)
# Purpose: Intercept all DNS queries and redirect them to ESP32's IP (e.g. 192.168.4.1)

import socket
import time
import gc

# === CONFIGURATION ===
CAPTIVE_PORTAL_IP = "192.168.4.1"
DNS_PORT = 53
MEMORY_THRESHOLD = 8000  # Minimum free bytes before skipping requests
MAX_PACKET_SIZE = 512    # Drop oversized DNS queries

# === GLOBAL CONTROL FLAG ===
dns_running = True

def start_dns_server(ip=CAPTIVE_PORTAL_IP, port=DNS_PORT):
    global dns_running
    dns_running = True

    dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns.bind(('', port))
    print("[DNS] Hijack server started on port", port)

    while dns_running:
        try:
            if gc.mem_free() < MEMORY_THRESHOLD:
                print("[DNS] Low memory, skipping request")
                time.sleep(0.05)
                continue

            data, addr = dns.recvfrom(1024)
            if len(data) > MAX_PACKET_SIZE:
                print("[DNS] Oversized packet dropped")
                continue

            response = build_dns_response(data, ip)
            dns.sendto(response, addr)

            time.sleep(0.01)
            gc.collect()

        except Exception as e:
            print("[DNS] Error:", e)

    dns.close()
    print("[DNS] Server stopped.")


def build_dns_response(request, ip):
    """
    Constructs a DNS response packet that redirects to the given IP.
    Args:
        request (bytes): Raw DNS request packet from client.
        ip (str): IP address to redirect all queries to.
    Returns:
        bytes: DNS response packet.
    """
    # === DNS HEADER ===
    transaction_id = request[:2]       # Echo client's transaction ID
    flags = b'\x81\x80'                # Standard response, no error
    qdcount = request[4:6]             # Number of questions
    ancount = b'\x00\x01'              # One answer
    nscount = b'\x00\x00'              # No authority records
    arcount = b'\x00\x00'              # No additional records

    dns_header = transaction_id + flags + qdcount + ancount + nscount + arcount

    # === QUESTION SECTION ===
    query = request[12:]               # Echo original query

    # === ANSWER SECTION ===
    answer = b'\xc0\x0c'               # Pointer to domain name (offset 12)
    answer += b'\x00\x01'              # Type A (IPv4)
    answer += b'\x00\x01'              # Class IN (Internet)
    answer += b'\x00\x00\x00\x3c'      # TTL = 60 seconds
    answer += b'\x00\x04'              # Data length = 4 bytes

    # Convert IP string to 4 bytes
    ip_bytes = bytes(map(int, ip.split('.')))
    answer += ip_bytes

    return dns_header + query + answer

def stop_dns_server():
    global dns_running
    dns_running = False
    print("[DNS] Stop signal received.")


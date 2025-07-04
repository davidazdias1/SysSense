import time
import socket
import requests
from datetime import datetime

# Configurações
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
CHECK_INTERVAL = 15  # segundos
API_URL = "http://127.0.0.1:8000/status_logger"  

def verificar_conexao(ip, port, timeout=5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return 1
    except Exception:
        return 0

while True:
    status = verificar_conexao(FIELDLOGGER_IP, FIELDLOGGER_PORT)
    try:
        response = requests.post(API_URL, json={"status": status})
        print(f"[{datetime.utcnow()}] Status: {status} - Enviado: {response.status_code}")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Erro ao enviar para API: {e}")
    time.sleep(CHECK_INTERVAL)

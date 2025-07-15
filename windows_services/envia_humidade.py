import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import requests

# ---------------- Configurações ----------------
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1
REGISTRO_HUMIDADE = 5  # Canal 3 analógico (posição 3)
INTERVALO = 5  # segundos
API_URL = "http://127.0.0.1:8000/humidade_logger"  # Endpoint da API FastAPI

# ---------------- Leitura do Modbus ----------------
def ler_entrada_analogica():
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        print("Erro ao conectar ao FieldLogger")
        return None

    try:
        resposta = client.read_holding_registers(address=REGISTRO_HUMIDADE, count=1, slave=MODBUS_UNIT_ID)
        if resposta.isError():
            print("Erro na leitura Modbus")
            return None

        valor_bruto = resposta.registers[0]
        print(f"[{datetime.utcnow()}] Valor bruto (humidade): {valor_bruto}")

        # Conversão direta (FieldLogger já retorna em %)
        humidade = float(valor_bruto)

        return humidade
    finally:
        client.close()

# ---------------- Loop de envio ----------------
while True:
    humidade = ler_entrada_analogica()
    if humidade is not None:
        payload = {
            "sensor": "SensorHum",
            "valor": round(humidade, 2)
        }
        try:
            response = requests.post(API_URL, json=payload)
            print(f"[{datetime.utcnow()}] Humidade: {humidade:.2f}% - Enviado: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] Erro ao enviar humidade: {e}")
    else:
        print(f"[{datetime.utcnow()}] Leitura falhou.")
    time.sleep(INTERVALO)

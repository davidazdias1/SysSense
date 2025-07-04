import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import requests

# Configurações
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1
REGISTRO_PT100 = 3  # Canal 1 analogico
INTERVALO = 5 # segundos
API_URL = "http://127.0.0.1:8000/temperatura_logger"  # FastAPI local

def ler_temperatura():
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        print("Erro ao conectar ao FieldLogger")
        return None

    try:
        resposta = client.read_holding_registers(address=REGISTRO_PT100, count=1, slave=MODBUS_UNIT_ID)
        if resposta.isError():
            print("Erro na leitura Modbus")
            return None
        valor_bruto = resposta.registers[0]
        temperatura = valor_bruto / 1.0
        return temperatura
    finally:
        client.close()

while True:
    temperatura = ler_temperatura()
    if temperatura is not None:
        payload = {
            "sensor": "Sensor1",
            "valor": temperatura
        }
        try:
            response = requests.post(API_URL, json=payload)
            print(f"[{datetime.utcnow()}] Temp: {temperatura:.1f} °C - Enviado: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] Erro ao enviar temperatura: {e}")
    else:
        print(f"[{datetime.utcnow()}] Leitura falhou.")
    time.sleep(INTERVALO)


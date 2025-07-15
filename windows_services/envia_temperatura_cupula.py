import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import requests

# ---------------- Configurações ----------------
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1
REGISTRO_CANAL_2 = 4  # Canal 2 analógico (posição 2 no FieldLogger)
INTERVALO = 5  # segundos
API_URL = "http://127.0.0.1:8000/temperatura_cupula"  # Endpoint da API

# ---------------- Função de leitura Modbus ----------------
def ler_entrada_analogica():
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        print("Erro ao conectar ao FieldLogger")
        return None

    try:
        resposta = client.read_holding_registers(address=REGISTRO_CANAL_2, count=1, slave=MODBUS_UNIT_ID)
        if resposta.isError():
            print("Erro na leitura Modbus")
            return None

        valor_bruto = resposta.registers[0]
        print(f"[{datetime.utcnow()}] Valor bruto lido do Modbus: {valor_bruto}")

        temperatura = float(valor_bruto) + 1# uso direto
        return temperatura
    finally:
        client.close()

# ---------------- Loop de envio ----------------
while True:
    temperatura = ler_entrada_analogica()
    if temperatura is not None:
        payload = {
            "sensor": "SensorCupula",
            "valor": round(temperatura, 2)
        }
        try:
            response = requests.post(API_URL, json=payload)
            print(f"[{datetime.utcnow()}] Temp Cúpula: {temperatura:.2f} °C - Enviado: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.utcnow()}] Erro ao enviar temperatura: {e}")
    else:
        print(f"[{datetime.utcnow()}] Leitura falhou.")
    time.sleep(INTERVALO)

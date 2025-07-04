import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import requests

# Configurações
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1
REGISTRO_DIGITAL = 14  # SensorDigital_1 → HR 40015
INTERVALO = 1  # segundos
API_URL = "http://127.0.0.1:8000/contador_unidades_logger"

ultimo_estado = None  # Guarda o estado anterior
contador = 0  # Contador acumulado de pulsos

def ler_digital():
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        print("Erro ao conectar ao FieldLogger")
        return None

    try:
        resposta = client.read_holding_registers(address=REGISTRO_DIGITAL, count=1, slave=MODBUS_UNIT_ID)
        if resposta.isError():
            print("Erro na leitura Modbus")
            return None
        return int(resposta.registers[0])
    finally:
        client.close()

while True:
    estado = ler_digital()

    if estado is None:
        print(f"[{datetime.utcnow()}] Leitura falhou.")
    elif estado == 0 and ultimo_estado == 5:
        contador += 1  # INCREMENTA
        payload = {
            "valor": contador,
            "sensor": "Contador1"
        }
        try:
            response = requests.post(API_URL, json=payload)
            print(f"[{datetime.utcnow()}] Pulso #{contador} - Enviado")
        except Exception as e:
            print(f"[{datetime.utcnow()}] Erro ao enviar: {e}")
    else:
        print(f"[{datetime.utcnow()}] Estado atual: {estado} - ignorado")

    ultimo_estado = estado
    time.sleep(INTERVALO)

import time
from datetime import datetime, timedelta
from pymodbus.client import ModbusTcpClient
import requests

# ------------------ Configurações ------------------
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1
REGISTRO_DIGITAL = 14  # HR 40015 = address 14 (porque começa em 40001)
API_URL = "http://127.0.0.1:8000/velocidade_logger"

INTERVALO_LEITURA = 1  # segundos
TEMPO_ATIVO = timedelta(seconds=60)

# ------------------ Variáveis de Estado ------------------
tempo_ultimo_movimento = None
velocidade = 0.0
ultima_velocidade_enviada = None

# ------------------ Função de Leitura Modbus ------------------
def ler_digital():
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        return None
    try:
        resposta = client.read_holding_registers(address=REGISTRO_DIGITAL, count=1, slave=MODBUS_UNIT_ID)
        if resposta.isError():
            return None
        return int(resposta.registers[0])
    finally:
        client.close()

# ------------------ Loop Principal ------------------
while True:
    estado = ler_digital()
    agora = datetime.utcnow()

    if estado is not None:
        print(f"Estado lido: {estado}")

        if estado == 5:
            # Tapete em movimento
            tempo_ultimo_movimento = agora
            distancia_metros = 0.455  # distância percorrida
            tempo_segundos = 17       # tempo que demora a percorrer essa distância
            velocidade = distancia_metros / tempo_segundos  # ~0.0267 m/s
        else:
            # Tapete parado por mais de 30 segundos
            if tempo_ultimo_movimento and agora - tempo_ultimo_movimento > TEMPO_ATIVO:
                velocidade = 0.0


        print(f"Velocidade: {velocidade}")

        # Enviar para a API se o valor mudou (evita redundância com comparação segura de floats)
        if ultima_velocidade_enviada is None or round(velocidade, 2) != round(ultima_velocidade_enviada, 2):
            payload = {
                "timestamp": agora.isoformat(),
                "valor": velocidade
            }
            try:
                requests.post(API_URL, json=payload)
                ultima_velocidade_enviada = velocidade
                print(f"→ Velocidade enviada: {velocidade}")
            except Exception as e:
                print(f"[{agora}] Erro ao enviar: {e}")

    else:
        print(f"[{datetime.utcnow()}] Leitura falhou.")

    time.sleep(INTERVALO_LEITURA)

import time
from datetime import datetime, timedelta
from pymodbus.client import ModbusTcpClient
import requests

# ------------------ Configurações ------------------
FIELDLOGGER_IP      = "192.168.0.30"   # IP do FieldLogger
FIELDLOGGER_PORT    = 502              # Porta Modbus TCP
MODBUS_UNIT_ID      = 1                # ID da unidade Modbus (slave id)
REGISTRO_DIGITAL    = 14               # Endereço do registo digital (HR40015)
API_URL             = "http://127.0.0.1:8000/velocidade_logger"

INTERVALO_LEITURA   = 1                # Intervalo entre leituras (s)
TEMPO_ATIVO         = timedelta(seconds=60)  # Tempo para considerar parado

# ------------------ Variáveis de Estado ------------------
tempo_ultimo_movimento    = None       # Quando foi detectado movimento
velocidade                = 0.0        # Velocidade calculada (m/s)
ultima_velocidade_enviada = None       # Para evitar envios repetidos

# ------------------ Função de Leitura Modbus ------------------
def ler_digital():
    """
    Lê o valor do registo digital via Modbus.
    Retorna inteiro lido, ou None em caso de falha.
    """
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        return None
    try:
        resp = client.read_holding_registers(
            address=REGISTRO_DIGITAL,
            count=1,
            slave=MODBUS_UNIT_ID
        )
        if resp.isError():
            return None
        return int(resp.registers[0])
    finally:
        client.close()

# ------------------ Loop Principal ------------------
while True:
    estado = ler_digital()         # lê entrada digital
    agora = datetime.utcnow()      # timestamp atual

    if estado is not None:
        # Leitura OK
        print(f"Estado lido: {estado}")

        if estado == 5:
            # Se o tapete está em movimento
            tempo_ultimo_movimento = agora
            distancia_m = 0.455    # distância percorrida (metros)
            tempo_s      = 17      # tempo para percorrer (s)
            velocidade   = distancia_m / tempo_s  # m/s
        else:
            # Se não houve pulso e passou TEMPO_ATIVO, pára o tapete
            if tempo_ultimo_movimento and (agora - tempo_ultimo_movimento) > TEMPO_ATIVO:
                velocidade = 0.0

        print(f"Velocidade: {velocidade:.4f} m/s")

        # Envia somente se a velocidade mudou (com arredondamento)
        if (ultima_velocidade_enviada is None or
            round(velocidade, 2) != round(ultima_velocidade_enviada, 2)):

            payload = {
                "timestamp": agora.isoformat(),
                "valor": velocidade
            }
            try:
                requests.post(API_URL, json=payload)
                ultima_velocidade_enviada = velocidade
                print(f"→ Velocidade enviada: {velocidade:.4f} m/s")
            except Exception as e:
                print(f"[{datetime.utcnow()}] Erro ao enviar: {e}")

    else:
        # Leitura falhou → considera velocidade zero e envia alerta
        print(f"[{agora}] Leitura falhou.")
        velocidade = 0.0

        # Só envia o zero uma vez até surgir outro valor
        if (ultima_velocidade_enviada is None or
            round(ultima_velocidade_enviada, 2) != 0.0):

            payload = {
                "timestamp": agora.isoformat(),
                "valor": velocidade
            }
            try:
                requests.post(API_URL, json=payload)
                ultima_velocidade_enviada = velocidade
                print(f"→ Alerta Zabbix enviado: {velocidade:.4f} m/s")
            except Exception as e:
                print(f"[{datetime.utcnow()}] Erro ao enviar alerta: {e}")

    time.sleep(INTERVALO_LEITURA)  # espera antes da próxima leitura

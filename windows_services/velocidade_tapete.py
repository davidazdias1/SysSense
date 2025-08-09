import time
from datetime import datetime, timedelta
from pymodbus.client import ModbusTcpClient
import requests

# ------------------ Configurações ------------------
FIELDLOGGER_IP      = "192.168.0.30"             # IP do FieldLogger
FIELDLOGGER_PORT    = 502                        # Porta Modbus TCP
MODBUS_UNIT_ID      = 1                          # ID da unidade Modbus (slave id)
REGISTRO_DIGITAL    = 14                         # Endereço do registo digital (HR40015)
API_URL             = "http://127.0.0.1:8000/velocidade_logger"

INTERVALO_LEITURA   = 1                          # Intervalo entre leituras (s)
TEMPO_ATIVO         = timedelta(seconds=60)      # Tempo para considerar parado
DISTANCIA_M         = 0.455                      # Distância fixa por pulso (m)
TEMPO_S             = 17                         # Tempo fixo por pulso (s)
VELO_FIXA           = DISTANCIA_M / TEMPO_S      # Velocidade fixa (m/s)

# ------------------ Variáveis de Estado ------------------
ultimo_estado = 0                # Para detectar borda de subida (0→5)
tempo_ultimo_movimento = None    # Quando foi detectado o último pulso válido
velocidade = 0.0                 # Velocidade atual (m/s)
ultima_velocidade_enviada = None # Para evitar envios repetidos

# ------------------ Função de Leitura Modbus ------------------
def ler_digital():
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
    estado = ler_digital()           # lê entrada digital
    agora = datetime.utcnow()        # timestamp atual

    if estado is not None:
        print(f"Estado lido: {estado}")

        # só tratamos movimento na transição 0→5
        if estado == 5 and ultimo_estado != 5:
            # pulso detectado → velocidade fixa
            tempo_ultimo_movimento = agora
            velocidade = VELO_FIXA
            print("→ Movimento detectado, velocidade fixa aplicada.")

        else:
            # se passou TEMPO_ATIVO sem novo pulso, zera a velocidade
            if tempo_ultimo_movimento and (agora - tempo_ultimo_movimento) > TEMPO_ATIVO:
                if velocidade != 0.0:
                    print("→ Timeout sem pulso, parada detectada.")
                velocidade = 0.0

    else:
        # Leitura falhou → considera como sem pulso
        print(f"[{agora.isoformat()}] Leitura falhou.")
        if tempo_ultimo_movimento and (agora - tempo_ultimo_movimento) > TEMPO_ATIVO:
            velocidade = 0.0

    print(f"Velocidade atual: {velocidade:.4f} m/s")

    # envia somente se a velocidade mudou (arredondando a 2 casas)
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
            print(f"[{datetime.utcnow().isoformat()}] Erro ao enviar: {e}")

    # atualiza o último estado (None vira 0)
    ultimo_estado = estado if estado is not None else 0

    time.sleep(INTERVALO_LEITURA)

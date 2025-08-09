import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import requests

# --------------------------
# Configurações de ligação
# --------------------------
FIELDLOGGER_IP    = "192.168.0.30"  # IP do FieldLogger Modbus
FIELDLOGGER_PORT  = 502             # Porta Modbus TCP
MODBUS_UNIT_ID    = 1               # ID da unidade Modbus (slave id)

# Endereços de registos digitais
REGISTRO_PEQUENAS = 15  # registo para detetar peças pequenas
REGISTRO_GRANDES  = 16  # registo para detetar peças grandes

INTERVALO = 0.1         # intervalo de leitura (s) – curto para maior precisão

# URLs da API onde enviar os contadores
API_URL_PEQUENAS = "http://127.0.0.1:8000/contador_unidades_logger"
API_URL_GRANDES  = "http://127.0.0.1:8000/contador_unidades_logger_grandes"

# --------------------------
# Variáveis de estado
# --------------------------
contador_pequenas = 0   # conta de peças pequenas
contador_grandes  = 0   # conta de peças grandes

pulso_pequena_ativo = False  # flag para detetar borda de descida em pequenas
pulso_grande_ativo  = False  # flag para detetar borda de descida em grandes

# --------------------------
# Função para ler um registo digital via Modbus
# --------------------------
def ler_digital(registro):
    """
    Lê o valor do registo 'registro' no FieldLogger.
    Devolve None em caso de falha, ou o valor inteiro lido.
    """
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        print("Erro ao conectar ao FieldLogger")
        return None
    try:
        resposta = client.read_holding_registers(
            address=registro,
            count=1,
            slave=MODBUS_UNIT_ID
        )
        if resposta.isError():
            print(f"Erro na leitura Modbus do registo {registro}")
            return None
        # retorna o primeiro valor lido
        return int(resposta.registers[0])
    finally:
        client.close()

# --------------------------
# Ciclo principal
# --------------------------
while True:
    # lê estado das entradas digitais
    estado_pequenas = ler_digital(REGISTRO_PEQUENAS)
    estado_grandes  = ler_digital(REGISTRO_GRANDES)

    # se falhou a leitura, espera e tenta de novo
    if estado_pequenas is None or estado_grandes is None:
        print(f"[{datetime.utcnow()}] Leitura falhou.")
        time.sleep(INTERVALO)
        continue

    # 1) detectar início de pulso em pequenas (valor==5)
    if estado_pequenas == 5 and not pulso_pequena_ativo:
        pulso_pequena_ativo = True

    # 2) detectar início de pulso em grandes (valor==5)
    if estado_grandes == 5 and not pulso_grande_ativo:
        pulso_grande_ativo = True

    # 3) detectar fim de pulso (valor==0) e processar
    if estado_pequenas == 0 and pulso_pequena_ativo:
        # se também houve pulso grande, conta como peça grande
        if pulso_grande_ativo:
            contador_grandes += 1
            payload = {"valor": contador_grandes, "sensor": "ContadorGrandes"}
            try:
                requests.post(API_URL_GRANDES, json=payload)
                print(f"[{datetime.utcnow()}] Peça GRANDE #{contador_grandes} - Enviado")
            except Exception as e:
                print(f"[{datetime.utcnow()}] Erro ao enviar peça grande: {e}")
        else:
            # caso contrário, conta como peça pequena
            contador_pequenas += 1
            payload = {"valor": contador_pequenas, "sensor": "ContadorPequenas"}
            try:
                requests.post(API_URL_PEQUENAS, json=payload)
                print(f"[{datetime.utcnow()}] Peça pequena #{contador_pequenas} - Enviado")
            except Exception as e:
                print(f"[{datetime.utcnow()}] Erro ao enviar peça pequena: {e}")

        # limpar flags para próximo pulso
        pulso_pequena_ativo = False
        pulso_grande_ativo  = False

    elif estado_grandes == 0 and pulso_grande_ativo:
        # se o pulso grande terminou sem pequenas, só limpa a flag
        pulso_grande_ativo = False

    else:
        # estado normal, aguardando próximo pulso
        print(f"[{datetime.utcnow()}] Aguardando pulso... "
              f"Pequenas: {estado_pequenas}, Grandes: {estado_grandes}")

    # espera antes da próxima leitura
    time.sleep(INTERVALO)

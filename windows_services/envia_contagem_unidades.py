import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import requests

FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1
REGISTRO_PEQUENAS = 15
REGISTRO_GRANDES = 16
INTERVALO = 0.1  # mais rápido para melhor precisão

API_URL_PEQUENAS = "http://127.0.0.1:8000/contador_unidades_logger"
API_URL_GRANDES = "http://127.0.0.1:8000/contador_unidades_logger_grandes"

contador_pequenas = 0
contador_grandes = 0

pulso_pequena_ativo = False
pulso_grande_ativo = False

def ler_digital(registro):
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect():
        print("Erro ao conectar ao FieldLogger")
        return None
    try:
        resposta = client.read_holding_registers(address=registro, count=1, slave=MODBUS_UNIT_ID)
        if resposta.isError():
            print(f"Erro na leitura Modbus do registrador {registro}")
            return None
        return int(resposta.registers[0])
    finally:
        client.close()

while True:
    estado_pequenas = ler_digital(REGISTRO_PEQUENAS)
    estado_grandes = ler_digital(REGISTRO_GRANDES)

    if estado_pequenas is None or estado_grandes is None:
        print(f"[{datetime.utcnow()}] Leitura falhou.")
        time.sleep(INTERVALO)
        continue

    # Verifica início de pulso
    if estado_pequenas == 5 and not pulso_pequena_ativo:
        pulso_pequena_ativo = True

    if estado_grandes == 5 and not pulso_grande_ativo:
        pulso_grande_ativo = True

    # Verifica fim de pulso e processa
    if estado_pequenas == 0 and pulso_pequena_ativo:
        if pulso_grande_ativo:
            contador_grandes += 1
            payload = {"valor": contador_grandes, "sensor": "ContadorGrandes"}
            try:
                requests.post(API_URL_GRANDES, json=payload)
                print(f"[{datetime.utcnow()}] Peça GRANDE #{contador_grandes} - Enviado")
            except Exception as e:
                print(f"[{datetime.utcnow()}] Erro ao enviar peça grande: {e}")
        else:
            contador_pequenas += 1
            payload = {"valor": contador_pequenas, "sensor": "ContadorPequenas"}
            try:
                requests.post(API_URL_PEQUENAS, json=payload)
                print(f"[{datetime.utcnow()}] Peça pequena #{contador_pequenas} - Enviado")
            except Exception as e:
                print(f"[{datetime.utcnow()}] Erro ao enviar peça pequena: {e}")
        pulso_pequena_ativo = False
        pulso_grande_ativo = False  # reinicia também para não repetir

    elif estado_grandes == 0 and pulso_grande_ativo:
        # Se o grande terminou o pulso sem pequenas, apenas limpa o estado
        pulso_grande_ativo = False

    else:
        print(f"[{datetime.utcnow()}] Aguardando pulso... Pequenas: {estado_pequenas}, Grandes: {estado_grandes}")

    time.sleep(INTERVALO)

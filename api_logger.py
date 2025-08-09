#!/usr/bin/env python3
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from pymongo.collection import Collection
from pydantic import BaseModel
from pymodbus.client import ModbusTcpClient
from datetime import datetime
from pathlib import Path
import threading, time, os

# --------------------------
# Configurações gerais
# --------------------------
MONGO_URI        = "mongodb://localhost:27017/"
DB_NAME          = "ProdSenseBD"
FIELDLOGGER_IP   = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID   = 1

# --------------------------
# Registros Modbus do Tapete
# --------------------------
REG_ENTRADA_CANAL_4 = 17   # habilita o tapete (1 = on, 0 = off)
REG_ENTRADA_CANAL_8 = 21   # modo: 0 = automático, 1 = manual
REG_SAIDA_LUZ_VERDE = 26   # saída do tapete/luz verde

# --------------------------
# Conexão ao MongoDB
# --------------------------
mongo       = MongoClient(MONGO_URI)
db          = mongo[DB_NAME]
col_status  : Collection = db["comunicacao_logger"]
col_temp    : Collection = db["temperatura_logger"]
col_hum     : Collection = db["humidade_logger"]
col_vel     : Collection = db["velocidade_logger"]
col_cnt_s   : Collection = db["contador_unidades_logger"]
col_cnt_l   : Collection = db["contador_unidades_logger_grandes"]

# --------------------------
# Inicialização do FastAPI
# --------------------------
app = FastAPI()
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static"
)

# --------------------------
# Modelos Pydantic
# --------------------------
class StatusEntrada(BaseModel):
    status: int

class TemperaturaEntrada(BaseModel):
    sensor: str
    valor: float

class ContadorEntrada(BaseModel):
    sensor: str
    valor: int

class VelocidadeEntrada(BaseModel):
    timestamp: str
    valor: float

# --------------------------
# Helpers Modbus
# --------------------------
def ler_registro_modbus(end: int):
    client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
    if not client.connect(): return None
    try:
        resp = client.read_holding_registers(address=end, count=1, slave=MODBUS_UNIT_ID)
        if resp.isError(): return None
        return resp.registers[0]
    finally:
        client.close()

# --------------------------
# Monitor de Canal 4 em Background
# --------------------------
def monitorar_canal_4_em_background():
    while True:
        val = ler_registro_modbus(REG_ENTRADA_CANAL_4)
        if val == 0:
            # força desligar o tapete
            c = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
            try:
                c.connect()
                c.unit_id = MODBUS_UNIT_ID
                c.write_register(REG_SAIDA_LUZ_VERDE, 0, slave=MODBUS_UNIT_ID)
            finally:
                c.close()
        time.sleep(1)

@app.on_event("startup")
def startup_monitor():
    t = threading.Thread(target=monitorar_canal_4_em_background, daemon=True)
    t.start()

# --------------------------
# Endpoint HTML
# --------------------------
@app.get("/", response_class=HTMLResponse)
def pagina_html():
    html = Path("relay_control.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, status_code=200)

# --------------------------
# Logging Genérico
# --------------------------
@app.post("/status_logger")
def postar_status(d: StatusEntrada):
    doc = {"timestamp": datetime.utcnow(), "status": d.status}
    res = col_status.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"msg":"Status inserido","dados":doc}

@app.post("/temperatura_logger")
def postar_temp(d: TemperaturaEntrada):
    doc = {"timestamp": datetime.utcnow(), "sensor":d.sensor, "valor":d.valor}
    res = col_temp.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"msg":"Temperatura inserida","dados":doc}

@app.post("/humidade_logger")
def postar_hum(d: TemperaturaEntrada):
    doc = {"timestamp": datetime.utcnow(), "sensor":d.sensor, "valor":d.valor}
    res = col_hum.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"msg":"Humidade inserida","dados":doc}

@app.post("/contador_unidades_logger")
def postar_cnt_small(d: ContadorEntrada):
    doc = {
        "timestamp": datetime.utcnow(),
        "sensor": d.sensor,
        "valor": d.valor
    }
    res = col_cnt_s.insert_one(doc)
    # converte o ObjectId em string
    doc["_id"] = str(res.inserted_id)
    return {"msg": "Contador pequenas inserido", "dados": doc}

@app.post("/contador_unidades_logger_grandes")
def postar_cnt_large(d: ContadorEntrada):
    # monta o documento sem o _id
    doc = {
        "timestamp": datetime.utcnow(),
        "sensor": d.sensor,
        "valor": d.valor
    }
    # insere no MongoDB e obtém o ObjectId
    res = col_cnt_l.insert_one(doc)
    # converte o ObjectId em string antes de incluir no JSON de resposta
    doc["_id"] = str(res.inserted_id)
    return {"msg": "Contador grandes inserido", "dados": doc}


@app.post("/velocidade_logger")
def postar_vel(d: VelocidadeEntrada):
    doc = {"timestamp": datetime.fromisoformat(d.timestamp), "valor":d.valor}
    res = col_vel.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"msg":"Velocidade inserida","dados":doc}

# --------------------------
# Últimas Leituras
# --------------------------
@app.get("/ultima_temperatura")
def get_ultima_temp():
    u = col_temp.find_one(sort=[("timestamp",-1)])
    if not u: return JSONResponse({"error":"Sem temperatura"},404)
    return {"timestamp":u["timestamp"],"valor":u["valor"]}

@app.get("/ultima_humidade")
def get_ultima_hum():
    u = col_hum.find_one(sort=[("timestamp",-1)])
    if not u: return JSONResponse({"error":"Sem humidade"},404)
    return {"timestamp":u["timestamp"],"valor":u["valor"]}

@app.get("/ultima_velocidade")
def get_ultima_vel():
    u = col_vel.find_one(sort=[("timestamp",-1)])
    if not u: return JSONResponse({"error":"Sem velocidade"},404)
    return {"timestamp":u["timestamp"],"valor":u["valor"]}

# --------------------------
# Controle de Relés
# --------------------------
RELAY1=8; RELAY2=9
def controlar_rele_generico(state:str, addr:int, nome:str):
    if state not in ("on","off"):
        return JSONResponse({"error":"Estado inválido"},400)
    client = ModbusTcpClient(FIELDLOGGER_IP,port=FIELDLOGGER_PORT)
    try:
        if not client.connect(): raise Exception("Falha conexão Modbus")
        client.unit_id = MODBUS_UNIT_ID
        val = True if state=="on" else False
        rsp = client.write_coil(addr,val)
        if rsp.isError(): raise Exception("Erro coil Modbus")
        return {"status":f"{nome} {'ligado' if val else 'desligado'} com sucesso"}
    except Exception as e:
        return JSONResponse({"error":str(e)},500)
    finally:
        client.close()

@app.post("/relay_temp/{state}")
def relay_temp(state:str):
    return controlar_rele_generico(state, RELAY1, "Ventilador")

@app.post("/relay_hum/{state}")
def relay_hum(state:str):
    if state not in ("on","off"):
        return JSONResponse({"error":"Estado inválido"},400)
    client = ModbusTcpClient(FIELDLOGGER_IP,port=FIELDLOGGER_PORT)
    try:
        if not client.connect(): raise Exception("Falha conexão Modbus")
        client.unit_id = MODBUS_UNIT_ID
        pulses = 1 if state=="on" else 2
        for _ in range(pulses):
            client.write_coil(RELAY2,True); time.sleep(0.1)
            client.write_coil(RELAY2,False); time.sleep(0.1)
        return {"status":f"Humidificador {'ligado' if state=='on' else 'desligado'} com sucesso"}
    except Exception as e:
        return JSONResponse({"error":str(e)},500)
    finally:
        client.close()

@app.post("/escrever_registro/{endereco}/{valor}")
def escrever_registro(endereco:int, valor:int):
    client=ModbusTcpClient(FIELDLOGGER_IP,port=FIELDLOGGER_PORT)
    try:
        if not client.connect(): raise Exception("Falha conexão Modbus")
        client.unit_id = MODBUS_UNIT_ID
        rsp = client.write_register(endereco,valor)
        if rsp.isError(): raise Exception("Erro register Modbus")
        return {"status":f"Registrador {endereco} atualizado para {valor}"}
    except Exception as e:
        return JSONResponse({"error":str(e)},500)
    finally:
        client.close()

# --------------------------
# Tapete / Luz Verde
# --------------------------
@app.get("/luz_verde/status")
def status_luz_verde():
    v = ler_registro_modbus(REG_SAIDA_LUZ_VERDE)
    if v is None:
        return JSONResponse({"error":"Não consegui ler estado"},500)
    return {"estado":"on" if v==1 else "off"}

@app.post("/luz_verde/{estado}")
def api_luz_verde(estado:str):
    if estado not in ("on","off"):
        return JSONResponse({"error":"use 'on' ou 'off'"},400)

    # só permite ligar se Canal4=1 e Canal8=0
    if estado=="on":
        if ler_registro_modbus(REG_ENTRADA_CANAL_4)!=1:
            return JSONResponse({"error":"Segurança ativa, não posso ligar"},400)
        if ler_registro_modbus(REG_ENTRADA_CANAL_8)!=0:
            return JSONResponse({"error":"Modo manual ativo, não posso ligar"},400)

    # efetua escrita
    c = ModbusTcpClient(FIELDLOGGER_IP,port=FIELDLOGGER_PORT)
    try:
        c.connect()
        c.unit_id = MODBUS_UNIT_ID
        val = 1 if estado=="on" else 0
        rsp = c.write_register(REG_SAIDA_LUZ_VERDE, val, slave=MODBUS_UNIT_ID)
        if rsp.isError():
            raise Exception("Erro ao escrever luz verde")
    finally:
        c.close()

    return {"status":f"Tapete {'ligado' if estado=='on' else 'desligado'} com sucesso"}

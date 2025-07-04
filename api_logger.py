from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pymongo import MongoClient
from pymongo.collection import Collection
from datetime import datetime
from pydantic import BaseModel
from pymodbus.client import ModbusTcpClient
from fastapi.staticfiles import StaticFiles
import os

# ---------------- Configurações ----------------
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "ProdSenseBD"
FIELDLOGGER_IP = "192.168.0.30"
FIELDLOGGER_PORT = 502
MODBUS_UNIT_ID = 1


# ---------------- MongoDB ----------------
mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
collection_status: Collection = db["comunicacao_logger"]
collection_temp: Collection = db["temperatura_logger"]
collection_unidades: Collection = db["contador_unidades_logger"]
collection_velocidade: Collection = db["velocidade_logger"]

# ---------------- FastAPI ----------------
app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


# ---------------- Modelos ----------------
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

# ---------------- Endpoints ----------------

@app.get("/")
def pagina_html():
    return HTMLResponse(content=open("relay_control.html").read(), status_code=200)

@app.get("/status_logger")
def get_ultimo_status():
    ultimo = collection_status.find_one(sort=[("timestamp", -1)])
    if ultimo:
        return {"timestamp": ultimo["timestamp"], "status": ultimo["status"]}
    else:
        return JSONResponse(content={"error": "Sem dados encontrados"}, status_code=404)

@app.post("/status_logger")
def postar_status(dado: StatusEntrada):
    registro = {
        "timestamp": datetime.utcnow(),
        "status": dado.status
    }
    result = collection_status.insert_one(registro)

    # Corrigir o ObjectId antes de retornar
    registro["_id"] = str(result.inserted_id)

    return {"msg": "Status inserido com sucesso", "dados": registro}


@app.post("/temperatura_logger")
def postar_temperatura(dado: TemperaturaEntrada):
    registro = {"timestamp": datetime.utcnow(), "sensor": dado.sensor, "valor": dado.valor}
    result = collection_temp.insert_one(registro)

    # Converter o ObjectId para string
    registro["_id"] = str(result.inserted_id)

    return {"msg": "Temperatura inserida com sucesso", "dados": registro}


@app.post("/contador_unidades_logger")
def postar_contador(dado: ContadorEntrada):
    registro = {"timestamp": datetime.utcnow(), "sensor": dado.sensor, "valor": dado.valor}
    collection_unidades.insert_one(registro)
    return {"msg": "Contador inserido com sucesso", "dados": registro}


        
RELAY1_COIL_ADDRESS = 8  # Coil direto do Relé 1
RELAY2_COIL_ADDRESS = 9  # Coil do Relé 2 (humidificador)

@app.get("/ultima_temperatura")
def get_ultima_temperatura():
    ultimo = collection_temp.find_one(sort=[("timestamp", -1)])
    if ultimo:
        return {"timestamp": ultimo["timestamp"], "valor": ultimo["valor"]}
    else:
        return JSONResponse(content={"error": "Sem temperatura encontrada"}, status_code=404)
        
@app.get("/ultima_humidade")
def get_ultima_humidade():
    # Retorno temporário enquanto o sensor de humidade não está disponível
    return {"timestamp": datetime.utcnow(), "valor": 55.5, "observacao": "Valor simulado - sensor ainda não instalado"}

@app.post("/relay_temp/{state}")
def controlar_rele_temp(state: str):
    return controlar_rele_generico(state, RELAY1_COIL_ADDRESS, "Ventilador")

@app.post("/relay_hum/{state}")
def controlar_rele_hum(state: str):
    return controlar_rele_generico(state, RELAY2_COIL_ADDRESS, "Humidificador") 
    
@app.post("/relay/{state}")
def controlar_rele(state: str):
    if state not in ["on", "off"]:
        return JSONResponse(content={"error": "Estado inválido. Use 'on' ou 'off'"}, status_code=400)

    try:
        client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
        if not client.connect():
            raise Exception("Não foi possível conectar ao FieldLogger via Modbus")

        client.unit_id = MODBUS_UNIT_ID
        valor = True if state == "on" else False
        response = client.write_coil(RELAY1_COIL_ADDRESS, valor)

        if response.isError():
            raise Exception("Erro ao escrever no coil Modbus")

        return {"status": f"Ventilador {'ligado' if valor else 'desligado'} com sucesso"}

    except Exception as e:
        return JSONResponse(content={"error": f"Falha no controlo do relé: {str(e)}"}, status_code=500)

    finally:
        client.close()


def controlar_rele_generico(state: str, address: int, nome: str):
    if state not in ["on", "off"]:
        return JSONResponse(content={"error": "Estado inválido. Use 'on' ou 'off'"}, status_code=400)

    try:
        client = ModbusTcpClient(FIELDLOGGER_IP, port=FIELDLOGGER_PORT)
        if not client.connect():
            raise Exception("Não foi possível conectar ao FieldLogger via Modbus")

        client.unit_id = MODBUS_UNIT_ID
        valor = state == "on"
        response = client.write_coil(address, valor)

        if response.isError():
            raise Exception("Erro ao escrever no coil Modbus")

        return {"status": f"{nome} {'ligado' if valor else 'desligado'} com sucesso"}

    except Exception as e:
        return JSONResponse(content={"error": f"Falha no controlo do relé: {str(e)}"}, status_code=500)

    finally:
        client.close()

#------------------Velocidade------------------------
@app.post("/velocidade_logger")
def postar_velocidade(dado: VelocidadeEntrada):
    registro = {
        "timestamp": datetime.fromisoformat(dado.timestamp),
        "valor": float(dado.valor)  # garante que é float
    }
    result = collection_velocidade.insert_one(registro)
    registro["_id"] = str(result.inserted_id)
    return {"msg": "Velocidade inserida com sucesso", "dados": registro}


@app.get("/ultima_velocidade")
def get_ultima_velocidade():
    ultimo = collection_velocidade.find_one(sort=[("timestamp", -1)])
    if ultimo:
        return {"timestamp": ultimo["timestamp"], "valor": ultimo["valor"]}
    else:
        return JSONResponse(content={"error": "Sem velocidade encontrada"}, status_code=404)


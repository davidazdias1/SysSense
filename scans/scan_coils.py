from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.0.30", port=502)
client.unit_id = 1

if not client.connect():
    print("❌ Não foi possível conectar ao FieldLogger")
    input("Pressione Enter para sair...")
    exit()

print("🔎 Varredura de Coils (0–50)...")
for addr in range(0, 51):
    try:
        resposta = client.write_coil(addr, True)
        if not resposta.isError():
            print(f"[✓] Coil válido para escrita: {addr}")
        else:
            print(f"[ ] {addr}: Erro - Code {resposta.function_code}, Ex {resposta.exception_code}")
    except Exception as e:
        print(f"[ ] {addr}: Exceção - {e}")

client.close()
input("\n✅ Varredura concluída. Pressione Enter para sair...")

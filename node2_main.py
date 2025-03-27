# node2_main.py - Nodo receptor que recibe datos y responde
# Este archivo debería renombrarse a main.py en el dispositivo 2

import time
import json
from tbeam_optimized import TBeam

# Configuración del nodo
NODE_ID = "NODE2"
PEER_NODE = "NODE1"  # ID del nodo con el que nos comunicamos
FREQUENCY = 868.0    # MHz - Debe coincidir con el otro nodo
STATS_INTERVAL = 30000  # Mostrar estadísticas cada 30 segundos

# Variables para estadísticas
messages_received = 0
messages_sent = 0
sensor_history = []  # Almacena los últimos datos recibidos
MAX_HISTORY = 10     # Número máximo de lecturas a guardar

# Inicializar el nodo T-Beam
print(f"Iniciando nodo receptor {NODE_ID}...")
tbeam = TBeam(node_id=NODE_ID, frequency=FREQUENCY)
print("Nodo receptor inicializado!")

# LED patterns para comunicación visual
def status_led_pattern():
    # Patrón diferente al nodo 1 para distinguirlos
    for _ in range(2):
        tbeam._blink_led(times=2, delay=100)
        time.sleep_ms(200)

# Callback para procesar mensajes recibidos
def on_message_received(message):
    global messages_received, sensor_history
    
    src = message.get('src', 'DESCONOCIDO')
    msg_type = message.get('type', 'UNKNOWN')
    
    print(f"RECIBIDO [{msg_type}] DE {src}: {message}")
    
    # Incrementar contador
    messages_received += 1
    
    # Procesar según tipo de mensaje
    if msg_type == 'DATA' and src == PEER_NODE:
        # Extraer y guardar datos de sensor
        sensor_data = message.get('content', {})
        if sensor_data:
            # Añadir timestamp
            sensor_data['timestamp'] = time.ticks_ms()
            
            # Guardar en historial
            sensor_history.append(sensor_data)
            if len(sensor_history) > MAX_HISTORY:
                sensor_history.pop(0)  # Eliminar el más antiguo
            
            # Enviar confirmación
            send_response(src, message.get('id', 'UNKNOWN_ID'), sensor_data)
    
    elif msg_type == 'PING':
        # La biblioteca ya responde automáticamente con PONG
        print(f"Ping recibido de {src}")
    
    elif msg_type == 'ACK':
        print(f"Confirmación recibida para mensaje {message.get('ref_id')}")

# Envía una respuesta con procesamiento adicional
def send_response(destination, message_id, data):
    global messages_sent
    
    # Calcular algunos valores derivados como ejemplo
    response_data = {
        "ref_msg_id": message_id,
        "received_temp": data.get('temp', 0),
        "temp_status": "normal" if 18 <= data.get('temp', 20) <= 25 else "alerta",
        "node2_battery": tbeam.get_battery_voltage(),
        "processed_at": time.ticks_ms()
    }
    
    # Construir mensaje
    response = {
        "type": "RESPONSE",
        "dst": destination,
        "ref_id": message_id,
        "content": response_data
    }
    
    # Enviar respuesta
    success = tbeam.send_message(response)
    
    if success:
        messages_sent += 1
        print(f"Respuesta enviada a {destination}. Total enviadas: {messages_sent}")
    else:
        print(f"Error al enviar respuesta a {destination}")

# Muestra estadísticas de funcionamiento
def show_stats():
    print("\n--- ESTADÍSTICAS DEL RECEPTOR ---")
    print(f"Mensajes recibidos: {messages_received}")
    print(f"Respuestas enviadas: {messages_sent}")
    print(f"Voltaje de batería: {tbeam.get_battery_voltage():.2f}V")
    
    # Mostrar último dato recibido
    if sensor_history:
        last_data = sensor_history[-1]
        print("\nÚltima lectura recibida:")
        for key, value in last_data.items():
            print(f"  {key}: {value}")
    
    # Mostrar configuración LoRa actual
    lora_config = tbeam.get_config()
    print("\nConfiguración LoRa actual:")
    print(f"  Frecuencia: {lora_config.get('frequency', 'N/A')} MHz")
    print(f"  Factor de dispersión: {lora_config.get('spreading_factor', 'N/A')}")
    print(f"  Ancho de banda: {lora_config.get('bandwidth', 'N/A')} Hz")
    print("--------------------------------\n")

# Configurar callback
tbeam.set_message_callback(on_message_received)

# Bucle principal
print("Iniciando bucle principal del receptor...")
status_led_pattern()  # Indicar inicio de operación

# Enviar un ping inicial para anunciar presencia
tbeam.send_ping(PEER_NODE)

last_stats_time = time.ticks_ms()

try:
    while True:
        current_time = time.ticks_ms()
        
        # Mostrar estadísticas periódicamente
        if time.ticks_diff(current_time, last_stats_time) > STATS_INTERVAL:
            show_stats()
            last_stats_time = current_time
        
        # Procesar mensajes entrantes durante un tiempo
        tbeam.process_messages(timeout_ms=1000)
        
        # Pequeña pausa para permitir que otras tareas se ejecuten
        time.sleep_ms(100)
        
except KeyboardInterrupt:
    print("Programa detenido por usuario")
    
except Exception as e:
    print(f"Error: {e}")
    import sys
    sys.print_exception(e)
    
finally:
    # Poner en standby antes de terminar
    print("Finalizando receptor...")
    tbeam.standby()
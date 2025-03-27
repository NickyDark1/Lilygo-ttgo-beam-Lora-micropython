# node1_main.py - Nodo emisor que envía datos periódicamente
# Este archivo debería renombrarse a main.py en el dispositivo 1

import time
import json
from tbeam_optimized import TBeam
import urandom # Para generar datos de ejemplo

# Configuración del nodo
NODE_ID = "NODE1"
DESTINATION_ID = "NODE2"
FREQUENCY = 868.0  # MHz - Ajustar según regulaciones locales
SEND_INTERVAL = 10000  # Intervalo de envío en ms (10 segundos)

# Variables globales para estadísticas
messages_sent = 0
messages_received = 0
last_received_data = None

# Inicializar el nodo T-Beam
print(f"Iniciando nodo {NODE_ID}...")
tbeam = TBeam(node_id=NODE_ID, frequency=FREQUENCY)
print("Nodo inicializado!")

# LED patterns para comunicación visual
def status_led_pattern():
    for _ in range(3):
        tbeam._blink_led(times=1, delay=50)
        time.sleep_ms(100)

# Callback para procesar mensajes recibidos
def on_message_received(message):
    global messages_received, last_received_data
    
    print(f"RECIBIDO DE {message.get('src', 'DESCONOCIDO')}: {message}")
    
    # Incrementar contador de mensajes
    messages_received += 1
    
    # Guardar datos si es mensaje de tipo DATA
    if message.get('type') == 'DATA':
        last_received_data = message.get('content')
        print(f"Datos recibidos: {last_received_data}")
        
        # Confirmar recepción enviando ACK
        send_ack(message.get('src'), message.get('id', 'UNKNOWN_ID'))
    
    # Si es un ACK, solo mostrar
    elif message.get('type') == 'ACK':
        print(f"Confirmación recibida para mensaje {message.get('ref_id')}")
    
    # Si es un PING, ya responde automáticamente la biblioteca

# Enviar confirmación de recepción
def send_ack(destination, message_id):
    ack_message = {
        "type": "ACK",
        "dst": destination,
        "ref_id": message_id,
        "content": {
            "received_at": time.ticks_ms(),
            "status": "OK"
        }
    }
    tbeam.send_message(ack_message)

# Generar datos de sensor simulados para enviar
def generate_sensor_data():
    return {
        "temp": 20 + (urandom.getrandbits(4) / 10),  # Temperatura entre 20-21.5°C
        "humidity": 40 + urandom.getrandbits(6),     # Humedad entre 40-103%
        "pressure": 1013 + urandom.getrandbits(4),   # Presión entre 1013-1027 hPa
        "battery": tbeam.get_battery_voltage(),      # Voltaje real de la batería
        "uptime": time.ticks_ms() // 1000            # Tiempo de funcionamiento en segundos
    }

# Enviar datos a otro nodo
def send_sensor_data(destination=DESTINATION_ID):
    global messages_sent
    
    # Generar datos de sensor
    sensor_data = generate_sensor_data()
    
    # Construir mensaje
    print(f"Enviando datos a {destination}...")
    success = tbeam.send_data(sensor_data, destination)
    
    if success:
        messages_sent += 1
        print(f"Datos enviados correctamente. Total enviados: {messages_sent}")
    else:
        print("Error al enviar datos")
    
    return success

# Mostrar estadísticas
def show_stats():
    print("\n--- ESTADÍSTICAS ---")
    print(f"Mensajes enviados: {messages_sent}")
    print(f"Mensajes recibidos: {messages_received}")
    print(f"Último dato recibido: {last_received_data}")
    print(f"Voltaje de batería: {tbeam.get_battery_voltage():.2f}V")
    print("-------------------\n")

# Configurar callback
tbeam.set_message_callback(on_message_received)

# Bucle principal
print("Iniciando bucle principal...")
status_led_pattern()  # Indicar inicio de operación

last_send_time = 0

try:
    # Enviar un ping inicial para anunciar presencia
    tbeam.send_ping(DESTINATION_ID)
    
    while True:
        current_time = time.ticks_ms()
        
        # Enviar datos periódicamente
        if time.ticks_diff(current_time, last_send_time) > SEND_INTERVAL:
            send_sensor_data()
            last_send_time = current_time
            show_stats()
        
        # Pequeña pausa para no saturar la CPU
        time.sleep_ms(100)
        
except KeyboardInterrupt:
    print("Programa detenido por usuario")
    
except Exception as e:
    print(f"Error: {e}")
    
finally:
    # Poner en standby antes de terminar
    print("Finalizando...")
    tbeam.standby()
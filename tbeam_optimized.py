# tbeam_optimized.py - Clase auxiliar optimizada para TTGO T-Beam con LoRa
from machine import Pin, SPI, ADC, deepsleep
import time
import json
import gc
from lora_optimized import LoRa, PAConfig

class TBeam:
    """Clase optimizada para gestionar el TTGO T-Beam con LoRa"""
    
    # Pines específicos para TTGO T-Beam V1.2
    PIN_LORA_SCK = 5
    PIN_LORA_MOSI = 27
    PIN_LORA_MISO = 19
    PIN_LORA_CS = 18
    PIN_LORA_DIO = 26
    PIN_LORA_RST = 23
    
    # Pines de LED
    PIN_LED1 = 25  # LED1 - Indicador de actividad
    
    # Pin para medir voltaje de batería (si está disponible)
    PIN_BAT_VOLTAGE = 2  # ADC para medir voltaje de batería
    
    def __init__(self, node_id="TBEAM", frequency=868.0):
        """
        Inicializa el T-Beam con LoRa
        
        Args:
            node_id: Identificador único del nodo
            frequency: Frecuencia en MHz (por defecto 868.0)
        """
        self.node_id = node_id
        self.message_counter = 0
        self.received_messages = []
        self.message_callback = None
        self.last_send_time = 0
        
        # Configurar LED
        self.led = Pin(self.PIN_LED1, Pin.OUT)
        self.led.value(0)
        
        # Configurar medición de batería
        try:
            self.battery_adc = ADC(Pin(self.PIN_BAT_VOLTAGE))
            self.battery_adc.atten(ADC.ATTN_11DB)  # Rango completo: 3.3V
        except Exception as e:
            print(f"Error al configurar ADC de batería: {e}")
            self.battery_adc = None
        
        # Inicializar SPI para LoRa
        self._init_lora(frequency)
        
        print(f"T-Beam inicializado. ID: {self.node_id}, Frecuencia: {frequency} MHz")
    
    def _init_lora(self, frequency):
        """
        Inicializa el módulo LoRa
        
        Args:
            frequency: Frecuencia en MHz
        """
        # Configurar SPI
        self.spi = SPI(
            1,
            baudrate=10000000,
            polarity=0,
            phase=0,
            sck=Pin(self.PIN_LORA_SCK, Pin.OUT),
            mosi=Pin(self.PIN_LORA_MOSI, Pin.OUT),
            miso=Pin(self.PIN_LORA_MISO, Pin.IN),
        )
        self.spi.init()
        
        # Resetear el módulo LoRa
        reset_pin = Pin(self.PIN_LORA_RST, Pin.OUT)
        reset_pin.value(0)
        time.sleep_ms(100)
        reset_pin.value(1)
        time.sleep_ms(100)
        
        # Intentar inicializar LoRa con manejo de excepciones
        try:
            # Configurar LoRa utilizando la nueva biblioteca optimizada
            self.lora = LoRa(
                self.spi,
                cs=Pin(self.PIN_LORA_CS, Pin.OUT),
                rx=Pin(self.PIN_LORA_DIO, Pin.IN),
                frequency=frequency,
                bandwidth=125000,
                spreading_factor=10,
                coding_rate=5,
                tx_power=20,
                preamble_length=8,
                crc=True,
                output_pin=PAConfig.BOOST_PIN
            )
            
            # Configurar callback para recepción
            self.lora.on_recv(self._on_message_received)
            
            # Iniciar en modo recepción
            self.lora.recv()
            print("LoRa inicializado correctamente")
        except Exception as e:
            print(f"Error al inicializar LoRa: {e}")
            print("Intentando con parámetros alternativos...")
            try:
                # Segundo intento con parámetros diferentes
                self.lora = LoRa(
                    self.spi,
                    cs=Pin(self.PIN_LORA_CS, Pin.OUT),
                    rx=Pin(self.PIN_LORA_DIO, Pin.IN),
                    frequency=frequency,
                    bandwidth=250000,  # Valores diferentes
                    spreading_factor=7,
                    coding_rate=5,
                    tx_power=17,
                    preamble_length=8,
                    output_pin=PAConfig.BOOST_PIN
                )
                self.lora.on_recv(self._on_message_received)
                self.lora.recv()
                print("LoRa inicializado con parámetros alternativos")
            except Exception as e2:
                print(f"Error en el segundo intento: {e2}")
                raise Exception("No se pudo inicializar el módulo LoRa")
    
    def _on_message_received(self, data):
        """
        Callback interno para manejar mensajes recibidos
        
        Args:
            data: Datos recibidos (bytes)
        """
        # Indicar recepción con LED
        self._blink_led()
        
        try:
            # Decodificar mensaje
            message_str = data.decode('utf-8')
            
            try:
                # Intentar parsear como JSON
                message = json.loads(message_str)
                
                # Añadir RSSI y timestamp
                message["rssi"] = self.lora.get_rssi()
                message["snr"] = self.lora.get_snr()
                message["received_at"] = time.ticks_ms()
                
                # Guardar mensaje
                self._add_to_message_buffer(message)
                
                # Procesar según destinatario
                if message.get("dst") == self.node_id or message.get("dst") == "BROADCAST":
                    # Mensaje dirigido a este nodo
                    print(f"Mensaje para este nodo: {message}")
                    
                    # Responder a PING automáticamente
                    if message.get("type") == "PING":
                        self._send_pong(message.get("src"))
                    
                    # Llamar al callback externo si existe
                    if self.message_callback:
                        self.message_callback(message)
                
            except ValueError:
                # No es JSON, tratar como texto plano
                plain_message = {
                    "type": "TEXT",
                    "src": "UNKNOWN",
                    "dst": self.node_id,
                    "content": message_str,
                    "rssi": self.lora.get_rssi(),
                    "received_at": time.ticks_ms()
                }
                
                self._add_to_message_buffer(plain_message)
                
                # Llamar al callback externo si existe
                if self.message_callback:
                    self.message_callback(plain_message)
            
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
        
        # Volver a modo recepción
        self.lora.recv()
    
    def _add_to_message_buffer(self, message, max_buffer=20):
        """
        Añade un mensaje al buffer, limitando el tamaño
        
        Args:
            message: Mensaje a añadir
            max_buffer: Tamaño máximo del buffer
        """
        if len(self.received_messages) >= max_buffer:
            self.received_messages.pop(0)  # Eliminar el más antiguo
        self.received_messages.append(message)
    
    def _send_pong(self, destination):
        """
        Responde automáticamente a un PING
        
        Args:
            destination: Destinatario del mensaje PONG
        """
        response = {
            "type": "PONG",
            "src": self.node_id,
            "dst": destination,
            "content": {"time": time.ticks_ms()},
            "id": self._get_next_message_id()
        }
        
        # Pequeña pausa para asegurar que el otro nodo esté listo para recibir
        time.sleep_ms(500)
        
        # Enviar respuesta
        self.send_message(json.dumps(response))
    
    def _get_next_message_id(self):
        """
        Genera un nuevo ID para mensajes
        
        Returns:
            str: ID único para el mensaje
        """
        self.message_counter += 1
        return f"{self.node_id}_{self.message_counter}"
    
    def _blink_led(self, times=1, delay=100):
        """
        Parpadea el LED el número de veces especificado
        
        Args:
            times: Número de parpadeos
            delay: Retardo entre parpadeos en ms
        """
        for _ in range(times):
            self.led.value(1)
            time.sleep_ms(delay)
            self.led.value(0)
            time.sleep_ms(delay)
    
    def send_message(self, message, blink=True):
        """
        Envía un mensaje por LoRa
        
        Args:
            message: Mensaje a enviar (str o dict)
            blink: Indicar envío con LED
            
        Returns:
            bool: True si el envío fue exitoso
        """
        # Si es un diccionario, convertir a JSON
        if isinstance(message, dict):
            # Asegurar que tenga los campos básicos
            if "src" not in message:
                message["src"] = self.node_id
            if "id" not in message:
                message["id"] = self._get_next_message_id()
            
            message_str = json.dumps(message)
        else:
            message_str = message
        
        # Registrar tiempo de envío
        self.last_send_time = time.ticks_ms()
        
        # Enviar
        print(f"Enviando: {message_str}")
        result = self.lora.send(message_str)
        
        # Indicar con LED
        if blink and result:
            self._blink_led(2)
        
        # Volver a modo recepción
        self.lora.recv()
        
        return result
    
    def send_ping(self, destination="BROADCAST"):
        """
        Envía un mensaje PING
        
        Args:
            destination: Destinatario del PING
            
        Returns:
            bool: True si el envío fue exitoso
        """
        ping = {
            "type": "PING",
            "src": self.node_id,
            "dst": destination,
            "content": {"time": time.ticks_ms()},
            "id": self._get_next_message_id()
        }
        
        return self.send_message(ping)
    
    def send_data(self, data, destination="BROADCAST"):
        """
        Envía datos en formato estructurado
        
        Args:
            data: Datos a enviar
            destination: Destinatario del mensaje
            
        Returns:
            bool: True si el envío fue exitoso
        """
        message = {
            "type": "DATA",
            "src": self.node_id,
            "dst": destination,
            "content": data,
            "id": self._get_next_message_id()
        }
        
        return self.send_message(message)
    
    def get_battery_voltage(self):
        """
        Lee el voltaje de la batería (si está disponible)
        
        Returns:
            float: Voltaje de la batería en voltios
        """
        if not self.battery_adc:
            return 0.0
            
        try:
            raw = self.battery_adc.read()
            # Convertir lectura a voltaje (ajustar divisor según tu hardware)
            voltage = raw * 3.3 * 2 / 4095  # Ajustar según el divisor de voltaje
            return voltage
        except Exception as e:
            print(f"Error al leer voltaje de batería: {e}")
            return 0.0
    
    def set_message_callback(self, callback):
        """
        Establece un callback para procesar mensajes
        
        Args:
            callback: Función de callback que recibe un mensaje como parámetro
        """
        self.message_callback = callback
    
    def sleep(self, duration_ms=0):
        """
        Pone el dispositivo en modo de bajo consumo
        
        Args:
            duration_ms: Duración del sleep en ms (0 para sleep sin timeout)
        """
        # Apagar LED
        self.led.value(0)
        
        # Poner LoRa en modo sleep
        self.lora.sleep()
        
        # Si se especifica duración, usar deepsleep
        if duration_ms > 0:
            deepsleep(duration_ms)
    
    def standby(self):
        """Pone el LoRa en modo standby (bajo consumo pero rápido reinicio)"""
        self.lora.standby()
    
    def wake(self):
        """Despierta el módulo LoRa y vuelve a modo recepción"""
        self.lora.recv()
        self.led.value(1)  # Indicar que está activo
    
    def get_messages(self, clear=False):
        """
        Obtiene los mensajes recibidos
        
        Args:
            clear: Si es True, limpia el buffer de mensajes
            
        Returns:
            list: Lista de mensajes recibidos
        """
        messages = self.received_messages.copy()
        if clear:
            self.received_messages = []
        return messages
    
    def clear_messages(self):
        """Limpia el buffer de mensajes"""
        self.received_messages = []
    
    def get_config(self):
        """
        Obtiene la configuración actual del módulo LoRa
        
        Returns:
            dict: Configuración actual
        """
        return self.lora.get_config()
    
    def set_lora_param(self, param, value):
        """
        Modifica un parámetro de configuración del LoRa
        
        Args:
            param: Nombre del parámetro (frequency, bandwidth, etc.)
            value: Nuevo valor
            
        Returns:
            bool: True si se pudo cambiar el parámetro
        """
        try:
            # Obtener el método setter correspondiente
            setter_method = getattr(self.lora, f"set_{param}", None)
            
            if setter_method and callable(setter_method):
                # Poner en modo standby para configuración
                self.lora.standby()
                
                # Aplicar el cambio
                setter_method(value)
                
                # Volver a modo recepción
                self.lora.recv()
                return True
            else:
                print(f"Parámetro '{param}' no soportado")
                return False
                
        except Exception as e:
            print(f"Error al cambiar parámetro '{param}': {e}")
            # Asegurar que volvemos a modo recepción
            self.lora.recv()
            return False
            
    def process_messages(self, timeout_ms=1000):
        """
        Procesa mensajes entrantes durante un tiempo determinado
        
        Args:
            timeout_ms: Tiempo máximo de espera en ms
            
        Returns:
            int: Número de mensajes procesados
        """
        count = 0
        start_time = time.ticks_ms()
        
        # Estar atento a mensajes por un tiempo
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            # Permitir procesamiento de otros temas
            time.sleep_ms(10)
            
            # Contar mensajes procesados
            if len(self.received_messages) > count:
                count = len(self.received_messages)
                
        return count


# Ejemplo de uso
if __name__ == "__main__":
    # Crear un nodo T-Beam
    tbeam = TBeam(node_id="NODO1", frequency=868.0)
    
    # Definir un callback para mensajes recibidos
    def on_message(message):
        print(f"Mensaje recibido: {message}")
        
        # Responder si es un mensaje de texto
        if message["type"] == "TEXT":
            tbeam.send_message({
                "type": "TEXT",
                "dst": message["src"],
                "content": f"Respuesta automática de {tbeam.node_id}"
            })
    
    # Configurar el callback
    tbeam.set_message_callback(on_message)
    
    # Enviar un ping de prueba
    tbeam.send_ping()
    
    # Ciclo principal - enviar datos de batería cada 60 segundos
    try:
        while True:
            # Leer voltaje de batería
            voltage = tbeam.get_battery_voltage()
            
            # Enviar datos
            tbeam.send_data({
                "battery": voltage,
                "uptime": time.ticks_ms() // 1000
            })
            
            # Esperar procesando mensajes entrantes
            tbeam.process_messages(timeout_ms=60000)
            
    except KeyboardInterrupt:
        print("Programa detenido")
        
    finally:
        # Poner en modo sleep al salir
        tbeam.sleep()
# lora_optimized.py - Biblioteca LoRa optimizada para ESP32 TTGO T-Beam
import gc
from machine import Pin
import time
from micropython import const

# Constantes agrupadas por categoría
class Registers:
    """Registros del SX127x"""
    FIFO = const(0x00)
    OP_MODE = const(0x01)
    FRF_MSB = const(0x06)
    FRF_MID = const(0x07)
    FRF_LSB = const(0x08)
    PA_CONFIG = const(0x09)
    LNA = const(0x0c)
    FIFO_ADDR_PTR = const(0x0d)
    FIFO_TX_BASE_ADDR = const(0x0e)
    FIFO_RX_BASE_ADDR = const(0x0f)
    FIFO_RX_CURRENT_ADDR = const(0x10)
    IRQ_FLAGS = const(0x12)
    RX_NB_BYTES = const(0x13)
    PKT_RSSI_VALUE = const(0x1a)
    PKT_SNR_VALUE = const(0x1b)
    MODEM_CONFIG_1 = const(0x1d)
    MODEM_CONFIG_2 = const(0x1e)
    PREAMBLE_MSB = const(0x20)
    PREAMBLE_LSB = const(0x21)
    PAYLOAD_LENGTH = const(0x22)
    MODEM_CONFIG_3 = const(0x26)
    DETECTION_OPTIMIZE = const(0x31)
    DETECTION_THRESHOLD = const(0x37)
    SYNC_WORD = const(0x39)
    DIO_MAPPING_1 = const(0x40)
    VERSION = const(0x42)
    PA_DAC = const(0x4D)

class Modes:
    """Modos de operación"""
    SLEEP = const(0x00)
    STDBY = const(0x01)
    TX = const(0x03)
    RX_CONTINUOUS = const(0x05)
    LORA_MASK = const(0x80)

class IRQFlags:
    """Flags de interrupción"""
    TX_DONE = const(0x08)
    PAYLOAD_CRC_ERROR = const(0x20)
    RX_DONE = const(0x40)

class PAConfig:
    """Configuración del amplificador de potencia"""
    RFO_PIN = const(0)
    BOOST_PIN = const(1)
    PA_BOOST = const(0x80)

class Config:
    """Valores por defecto y límites de configuración"""
    MAX_PKT_LENGTH = const(255)
    TX_BASE_ADDR = const(0x00)
    RX_BASE_ADDR = const(0x00)
    SX127X_VERSION = const(0x12)
    
    # Valores por defecto
    DEFAULT = {
        'frequency': 915.0,
        'bandwidth': 250000,
        'spreading_factor': 10,
        'coding_rate': 5,
        'preamble_length': 8,
        'tx_power': 17,
        'crc': False,
        'implicit': False,
        'sync_word': 0x12,
        'output_pin': PAConfig.BOOST_PIN
    }
    
    # Bandwidths soportados en Hz
    BANDWIDTHS = (7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000)

class LoRa:
    """
    Clase optimizada para controlar módulos LoRa basados en SX127x.
    Compatible con ESP32 y MicroPython.
    """

    def __init__(self, spi, **kwargs):
        """
        Inicializa el módulo LoRa con la configuración especificada.
        
        Args:
            spi: Objeto SPI para comunicación
            cs: Pin de selección del chip (requerido)
            rx: Pin de recepción DIO0 (opcional)
            frequency: Frecuencia en MHz (default: 915.0)
            bandwidth: Ancho de banda en Hz (default: 250000)
            spreading_factor: Factor de dispersión 7-12 (default: 10)
            coding_rate: Tasa de codificación 5-8 (default: 5)
            preamble_length: Longitud del preámbulo (default: 8)
            tx_power: Potencia de transmisión en dBm (default: 17)
            crc: Usar CRC (default: False)
            implicit: Modo implícito vs explícito (default: False)
            sync_word: Palabra de sincronización (default: 0x12)
        """
        if 'cs' not in kwargs:
            raise ValueError('Se requiere el pin CS para la comunicación SPI')
            
        # Configuración de hardware
        self.spi = spi
        self.cs = kwargs['cs']
        self.rx = kwargs.get('rx', None)
        
        # Almacenar configuración
        self._config = {}
        self._init_config(kwargs)
        
        # Verificar comunicación con el chip
        self._verify_chip_version()
        
        # Poner en modo sleep para configuración
        self._set_mode(Modes.SLEEP)
        
        # Aplicar configuración
        self._configure_radio()
        
        # Volver a modo standby
        self.standby()
        
        # Callback para recepción
        self._on_recv = None
    
    def _init_config(self, kwargs):
        """
        Inicializa la configuración con valores por defecto y sobrescribe con los proporcionados.
        
        Args:
            kwargs: Parámetros de configuración proporcionados
        """
        # Copiar valores por defecto
        for key, value in Config.DEFAULT.items():
            self._config[key] = kwargs.get(key, value)
    
    def _verify_chip_version(self):
        """
        Verifica la versión del chip SX127x.
        Sigue intentando hasta 5 veces si falla inicialmente.
        """
        version = self._read(Registers.VERSION)
        attempts = 0
        
        while version != Config.SX127X_VERSION and attempts < 5:
            time.sleep_ms(100)
            version = self._read(Registers.VERSION)
            print(f"Versión leída: {hex(version)}")
            attempts += 1
            
        if version != Config.SX127X_VERSION:
            print(f"Advertencia: Versión del chip {hex(version)} no es {hex(Config.SX127X_VERSION)}")
            print("Continuando de todos modos...")
    
    def _configure_radio(self):
        """Aplica toda la configuración inicial al radio."""
        # Configurar direcciones base para transmisión/recepción
        self._write(Registers.FIFO_TX_BASE_ADDR, Config.TX_BASE_ADDR)
        self._write(Registers.FIFO_RX_BASE_ADDR, Config.RX_BASE_ADDR)
        
        # Aplicar parámetros de configuración
        self.set_frequency(self._config['frequency'])
        self.set_bandwidth(self._config['bandwidth'])
        self.set_spreading_factor(self._config['spreading_factor'])
        self.set_coding_rate(self._config['coding_rate'])
        self.set_preamble_length(self._config['preamble_length'])
        self.set_crc(self._config['crc'])
        self.set_sync_word(self._config['sync_word'])
        self.set_implicit(self._config['implicit'])
        
        # Configuración del amplificador y LNA
        self._write(Registers.LNA, self._read(Registers.LNA) | 0x03)  # LNA boost
        self._write(Registers.MODEM_CONFIG_3, 0x04)  # AGC automático
        
        # Configuración de potencia
        self.set_tx_power(self._config['tx_power'], self._config['output_pin'])
    
    def _set_mode(self, mode):
        """
        Establece el modo de operación del módulo.
        
        Args:
            mode: Modo de operación (desde la clase Modes)
        """
        self._write(Registers.OP_MODE, Modes.LORA_MASK | mode)
    
    def standby(self):
        """Pone el módulo en modo standby (bajo consumo pero inicio rápido)."""
        self._set_mode(Modes.STDBY)

    def sleep(self):
        """Pone el módulo en modo sleep (mínimo consumo)."""
        self._set_mode(Modes.SLEEP)
    
    def recv(self):
        """Pone el módulo en modo de recepción continua."""
        self._set_mode(Modes.RX_CONTINUOUS)
    
    #
    # Métodos de configuración
    #
    def set_frequency(self, frequency):
        """
        Configura la frecuencia de operación.
        
        Args:
            frequency: Frecuencia en MHz (433, 868, 915, etc.)
        """
        self._config['frequency'] = frequency
        
        # Convertir frecuencia a valor de registro
        frf = int(frequency * 1000000.0 / 61.03515625)
        
        # Escribir en los tres registros
        self._write(Registers.FRF_MSB, (frf >> 16) & 0xff)
        self._write(Registers.FRF_MID, (frf >> 8) & 0xff)
        self._write(Registers.FRF_LSB, frf & 0xff)

    def set_bandwidth(self, bw):
        """
        Configura el ancho de banda.
        
        Args:
            bw: Ancho de banda en Hz (7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000)
        """
        self._config['bandwidth'] = bw
        
        # Encontrar el índice del ancho de banda más cercano
        bw_index = 9  # Valor por defecto si no coincide
        
        for i, bandwidth in enumerate(Config.BANDWIDTHS):
            if bw <= bandwidth:
                bw_index = i
                break
        
        # Configurar en registro
        reg_value = self._read(Registers.MODEM_CONFIG_1) & 0x0f
        self._write(Registers.MODEM_CONFIG_1, reg_value | (bw_index << 4))
        
        # Actualizar configuración si SF > 10 y BW < 250kHz
        sf = self._config.get('spreading_factor', 10)
        if sf > 10 and bw < 250000:
            self._write(Registers.MODEM_CONFIG_3, 0x08)  # LNA automático activado
        else:
            self._write(Registers.MODEM_CONFIG_3, 0x04)  # Solo AGC automático

    def set_spreading_factor(self, sf):
        """
        Configura el factor de dispersión.
        
        Args:
            sf: Factor de dispersión (6-12)
        """
        if sf < 6 or sf > 12:
            raise ValueError('Factor de dispersión debe estar entre 6-12')
            
        self._config['spreading_factor'] = sf
        
        # Optimizaciones para SF6
        self._write(Registers.DETECTION_OPTIMIZE, 0xc5 if sf == 6 else 0xc3)
        self._write(Registers.DETECTION_THRESHOLD, 0x0c if sf == 6 else 0x0a)
        
        # Configurar SF en REG_MODEM_CONFIG_2
        reg2 = self._read(Registers.MODEM_CONFIG_2)
        self._write(Registers.MODEM_CONFIG_2, (reg2 & 0x0f) | ((sf << 4) & 0xf0))
        
        # Actualizar configuración de LNA si es necesario
        bw = self._config.get('bandwidth', 250000)
        if sf > 10 and bw < 250000:
            self._write(Registers.MODEM_CONFIG_3, 0x08)
        else:
            self._write(Registers.MODEM_CONFIG_3, 0x04)

    def set_coding_rate(self, denom):
        """
        Configura la tasa de codificación (4/denom).
        
        Args:
            denom: Denominador (5-8 para tasas 4/5 hasta 4/8)
        """
        denom = min(max(denom, 5), 8)
        self._config['coding_rate'] = denom
        
        cr = denom - 4
        reg1 = self._read(Registers.MODEM_CONFIG_1)
        self._write(Registers.MODEM_CONFIG_1, (reg1 & 0xf1) | (cr << 1))

    def set_preamble_length(self, length):
        """
        Configura la longitud del preámbulo.
        
        Args:
            length: Longitud del preámbulo (6-65535)
        """
        length = max(6, min(length, 65535))
        self._config['preamble_length'] = length
        
        self._write(Registers.PREAMBLE_MSB, (length >> 8) & 0xff)
        self._write(Registers.PREAMBLE_LSB, length & 0xff)

    def set_crc(self, crc=True):
        """
        Activa o desactiva la verificación CRC.
        
        Args:
            crc: True para activar CRC, False para desactivar
        """
        self._config['crc'] = crc
        
        reg = self._read(Registers.MODEM_CONFIG_2)
        if crc:
            reg |= 0x04
        else:
            reg &= 0xfb
        self._write(Registers.MODEM_CONFIG_2, reg)

    def set_sync_word(self, sw):
        """
        Configura la palabra de sincronización.
        
        Args:
            sw: Palabra de sincronización (1 byte, 0x12 por defecto, 0x34 para LoRaWAN)
        """
        self._config['sync_word'] = sw
        self._write(Registers.SYNC_WORD, sw)

    def set_implicit(self, implicit=False):
        """
        Configura el modo de encabezado (implícito o explícito).
        
        Args:
            implicit: True para modo implícito, False para explícito
        """
        self._config['implicit'] = implicit
        
        reg = self._read(Registers.MODEM_CONFIG_1)
        if implicit:
            reg |= 0x01
        else:
            reg &= 0xfe
        self._write(Registers.MODEM_CONFIG_1, reg)

    def set_tx_power(self, level, output_pin=PAConfig.BOOST_PIN):
        """
        Configura la potencia de transmisión.
        
        Args:
            level: Nivel de potencia en dBm (0-14 para RFO, 2-20 para PA_BOOST)
            output_pin: Pin de salida (PAConfig.RFO_PIN o PAConfig.BOOST_PIN)
        """
        self._config['tx_power'] = level
        self._config['output_pin'] = output_pin
        
        if output_pin == PAConfig.RFO_PIN:
            # RFO pin: potencia limitada a 14 dBm
            level = min(max(level, 0), 14)
            self._write(Registers.PA_CONFIG, 0x70 | level)
        else:
            # PA_BOOST pin: potencia hasta 20 dBm
            if level > 17:
                # Activar DAC de alta potencia para +20 dBm
                if level > 19:
                    self._write(Registers.PA_DAC, self._read(Registers.PA_DAC) | 0x07)
                else:
                    self._write(Registers.PA_DAC, (self._read(Registers.PA_DAC) & ~0x07) | 0x04)
                
                level = 15  # Valor fijo para PA_DAC activado
            else:
                # Desactivar DAC de alta potencia
                self._write(Registers.PA_DAC, self._read(Registers.PA_DAC) & ~0x07)
                level = level - 2  # Ajuste para mapear 2-17 dBm a 0-15
            
            self._write(Registers.PA_CONFIG, PAConfig.PA_BOOST | level)
    
    #
    # Métodos de transmisión
    #
    def begin_packet(self):
        """Inicia un nuevo paquete para transmisión."""
        self.standby()
        self._write(Registers.FIFO_ADDR_PTR, Config.TX_BASE_ADDR)
        self._write(Registers.PAYLOAD_LENGTH, 0)

    def write_packet(self, data):
        """
        Escribe datos en el paquete actual.
        
        Args:
            data: Bytes o cadena a escribir
            
        Returns:
            int: Número de bytes escritos
        """
        if isinstance(data, str):
            data = data.encode()
            
        # Verificar espacio disponible
        current_length = self._read(Registers.PAYLOAD_LENGTH)
        new_length = current_length + len(data)
        
        if new_length > Config.MAX_PKT_LENGTH:
            raise ValueError(f'La longitud máxima del paquete es {Config.MAX_PKT_LENGTH} bytes')
        
        # Escribir datos al FIFO
        for byte in data:
            self._write(Registers.FIFO, byte)
        
        # Actualizar longitud
        self._write(Registers.PAYLOAD_LENGTH, new_length)
        return len(data)

    def end_packet(self, timeout=5000):
        """
        Finaliza y transmite el paquete.
        
        Args:
            timeout: Tiempo máximo de espera en ms para la transmisión
            
        Returns:
            bool: True si el paquete se envió correctamente
        """
        # Iniciar transmisión
        self._set_mode(Modes.TX)
        
        # Esperar a que finalice la transmisión
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout:
            if self._read(Registers.IRQ_FLAGS) & IRQFlags.TX_DONE:
                # Limpiar flag de transmisión completada
                self._write(Registers.IRQ_FLAGS, IRQFlags.TX_DONE)
                gc.collect()
                return True
            time.sleep_ms(10)
        
        return False

    def send(self, data, timeout=5000):
        """
        Envía datos completos en un solo paquete.
        
        Args:
            data: Datos a enviar (bytes o cadena)
            timeout: Tiempo máximo de espera en ms
            
        Returns:
            bool: True si se envió correctamente
        """
        self.begin_packet()
        self.write_packet(data)
        return self.end_packet(timeout)

    #
    # Métodos de recepción
    #
    def on_recv(self, callback):
        """
        Configura un callback para cuando se reciban datos.
        
        Args:
            callback: Función a llamar cuando se reciban datos
        """
        self._on_recv = callback
        
        if self.rx:
            if callback:
                self._write(Registers.DIO_MAPPING_1, 0x00)  # DIO0 = RxDone
                self.rx.irq(handler=self._irq_handler, trigger=Pin.IRQ_RISING)
            else:
                self.rx.irq(handler=None, trigger=0)

    def _irq_handler(self, pin):
        """
        Manejador de interrupciones para recepción de datos.
        
        Args:
            pin: Pin que generó la interrupción
        """
        # Leer y limpiar flags
        irq_flags = self._read(Registers.IRQ_FLAGS)
        self._write(Registers.IRQ_FLAGS, irq_flags)
        
        # Verificar si hay datos recibidos sin error CRC
        if (irq_flags & IRQFlags.RX_DONE) and not (irq_flags & IRQFlags.PAYLOAD_CRC_ERROR):
            payload = self._read_payload()
            if self._on_recv:
                self._on_recv(payload)

    def receive_message(self, timeout=0):
        """
        Configura el módulo para recepción y espera un mensaje.
        
        Args:
            timeout: Tiempo máximo de espera en ms (0 para esperar indefinidamente)
            
        Returns:
            bytes or None: Mensaje recibido o None si se agotó el tiempo
        """
        # Poner en modo recepción
        self.recv()
        
        # Esperar a recibir o a que se agote el tiempo
        start_time = time.ticks_ms()
        while timeout == 0 or time.ticks_diff(time.ticks_ms(), start_time) < timeout:
            # Verificar flags
            irq_flags = self._read(Registers.IRQ_FLAGS)
            
            if irq_flags & IRQFlags.RX_DONE:
                # Limpiar flag
                self._write(Registers.IRQ_FLAGS, IRQFlags.RX_DONE)
                
                # Verificar CRC
                if not (irq_flags & IRQFlags.PAYLOAD_CRC_ERROR):
                    return self._read_payload()
            
            # Pequeña pausa si hay timeout
            if timeout > 0:
                time.sleep_ms(10)
        
        return None

    def start_continuous_receive(self, callback=None):
        """
        Configura recepción continua con callback opcional.
        
        Args:
            callback: Función a llamar cuando se recibe un mensaje
        """
        if callback:
            self.on_recv(callback)
        self.recv()

    def stop_receive(self):
        """Detiene el modo de recepción continua."""
        self.standby()
        if self.rx:
            self.rx.irq(handler=None, trigger=0)
            
    #
    # Métodos para obtener información del módulo
    #
    def get_rssi(self):
        """
        Obtiene el RSSI (intensidad de la señal) del último paquete recibido.
        
        Returns:
            int: Valor RSSI en dBm
        """
        rssi = self._read(Registers.PKT_RSSI_VALUE)
        
        # Ajuste de RSSI según banda de frecuencia
        if self._config['frequency'] >= 779.0:
            return rssi - 157
        return rssi - 164

    def get_snr(self):
        """
        Obtiene la relación señal/ruido del último paquete recibido.
        
        Returns:
            float: Valor SNR en dB
        """
        return self._read(Registers.PKT_SNR_VALUE) * 0.25

    def get_config(self):
        """
        Obtiene la configuración actual del módulo.
        
        Returns:
            dict: Configuración actual
        """
        return self._config.copy()
    
    #
    # Métodos de bajo nivel para comunicación SPI
    #
    def _read_payload(self):
        """
        Lee el payload del último paquete recibido.
        
        Returns:
            bytes: Datos recibidos
        """
        # Obtener dirección del puntero FIFO
        current_addr = self._read(Registers.FIFO_RX_CURRENT_ADDR)
        self._write(Registers.FIFO_ADDR_PTR, current_addr)
        
        # Determinar longitud
        if self._config['implicit']:
            length = self._read(Registers.PAYLOAD_LENGTH)
        else:
            length = self._read(Registers.RX_NB_BYTES)
        
        # Leer datos
        payload = bytearray(length)
        for i in range(length):
            payload[i] = self._read(Registers.FIFO)
        
        gc.collect()
        return bytes(payload)

    def _transfer(self, addr, value=0x00):
        """
        Realiza una transferencia SPI.
        
        Args:
            addr: Dirección del registro
            value: Dato a escribir (solo para escritura)
            
        Returns:
            bytearray: Dato leído
        """
        resp = bytearray(1)
        self.cs.value(0)
        
        try:
            self.spi.write(bytes([addr]))
            self.spi.write_readinto(bytes([value]), resp)
        finally:
            self.cs.value(1)
            
        return resp

    def _read(self, addr):
        """
        Lee un registro.
        
        Args:
            addr: Dirección del registro
            
        Returns:
            int: Valor leído
        """
        return int.from_bytes(self._transfer(addr & 0x7f), 'big')

    def _write(self, addr, value):
        """
        Escribe en un registro.
        
        Args:
            addr: Dirección del registro
            value: Valor a escribir
        """
        self._transfer(addr | 0x80, value)


# Ejemplo de uso
def create_lora(spi, cs_pin, rx_pin=None, **kwargs):
    """
    Crea y configura una instancia de LoRa con los parámetros especificados.
    
    Args:
        spi: Objeto SPI configurado
        cs_pin: Pin CS para SPI
        rx_pin: Pin para interrupción de recepción (opcional)
        **kwargs: Parámetros adicionales de configuración
        
    Returns:
        LoRa: Instancia configurada
    """
    cs = Pin(cs_pin, Pin.OUT, value=1)
    rx = Pin(rx_pin, Pin.IN) if rx_pin else None
    
    return LoRa(spi, cs=cs, rx=rx, **kwargs)
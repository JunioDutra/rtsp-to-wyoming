#!/usr/bin/env python3
"""
ONVIF Voice Assistant for Home Assistant
Connects ONVIF camera audio to Wyoming Faster Whisper
"""

import asyncio
import json
import logging
import os
import socket
import struct
import sys
import wave
from pathlib import Path
from typing import Optional
import io

import av
import numpy as np
import requests
import webrtcvad

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class WyomingClient:
    """Cliente para comunicação com Wyoming Protocol"""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        
    def connect(self):
        """Conecta ao servidor Wyoming"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            logger.info(f"Connected to Wyoming server at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Wyoming server: {e}")
            return False
    
    def send_audio(self, audio_data: bytes, sample_rate: int = 16000, sample_width: int = 2, channels: int = 1) -> Optional[str]:
        """
        Envia áudio para Wyoming e recebe transcrição
        
        Wyoming Protocol format:
        - Header: tipo de mensagem (audio-chunk, audio-stop, etc)
        - Payload: dados do áudio em PCM
        """
        try:
            if not self.socket:
                if not self.connect():
                    return None
            
            # Enviar início da transcrição
            self._send_message({
                "type": "transcribe",
                "data": {
                    "rate": sample_rate,
                    "width": sample_width,
                    "channels": channels
                }
            })
            
            # Enviar chunks de áudio
            chunk_size = 8192
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                self._send_audio_chunk(chunk)
            
            # Sinalizar fim do áudio
            self._send_message({"type": "audio-stop"})
            
            # Receber transcrição
            response = self._receive_message()
            
            if response and response.get("type") == "transcript":
                text = response.get("data", {}).get("text", "")
                if text:
                    logger.info(f"Transcription received: '{text}'")
                else:
                    logger.debug("Empty transcription received")
                return text
            
            logger.debug("No transcript response received")
            return None
            
        except Exception as e:
            logger.error(f"Error sending audio to Wyoming: {e}")
            self.disconnect()
            return None
    
    def _send_message(self, message: dict):
        """Envia mensagem JSON para Wyoming"""
        data = json.dumps(message).encode("utf-8")
        # Enviar tamanho da mensagem (4 bytes) + mensagem
        self.socket.sendall(struct.pack("<I", len(data)) + data)
    
    def _send_audio_chunk(self, chunk: bytes):
        """Envia chunk de áudio"""
        self._send_message({
            "type": "audio-chunk",
            "data": chunk.hex()
        })
    
    def _receive_message(self) -> Optional[dict]:
        """Recebe mensagem JSON do Wyoming"""
        try:
            # Receber tamanho da mensagem (4 bytes)
            size_data = self.socket.recv(4)
            if not size_data:
                return None
            
            size = struct.unpack("<I", size_data)[0]
            
            # Receber mensagem completa
            data = b""
            while len(data) < size:
                chunk = self.socket.recv(size - len(data))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode("utf-8"))
            
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None
    
    def disconnect(self):
        """Desconecta do servidor"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None


class AudioBuffer:
    """Buffer para acumular áudio com VAD (Voice Activity Detection)"""
    
    def __init__(self, sample_rate: int = 16000, vad_threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.buffer = []
        self.vad = webrtcvad.Vad(2)  # Agressividade média (0-3)
        self.vad_threshold = vad_threshold
        self.is_speaking = False
        self.silence_frames = 0
        self.max_silence_frames = 20  # ~600ms de silêncio para finalizar
        
    def add_frame(self, frame: bytes) -> Optional[bytes]:
        """
        Adiciona frame de áudio ao buffer
        Retorna áudio completo quando detectar fim da fala
        """
        # Verificar atividade de voz (frame deve ter 10, 20 ou 30ms a 8/16/32kHz)
        try:
            is_speech = self.vad.is_speech(frame, self.sample_rate)
        except:
            is_speech = True  # Se VAD falhar, assume que é fala
        
        if is_speech:
            if not self.is_speaking:
                logger.debug("🎤 Voice activity detected - Recording started")
            self.is_speaking = True
            self.silence_frames = 0
            self.buffer.append(frame)
        elif self.is_speaking:
            self.silence_frames += 1
            self.buffer.append(frame)
            
            # Se silêncio durar muito, considera que a fala terminou
            if self.silence_frames >= self.max_silence_frames:
                audio_data = b"".join(self.buffer)
                duration_seconds = len(audio_data) / (self.sample_rate * 2)  # 2 bytes per sample
                logger.debug(f"🔇 Silence detected - Recording stopped (duration: {duration_seconds:.2f}s, {len(audio_data)} bytes)")
                self.reset()
                return audio_data
        
        return None
    
    def reset(self):
        """Reseta o buffer"""
        self.buffer = []
        self.is_speaking = False
        self.silence_frames = 0


class ONVIFVoiceAssistant:
    """Assistente de voz principal"""
    
    def __init__(self, config: dict):
        self.config = config
        self.wyoming_client = WyomingClient(
            config["wyoming_host"],
            config["wyoming_port"]
        )
        self.audio_buffer = AudioBuffer(
            sample_rate=config["sample_rate"],
            vad_threshold=config.get("vad_threshold", 0.5)
        )
        self.running = False
        
    async def start(self):
        """Inicia o assistente"""
        logger.info("Starting ONVIF Voice Assistant...")
        logger.info(f"RTSP URL: {self.config['rtsp_url']}")
        logger.info(f"Wyoming server: {self.config['wyoming_host']}:{self.config['wyoming_port']}")
        
        self.running = True
        
        while self.running:
            try:
                await self._process_audio_stream()
            except Exception as e:
                logger.error(f"Error processing audio stream: {e}")
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _process_audio_stream(self):
        """Processa stream de áudio da câmera ONVIF"""
        logger.info("Opening RTSP stream...")
        
        # Abrir stream RTSP com PyAV
        container = av.open(self.config["rtsp_url"], options={
            'rtsp_transport': 'tcp',
            'stimeout': '5000000'  # 5 segundos timeout
        })
        
        # Encontrar stream de áudio
        audio_stream = None
        for stream in container.streams:
            if stream.type == 'audio':
                audio_stream = stream
                break
        
        if not audio_stream:
            raise Exception("No audio stream found in RTSP source")
        
        logger.info(f"Audio stream found: {audio_stream.codec_context.name}, "
                   f"{audio_stream.codec_context.sample_rate}Hz, "
                   f"{audio_stream.codec_context.channels} channels")
        
        # Configurar resampler para 16kHz mono (formato esperado pelo Whisper)
        resampler = av.audio.resampler.AudioResampler(
            format='s16',
            layout='mono',
            rate=self.config["sample_rate"]
        )
        
        logger.info("Processing audio stream...")
        
        for packet in container.demux(audio_stream):
            if not self.running:
                break
                
            for frame in packet.decode():
                # Resample para formato correto
                resampled_frames = resampler.resample(frame)
                
                for resampled_frame in resampled_frames:
                    # Converter para bytes PCM
                    audio_bytes = resampled_frame.to_ndarray().tobytes()
                    
                    # Processar em chunks de 30ms (480 samples a 16kHz)
                    frame_size = int(self.config["sample_rate"] * 0.03) * 2  # 2 bytes por sample
                    
                    for i in range(0, len(audio_bytes), frame_size):
                        chunk = audio_bytes[i:i + frame_size]
                        
                        if len(chunk) < frame_size:
                            continue
                        
                        # VAD e buffer
                        if self.config.get("vad_enabled", True):
                            complete_audio = self.audio_buffer.add_frame(chunk)
                            
                            if complete_audio:
                                # Enviar para transcrição
                                await self._transcribe_and_process(complete_audio)
                        else:
                            # Sem VAD, acumular por tempo fixo
                            self.audio_buffer.buffer.append(chunk)
                            
                            # Processar a cada X segundos
                            buffer_duration = len(self.audio_buffer.buffer) * 0.03
                            chunk_target = self.config.get("chunk_duration", 2)
                            
                            if buffer_duration >= chunk_target:
                                complete_audio = b"".join(self.audio_buffer.buffer)
                                logger.debug(f"🎵 Accumulated {buffer_duration:.1f}s of audio (target: {chunk_target}s)")
                                self.audio_buffer.reset()
                                await self._transcribe_and_process(complete_audio)
        
        container.close()
    
    async def _transcribe_and_process(self, audio_data: bytes):
        """Transcreve áudio e processa comandos"""
        try:
            duration = len(audio_data) / (self.config["sample_rate"] * 2)
            logger.debug(f"📤 Sending audio to Wyoming: {len(audio_data)} bytes ({duration:.2f}s)")
            
            # Enviar para Wyoming Whisper
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                self.wyoming_client.send_audio,
                audio_data,
                self.config["sample_rate"]
            )
            
            if text:
                text = text.strip().lower()
                logger.info(f"✅ Recognized text: '{text}'")
                
                # Processar comandos
                await self._process_command(text)
            else:
                logger.debug("⚠️  No text recognized (empty or failed transcription)")
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
    
    async def _process_command(self, text: str):
        """Processa comandos reconhecidos"""
        commands = self.config.get("commands", [])
        
        logger.debug(f"🔍 Checking {len(commands)} command patterns for: '{text}'")
        
        for command in commands:
            pattern = command["pattern"].lower()
            
            # Match simples (pode melhorar com fuzzy matching)
            if pattern in text:
                logger.info(f"🎯 Command matched! Pattern: '{pattern}' → Action: {command['action']}")
                await self._execute_action(command)
                return
        
        logger.info(f"❌ No command matched for text: '{text}'")
    
    async def _execute_action(self, command: dict):
        """Executa ação no Home Assistant"""
        try:
            action = command["action"]
            entity_id = command.get("entity_id")
            service_data = command.get("service_data", {})
            
            logger.debug(f"🚀 Executing: {action} on {entity_id}")
            
            # Chamar serviço do Home Assistant
            url = "http://supervisor/core/api/services/" + action.replace(".", "/")
            
            payload = {}
            if entity_id:
                payload["entity_id"] = entity_id
            
            if isinstance(service_data, str):
                service_data = json.loads(service_data)
            payload.update(service_data)
            
            logger.debug(f"📡 Request URL: {url}")
            logger.debug(f"📦 Payload: {payload}")
            
            headers = {
                "Authorization": f"Bearer {os.environ.get('SUPERVISOR_TOKEN')}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.ok:
                logger.info(f"✅ Action executed successfully: {action} on {entity_id}")
            else:
                logger.error(f"❌ Failed to execute action: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Error executing action: {e}")
    
    def stop(self):
        """Para o assistente"""
        logger.info("Stopping assistant...")
        self.running = False


async def main():
    """Função principal"""
    # Carregar configuração
    config_path = Path("/data/options.json")
    
    if not config_path.exists():
        logger.error("Configuration file not found!")
        sys.exit(1)
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Ajustar nível de log
    log_level = config.get("log_level", "info").upper()
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Criar e iniciar assistente
    assistant = ONVIFVoiceAssistant(config)
    
    try:
        await assistant.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        assistant.stop()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
ONVIF Voice Assistant for Home Assistant
Connects ONVIF camera audio to Wyoming Faster Whisper
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import wave
from pathlib import Path
from typing import Optional

import av
import numpy as np
import requests
import webrtcvad
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncClient

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class WyomingClient:
    """Cliente para comunicação com Wyoming Protocol usando biblioteca oficial"""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.uri = f"tcp://{host}:{port}"
        
    async def send_audio(self, audio_data: bytes, sample_rate: int = 16000, sample_width: int = 2, channels: int = 1) -> Optional[str]:
        """
        Envia áudio para Wyoming e recebe transcrição usando protocolo oficial
        """
        try:
            logger.debug(f"📨 Connecting to Wyoming at {self.uri}")
            
            async with AsyncClient.from_uri(self.uri) as client:
                logger.info(f"✅ Connected to Wyoming server")
                
                # Padrão Wyoming Satellite: AudioStart → AudioChunk(s) → AudioStop
                # NÃO envia Transcribe (isso é para clientes ASR diretos)
                
                # 1. Enviar AudioStart
                await client.write_event(
                    AudioStart(
                        rate=sample_rate,
                        width=sample_width,
                        channels=channels
                    ).event()
                )
                logger.debug(f"📨 AudioStart (rate={sample_rate}Hz, {sample_width}B, {channels}ch)")
                
                # 2. Enviar áudio em chunks (padrão satellite: 1024 samples)
                chunk_size = 1024 * sample_width * channels
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
                chunks_sent = 0
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i + chunk_size]
                    await client.write_event(
                        AudioChunk(
                            rate=sample_rate,
                            width=sample_width,
                            channels=channels,
                            audio=chunk
                        ).event()
                    )
                    chunks_sent += 1
                    
                    # Log a cada 10 chunks ou no último
                    if chunks_sent % 10 == 0 or chunks_sent == total_chunks:
                        logger.debug(f"📦 Chunk {chunks_sent}/{total_chunks}")
                
                logger.debug(f"📦 {chunks_sent} chunks sent ({len(audio_data)} bytes)")
                
                # 3. Sinalizar fim do áudio
                await client.write_event(AudioStop().event())
                logger.info("🛑 AudioStop sent - waiting for transcript...")
                
                # 4. Aguardar resposta Transcript (como Wyoming Satellite)
                # Timeout ajustado baseado no tamanho do áudio (1s por 2s de áudio, min 30s, max 60s)
                audio_duration = len(audio_data) / (16000 * 2)  # 16kHz, 2 bytes per sample
                timeout = max(30.0, min(60.0, audio_duration * 0.5))
                logger.debug(f"⏱️  Waiting for transcript (timeout: {timeout:.1f}s for {audio_duration:.1f}s audio)")
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        logger.warning(f"⏰ Timeout after {timeout}s")
                        return None
                    
                    event = await asyncio.wait_for(client.read_event(), timeout=5.0)
                    
                    if event is None:
                        logger.debug("⚠️  Connection closed without response")
                        break
                    
                    if Transcript.is_type(event.type):
                        transcript = Transcript.from_event(event)
                        text = transcript.text.strip()
                        
                        if text:
                            logger.debug(f"� Received transcript: '{text}'")
                            return text
                        else:
                            logger.debug("📥 Received empty transcript")
                            return None
                
                logger.debug("⚠️  No transcript received")
                return None
                
        except asyncio.TimeoutError:
            logger.error("⏰ Timeout waiting for response from Wyoming (>30s)")
            return None
        except Exception as e:
            logger.error(f"❌ Error communicating with Wyoming: {e}")
            logger.exception(e)
            return None


class AudioBuffer:
    """Buffer para acumular áudio com VAD (Voice Activity Detection)"""
    
    def __init__(self, sample_rate: int = 16000, vad_threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.buffer = []
        self.vad = webrtcvad.Vad(3)  # Agressividade MÁXIMA (0-3) para reduzir false positives
        self.vad_threshold = vad_threshold
        self.is_speaking = False
        self.silence_frames = 0
        self.max_silence_frames = 30  # ~900ms de silêncio (aumentado de 20)
        self.max_recording_frames = 1000  # Máximo 30s de gravação (1000 frames × 30ms)
        self.recorded_frames = 0
        self.min_energy_threshold = 500  # Energia mínima para considerar como voz real (rejeita TV/rádio distante)
        
    def _calculate_energy(self, frame: bytes) -> float:
        """Calcula energia RMS do frame de áudio"""
        import array
        samples = array.array('h', frame)  # 16-bit signed integers
        sum_squares = sum(s * s for s in samples)
        return (sum_squares / len(samples)) ** 0.5 if samples else 0
        
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
        
        # FILTRO DE ENERGIA: Rejeitar áudio de TV/rádio distante
        energy = self._calculate_energy(frame)
        if is_speech and energy < self.min_energy_threshold:
            logger.debug(f"🔇 Low energy audio rejected: {energy:.0f} < {self.min_energy_threshold}")
            is_speech = False
        
        if is_speech:
            if not self.is_speaking:
                logger.info("🎤 Voice activity detected - Recording started")
                self.recorded_frames = 0
            self.is_speaking = True
            self.silence_frames = 0
            self.buffer.append(frame)
            self.recorded_frames += 1
            
            # LIMITE MÁXIMO: Forçar finalização após 30s
            if self.recorded_frames >= self.max_recording_frames:
                audio_data = b"".join(self.buffer)
                duration_seconds = len(audio_data) / (self.sample_rate * 2)
                logger.warning(f"⚠️  Max recording duration reached! Forcing stop: {duration_seconds:.2f}s, {len(audio_data)} bytes")
                self.reset()
                return audio_data
            
            # Log periódico durante gravação
            if self.recorded_frames % 50 == 0:
                duration = self.recorded_frames * 0.03
                logger.debug(f"📼 Recording... {duration:.1f}s ({self.recorded_frames}/{self.max_recording_frames} frames)")
        elif self.is_speaking:
            self.silence_frames += 1
            self.buffer.append(frame)
            
            # Log de silêncio
            if self.silence_frames == 1:
                logger.debug(f"🔇 Silence started (frames: {len(self.buffer)})")
            
            # Se silêncio durar muito, considera que a fala terminou
            if self.silence_frames >= self.max_silence_frames:
                audio_data = b"".join(self.buffer)
                duration_seconds = len(audio_data) / (self.sample_rate * 2)  # 2 bytes per sample
                logger.info(f"✅ Recording complete: {duration_seconds:.2f}s, {len(audio_data)} bytes, silence frames: {self.silence_frames}")
                self.reset()
                return audio_data
            elif self.silence_frames % 10 == 0:
                logger.debug(f"🔇 Silence continuing... {self.silence_frames}/{self.max_silence_frames} frames")
        
        return None
    
    def reset(self):
        """Reseta o buffer"""
        self.buffer = []
        self.is_speaking = False
        self.silence_frames = 0
        self.recorded_frames = 0


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
        
        frame_count = 0
        vad_check_count = 0
        
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
                        
                        frame_count += 1
                        
                        # Log inicial para debug
                        if frame_count == 1:
                            logger.debug(f"📊 Frame size: {frame_size} bytes ({frame_size//2} samples = 30ms)")
                        
                        # VAD e buffer
                        if self.config.get("vad_enabled", True):
                            vad_check_count += 1
                            
                            # Log periódico para confirmar que está processando
                            if vad_check_count % 1000 == 0:
                                logger.debug(f"📡 Processed {vad_check_count} VAD checks ({vad_check_count * 0.03:.0f}s of audio)")
                            
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
            
            # Enviar para Wyoming Whisper (agora é async)
            text = await self.wyoming_client.send_audio(
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
        
        # Normalizar texto (remover pontuação final)
        text_clean = text.strip().rstrip('.,!?')
        
        for command in commands:
            pattern = command["pattern"].lower().strip()
            
            # Match com palavras completas (evita "ligar" dar match em "desligar")
            # Aceita se o pattern é exatamente o texto OU se está como palavra completa
            text_words = text_clean.split()
            pattern_words = pattern.split()
            
            # Exact match
            if text_clean == pattern:
                logger.info(f"🎯 Command matched! Pattern: '{pattern}'")
                await self._execute_actions(command)
                return
            
            # Partial match com palavras completas (ex: "por favor ligar a luz" deve dar match em "ligar a luz")
            if all(word in text_words for word in pattern_words):
                # Verificar se as palavras aparecem na ordem correta
                try:
                    indices = [text_words.index(word) for word in pattern_words]
                    if indices == sorted(indices):  # Palavras na ordem
                        logger.info(f"🎯 Command matched! Pattern: '{pattern}'")
                        await self._execute_actions(command)
                        return
                except ValueError:
                    pass
        
        logger.info(f"❌ No command matched for text: '{text_clean}'")
    
    async def _execute_actions(self, command: dict):
        """Executa uma ou múltiplas ações do comando"""
        # Suporte para formato antigo (action único) e novo (actions lista)
        if "actions" in command:
            actions_list = command["actions"]
            if not isinstance(actions_list, list):
                actions_list = [actions_list]
        elif "action" in command:
            # Formato antigo: converter para lista
            actions_list = [{
                "action": command["action"],
                "entity_id": command.get("entity_id"),
                "service_data": command.get("service_data", {})
            }]
        else:
            logger.error("❌ Command has no 'action' or 'actions' field!")
            return
        
        logger.info(f"🚀 Executing {len(actions_list)} action(s)...")
        
        for idx, action_config in enumerate(actions_list, 1):
            logger.info(f"  [{idx}/{len(actions_list)}] {action_config.get('action', 'unknown')}")
            await self._execute_action(action_config)
    
    async def _execute_action(self, action_config: dict):
        """Executa uma ação individual no Home Assistant"""
    async def _execute_action(self, action_config: dict):
        """Executa uma ação individual no Home Assistant"""
        try:
            action = action_config.get("action")
            entity_id = action_config.get("entity_id")
            service_data = action_config.get("service_data", {})
            
            logger.debug(f"🚀 Executing: {action} on {entity_id}")
            
            # Obter token de autenticação primeiro
            token = os.environ.get('SUPERVISOR_TOKEN')
            if not token:
                logger.warning("⚠️  SUPERVISOR_TOKEN not found, trying HASSIO_TOKEN...")
                token = os.environ.get('HASSIO_TOKEN')
            
            if not token:
                logger.error("❌ No authentication token found!")
                logger.error("💡 Make sure 'homeassistant_api: true' is set in config.yaml")
                logger.error("� Available env vars: " + ", ".join([k for k in os.environ.keys() if 'TOKEN' in k or 'SUPERVISOR' in k]))
                return
            
            # Dividir action em domain e service (ex: "light.turn_on" -> "light", "turn_on")
            try:
                domain, service = action.split(".", 1)
            except ValueError:
                logger.error(f"❌ Invalid action format: '{action}'. Expected 'domain.service'")
                return
            
            # URL correta da API do Home Assistant via Supervisor
            url = f"http://supervisor/core/api/services/{domain}/{service}"
            
            payload = {}
            if entity_id:
                payload["entity_id"] = entity_id
            
            if isinstance(service_data, str):
                service_data = json.loads(service_data)
            payload.update(service_data)
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            logger.debug(f"📡 Request URL: {url}")
            logger.debug(f"📦 Payload: {payload}")
            logger.debug(f"🔐 Using token: {token[:10]}***")
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.ok:
                logger.info(f"✅ Action executed successfully: {action} on {entity_id}")
            else:
                logger.error(f"❌ Failed to execute action: {response.status_code}")
                logger.error(f"📄 Response: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Error executing action: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
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
    
    # Debug: Mostrar variáveis de ambiente relevantes
    logger.info("🔍 Environment check:")
    logger.info(f"  - SUPERVISOR_TOKEN: {'✅ Present' if os.environ.get('SUPERVISOR_TOKEN') else '❌ Missing'}")
    logger.info(f"  - HASSIO_TOKEN: {'✅ Present' if os.environ.get('HASSIO_TOKEN') else '❌ Missing'}")
    if os.environ.get('SUPERVISOR_TOKEN'):
        token = os.environ.get('SUPERVISOR_TOKEN')
        logger.debug(f"  - Token preview: {token[:10]}***")
    
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

# Changelog

## [1.3.3] - 2025-10-20
### 🐛 Fixed
- **Pattern matching incorreto**: "desligar" não vai mais dar match em "ligar"
  - Implementado match de palavras completas
  - Suporta partial match com ordem correta ("por favor ligar a luz" → "ligar a luz")
  - Remove pontuação final antes de comparar
- **Erro 401 Unauthorized**: Corrigido formato da URL da API
  - URL: `http://supervisor/core/api/services/{domain}/{service}` (formato correto)
  - Melhor validação do formato de action (`domain.service`)
  - Fallback automático: SUPERVISOR_TOKEN → HASSIO_TOKEN
  - Logs detalhados de ambiente e autenticação no startup
- **Debugging melhorado**: 
  - Verifica tokens disponíveis ao iniciar
  - Mostra preview do token sendo usado
  - Traceback completo em caso de erro na execução

### 🎯 Improvements
- Pattern matching agora exige palavras completas na ordem correta
- Melhor logging de autenticação, ambiente e debug de erros
- Validação do formato de action antes de enviar request

## [1.3.2] - 2025-10-20
### 🐛 Fixed
- **VAD muito sensível**: Aumentada agressividade do WebRTC VAD de 2 para 3 (menos false positives de ruído ambiente)
- **Gravações infinitas**: Adicionado limite máximo de 30s de gravação contínua
- **Timeout inadequado**: Timeout dinâmico baseado no tamanho do áudio (min 30s, max 60s)
- **Silêncio muito curto**: Aumentado threshold de silêncio de 600ms para 900ms

### 🎯 Changes
- VAD aggressiveness: 2 → 3 (MAXIMUM)
- Max silence frames: 20 → 30 (~900ms)
- Max recording duration: unlimited → 30s (1000 frames)
- Wyoming timeout: fixed 30s → dynamic 30-60s based on audio length

## [1.3.1] - 2025-10-20
### 🐛 Debug
- Adicionados logs detalhados para debug do pipeline VAD
- Contador de frames gravados e progresso de gravação
- Log de detecção de silêncio e threshold

## [1.3.0] - 2025-10-20
### Changed
- **BREAKING**: Refatorado `WyomingClient` para seguir padrão Wyoming Satellite
  - Removido envio de evento `Transcribe` (usado apenas em clientes ASR diretos)
  - Sequência correta: `AudioStart` → `AudioChunk(s)` → `AudioStop` → aguarda `Transcript`
  - Chunk size ajustado para 1024 samples (padrão satellite) ao invés de 8192 bytes
  - Timeout melhorado com verificação incremental (5s por evento, 30s total)
  - Logs mais informativos sobre conexão e envio de dados

### Technical Details
- Baseado na implementação oficial do `rhasspy/wyoming-satellite`
- Compatível com Wyoming Faster Whisper e outros servidores Wyoming ASR
- Melhor handling de eventos não-Transcript (ignorados, como satellite faz)

## [1.2.0] - 2025-01-20

### Initial Release

#### Features
- ✅ ONVIF/RTSP audio stream capture
- ✅ Wyoming Protocol integration for Faster Whisper
- ✅ Voice Activity Detection (VAD) using WebRTC VAD
- ✅ Customizable voice commands
- ✅ Direct Home Assistant API integration
- ✅ Configurable audio processing parameters
- ✅ Multi-architecture support (amd64, aarch64, armv7, armhf, i386)

#### Commands
- Flexible pattern matching for voice commands
- Support for any Home Assistant service call
- Optional entity_id and service_data parameters

#### Audio Processing
- Automatic resampling to 16kHz mono
- Configurable chunk duration
- VAD with adjustable threshold
- Silence detection for natural speech segmentation

#### Configuration
- Web UI configuration through Home Assistant
- Real-time log viewing
- Multiple log levels (debug, info, warning, error)

### Known Limitations
- Single camera support (multi-camera planned for v1.1)
- Basic pattern matching (fuzzy matching planned)
- No wake word detection yet

### Requirements
- Home Assistant OS or Supervised
- Wyoming Faster Whisper server (local or remote)
- ONVIF-compatible camera with audio

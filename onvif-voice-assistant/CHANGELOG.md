# Changelog

## [1.4.2] - 2025-10-20
### 🐛 Fixed
- **Schema inválido impedindo addon de aparecer na loja**: Simplificado schema de `commands`
  - Removida validação detalhada que causava erro no Supervisor
  - Schema agora aceita lista de objetos genéricos
  - Addon deve aparecer normalmente na loja após reload do repositório

## [1.4.1] - 2025-10-20
### ✨ New Features
- **Múltiplas ações por comando**: Agora pode executar várias ações em um único comando de voz
  - Formato antigo (`action` único) ainda funciona para compatibilidade
  - Novo formato: use `actions` com lista de ações
  - Exemplo: "boa noite" → desliga 3 luzes + liga alarme
  - Logs mostram progresso: `[1/3] light.turn_off`, `[2/3] light.turn_off`, etc.

### 🐛 Fixed
- **VAD muito sensível detectando TV/rádio**: Adicionado filtro de energia mínima
  - Calcula RMS energy de cada frame
  - Rejeita áudio com energia < 500 (TV/rádio distante)
  - Evita gravações de 35s+ de conversas de fundo
  - Logs: `🔇 Low energy audio rejected: XXX < 500`

### 🎯 Improvements
- Melhor filtro de ruído ambiente
- Reduz timeouts do Whisper (menos áudios longos enviados)
- Foco em comandos de voz diretos para câmera

## [1.4.0] - 2025-10-20
### 🔄 Major Refactor
- **ESTRUTURA S6-OVERLAY**: Refatorado para usar S6-overlay corretamente
  - Criada estrutura `rootfs/` conforme padrão oficial do HA
  - Service em `rootfs/etc/services.d/onvif-voice-assistant/`
  - Script `run` com bashio para logging padronizado
  - Script `finish` para cleanup ao parar
  - App movido para `rootfs/app/app.py`
- **DOCKERFILE**: Removido CMD, agora usa S6-overlay da imagem base
  - `COPY rootfs /` ao invés de copiar arquivos individuais
  - S6 inicia automaticamente como PID 1
  - `init: false` agora correto (S6 é o init system)

### 🐛 Fixed
- **SUPERVISOR_TOKEN injection**: S6-overlay corretamente configurado deve resolver injeção de variáveis de ambiente
  - Imagens base do HA (`ghcr.io/home-assistant/*-base-python`) já incluem S6-overlay
  - Com `init: false`, S6 roda como PID 1 e gerencia variáveis de ambiente

### 📚 Reference
- Baseado em [home-assistant/addons-example](https://github.com/home-assistant/addons-example)
- [docker-base](https://github.com/home-assistant/docker-base) inclui S6-overlay, Bashio e TempIO

## [1.3.5] - 2025-10-20
### 🐛 Fixed
- **CRITICAL: SUPERVISOR_TOKEN ainda ausente**: Mudado `init: true` no config.yaml
  - **Root cause**: `init: false` é apenas para addons com S6-overlay próprio
  - Com `init: false`, Supervisor não injeta variáveis de ambiente corretamente
  - Este addon não usa S6-overlay, precisa do Docker default init
  - **Resultado**: Supervisor agora deve injetar `SUPERVISOR_TOKEN` corretamente

### 📚 Reference
- Baseado na [documentação oficial](https://developers.home-assistant.io/docs/add-ons/configuration/#optional-configuration-options):
  > "Set this to false to disable the Docker default system init. Use this if the image has its own init system (Like s6-overlay)"

## [1.3.4] - 2025-10-20
### 🐛 Fixed
- **CRITICAL: SUPERVISOR_TOKEN missing**: Adicionadas labels obrigatórias no Dockerfile
  - `io.hass.version`: Versão do addon
  - `io.hass.type="addon"`: Identifica como addon oficial
  - `io.hass.arch`: Arquiteturas suportadas
- **Resultado**: Supervisor agora injeta automaticamente `SUPERVISOR_TOKEN` no ambiente
- **Solução**: Comandos do Home Assistant agora funcionam (sem erro 401)

### 📚 Reference
- Baseado na [documentação oficial do HA](https://developers.home-assistant.io/docs/add-ons/configuration/#add-on-dockerfile)
- Labels são obrigatórias para integração com Supervisor

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

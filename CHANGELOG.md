# Changelog

## [1.0.0] - 2025-10-20

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

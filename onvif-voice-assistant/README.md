# ONVIF Voice Assistant for Home Assistant

Este addon conecta o áudio de uma câmera ONVIF ao Wyoming Faster Whisper para reconhecimento de voz e execução de comandos no Home Assistant.

## 🎯 Funcionalidades

- ✅ Captura áudio de câmeras ONVIF via RTSP
- ✅ Integração nativa com Wyoming Faster Whisper
- ✅ Detecção de atividade de voz (VAD)
- ✅ Reconhecimento de comandos customizáveis
- ✅ Execução automática de ações no Home Assistant
- ✅ Configuração via interface web do HA

## 📋 Pré-requisitos

1. **Wyoming Faster Whisper** rodando e acessível
   - Pode ser um servidor externo ou addon do HA
   - Porta padrão: 10300

2. **Câmera ONVIF** configurada no Home Assistant
   - Com áudio habilitado
   - URL RTSP acessível

## 🚀 Instalação

### Método 1: Via repositório Git (recomendado)

1. No Home Assistant, vá em **Supervisor → Add-on Store → ⋮ (menu) → Repositories**

2. Adicione o repositório:
   ```
   https://github.com/SEU-USUARIO/onvif-voice-assistant
   ```

3. Procure por "ONVIF Voice Assistant" e clique em **Install**

### Método 2: Instalação Local

1. Copie a pasta `onvif-voice-assistant` para:
   ```
   /addon/onvif-voice-assistant/
   ```

2. Reinicie o Supervisor

3. O addon aparecerá na lista de addons locais

## ⚙️ Configuração

### Configuração Básica

```yaml
wyoming_host: "192.168.1.50"  # IP do servidor Wyoming Whisper
wyoming_port: 10300            # Porta do Wyoming
rtsp_url: "rtsp://admin:senha@192.168.1.100:554/stream1"  # URL RTSP da câmera
sample_rate: 16000             # Taxa de amostragem (não alterar)
channels: 1                    # Mono (não alterar)
chunk_duration: 2              # Duração dos chunks em segundos
vad_enabled: true              # Ativar detecção de voz
vad_threshold: 0.5             # Sensibilidade VAD (0-1)
log_level: "info"              # debug, info, warning, error
```

### Configuração de Comandos

#### Formato Simples (uma ação por comando)

```yaml
commands:
  - pattern: "ligar a luz"
    action: "light.turn_on"
    entity_id: "light.sala"
  
  - pattern: "desligar a luz"
    action: "light.turn_off"
    entity_id: "light.sala"
```

#### Formato Avançado (múltiplas ações por comando)

```yaml
commands:
  # Comando "boa noite" executa 4 ações sequenciais
  - pattern: "boa noite"
    actions:
      - action: "light.turn_off"
        entity_id: "light.sala"
      - action: "light.turn_off"
        entity_id: "light.quarto"
      - action: "light.turn_off"
        entity_id: "light.cozinha"
      - action: "switch.turn_on"
        entity_id: "switch.alarme"
  
  # Comando "modo filme" ajusta várias coisas
  - pattern: "modo filme"
    actions:
      - action: "light.turn_on"
        entity_id: "light.tv"
        service_data: '{"brightness": 30}'
      - action: "light.turn_off"
        entity_id: "light.teto"
      - action: "media_player.turn_on"
        entity_id: "media_player.tv_sala"
```

#### Outros Exemplos

```yaml
commands:
  - pattern: "ligar o ventilador"
    action: "switch.turn_on"
    entity_id: "switch.ventilador"
  
  - pattern: "fechar as cortinas"
    action: "cover.close_cover"
    entity_id: "cover.cortina_sala"
  
  - pattern: "tocar música"
    action: "media_player.play_media"
    entity_id: "media_player.spotify"
    service_data: '{"media_content_type": "playlist", "media_content_id": "spotify:playlist:xxxxx"}'
```

### Parâmetros Detalhados

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `wyoming_host` | string | IP ou hostname do servidor Wyoming Whisper |
| `wyoming_port` | int | Porta do Wyoming (padrão: 10300) |
| `rtsp_url` | string | URL completa do stream RTSP da câmera ONVIF |
| `sample_rate` | int | Taxa de amostragem (16000 Hz recomendado) |
| `channels` | int | Número de canais (1 = mono) |
| `chunk_duration` | float | Duração do áudio para processar (segundos) |
| `vad_enabled` | bool | Ativar detecção automática de fala |
| `vad_threshold` | float | Sensibilidade VAD (0.0 a 1.0) |
| `log_level` | string | Nível de log (debug/info/warning/error) |

#### Comandos

Cada comando suporta dois formatos:

**Formato Simples (uma ação):**
- **pattern**: Texto a ser reconhecido (case-insensitive)
- **action**: Serviço do HA no formato `domain.service`
- **entity_id**: (opcional) Entidade alvo
- **service_data**: (opcional) Dados extras em JSON

**Formato Avançado (múltiplas ações):**
- **pattern**: Texto a ser reconhecido
- **actions**: Lista de ações a executar sequencialmente
  - Cada ação tem: `action`, `entity_id` (opcional), `service_data` (opcional)

## 🎙️ Como Usar

1. **Inicie o addon** e verifique os logs

2. **Fale próximo à câmera** com os comandos configurados

3. **Monitore os logs** para ver as transcrições:
   ```
   [INFO] Recognized: 'ligar a luz'
   [INFO] Command matched: ligar a luz
   [INFO] Action executed: light.turn_on on light.sala
   ```

## 🔧 Troubleshooting

### Addon não conecta ao Wyoming

- Verifique se o servidor Wyoming está rodando:
  ```bash
  telnet IP_WYOMING 10300
  ```
- Confirme firewall/rede

### Sem áudio da câmera

- Teste o stream RTSP com VLC ou ffplay:
  ```bash
  ffplay rtsp://admin:senha@IP_CAMERA:554/stream1
  ```
- Verifique se a câmera tem áudio habilitado
- Tente URLs diferentes (stream1, stream2, Streaming/Channels/101, etc)

### Comandos não reconhecidos

- Ative `log_level: debug` para ver todas as transcrições
- Ajuste o `vad_threshold` se muito/pouco sensível
- Use frases claras e pausadas
- Considere melhorar o modelo Whisper (large vs small)

### Alta latência

- Reduza `chunk_duration` (mínimo 1 segundo)
- Use modelo Whisper menor (small, base)
- Verifique latência de rede

## 📊 Monitoramento

Você pode criar sensores no HA para monitorar:

```yaml
# configuration.yaml
sensor:
  - platform: command_line
    name: "Voice Assistant Status"
    command: "docker ps --filter name=addon_onvif_voice --format '{{.Status}}'"
    scan_interval: 60
```

## 🔐 Segurança

- ⚠️ O RTSP URL contém credenciais - proteja seu arquivo de configuração
- 🔒 Use HTTPS para acessar o Home Assistant externamente
- 🛡️ Considere segmentar a rede da câmera

## 🚀 Melhorias Futuras

- [ ] Wake word detection (ativar por "Ok Assistant")
- [ ] Múltiplas câmeras simultâneas
- [ ] Histórico de comandos
- [ ] Integração com Conversation API do HA
- [ ] Feedback sonoro (beep de confirmação)
- [ ] Suporte a frases parciais (fuzzy matching)

## 📝 Licença

MIT License

## 🤝 Contribuições

Pull requests são bem-vindos!

## 🐛 Reportar Problemas

Abra uma issue no GitHub com:
- Logs completos do addon
- Configuração (sem senhas)
- Modelo de câmera
- Versão do Home Assistant

---

**Desenvolvido com ❤️ para a comunidade Home Assistant**

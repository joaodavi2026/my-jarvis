# JARVIS Windows (OpenJarvis local + modo show)

Assistente pessoal 100% local no Windows: voz em português, Ollama + Gemma, e ativação por **duas palmas**.

## Arquitetura

```
MICROFONE -> faster-whisper (STT, pt) -> OpenJarvis -> Ollama -> gemma4:e4b -> resposta
          -> Kokoro (voz pf_dora, pt-BR) -> ALTO-FALANTE

DUAS PALMAS -> detector local (jarvis_show) -> jingle -> Ollama + servidor + navegador -> jarvis chat --voice
```

- **OpenJarvis** (Apache-2.0): clonado em `D:\JARVIS\Source\jarvis` (sem alterações no código). Faz a conversa por voz nativa (`chat --voice`), o servidor web (`start`) e o diagnóstico (`doctor`).
- **jarvis-show** (este repositório, pasta `show/`): só o detector de palmas, o orquestrador e os launchers. Não reimplementa a voz.
- Os providers pagos (OpenAI, Cartesia, ElevenLabs, Deepgram) **não** estão configurados.

## Onde fica cada coisa

| Item | Local |
|---|---|
| Código OpenJarvis | `D:\JARVIS\Source\jarvis` |
| Ambiente Python (SSD) | `%USERPROFILE%\.venvs\openjarvis` (variável de usuário `UV_PROJECT_ENVIRONMENT`) |
| Cache do uv | `%USERPROFILE%\.uv-cache` (`UV_CACHE_DIR`) |
| Configuração do Jarvis | `%USERPROFILE%\.openjarvis\config.toml` |
| Modelos do Ollama | `%USERPROFILE%\.ollama` (SSD) |
| Modelos Kokoro e Whisper | `%USERPROFILE%\.cache\huggingface` |
| jarvis-show | `D:\JARVIS\Source\my-jarvis\show` |
| Jingle (opcional) | `show\assets\jingle.mp3` (ou `JARVIS_JINGLE`) |

## Requisitos e instalação (já feita nesta máquina)

Windows 11, ~15 GB livres. Ferramentas: `uv`, Git, Node >= 22.22 (usa-se o Node 24 do nvm só para o build do frontend), Ollama.

```
winget install -e --id astral-sh.uv
winget install -e --id Ollama.Ollama
git clone https://github.com/open-jarvis/OpenJarvis jarvis
cd jarvis
uv sync --extra desktop --extra voice
ollama pull gemma4:e4b
uv run jarvis _bootstrap --write-config --engine ollama --model gemma4:e4b
uv run jarvis config set security.profile personal
uv run jarvis config set speech.voice_id pf_dora
uv run jarvis config set speech.language pt
```

Ajustes extras aplicados (e por quê):
- `analytics.enabled = false`: o OpenJarvis envia por padrão estatísticas anônimas a um servidor PostHog externo; aqui fica desligado.
- `speech.backend = faster-whisper`, `speech.device = cpu`, `speech.compute_type = int8` (o padrão `float16` não existe na CPU), `speech.model = small` (melhor em português que o `base`).
- Variáveis de usuário `UV_PROJECT_ENVIRONMENT`, `UV_CACHE_DIR`, `UV_PYTHON` (o Python 3.13 **assinado** do python.org) e `UV_PYTHON_PREFERENCE=only-system`: o ambiente fica no SSD e usa o Python assinado.
- Modelo de linguagem do spaCy (só dados), necessário ao gerador de fonemas do Kokoro:
  `uv pip install --python %UV_PROJECT_ENVIRONMENT%\Scripts\python.exe "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"`.
  `uv run` preserva esse pacote; um `uv sync` puro o remove (use `uv sync --extra desktop --extra voice --inexact`).

## Comandos do dia a dia

Na pasta `D:\JARVIS\Source\jarvis`:

| O que | Comando |
|---|---|
| Chat no terminal | `uv run jarvis` |
| Pergunta única | `uv run jarvis ask "sua pergunta"` |
| Interface web | `uv run jarvis start` (http://127.0.0.1:8000, só local) |
| Voz | `uv run jarvis chat --voice` (Enter para falar) |
| Diagnóstico | `uv run jarvis doctor` |

Modo show (em `D:\JARVIS\Source\my-jarvis\show`): `jarvis-show.cmd`. Modo normal (sem palmas, voz nem jingle): `jarvis-start.cmd`.

## jarvis-show

1. Fica ouvindo o microfone (16 kHz, blocos de 20 ms; nada é gravado nem enviado).
2. Uma palma é um som curto, de banda larga, bem acima do ruído de fundo, que decai em cerca de 100 ms. Fala, batidas graves e ruído constante são rejeitados.
3. Uma palma sozinha não faz nada. Duas palmas com 0,15 a 0,8 s entre elas ativam; depois há 5 s de cooldown.
4. Ao ativar: toca o jingle (se existir), garante o Ollama e o servidor, abre o navegador **uma vez** (a cada 2 min no máximo) e abre o `chat --voice` em uma janela. Por padrão o jarvis-show encerra depois de ativar (`--keep-listening` para continuar ouvindo).
5. Só uma instância roda por vez.

Opções: `--list-devices`, `--calibrate` (só mostra palmas detectadas), `--activate-now`, `--no-voice`, `--no-jingle`, `--no-browser`, `--keep-listening`.

### Microfone e sensibilidade

- `jarvis-show.cmd --list-devices` lista as entradas. Defina `JARVIS_MIC` com o número ou parte do nome (ex.: `setx JARVIS_MIC "Microphone Array"`). Sem a variável, usa o microfone padrão do Windows.
- `JARVIS_CLAP_THRESH` (padrão 8): quanto **maior**, **menos** sensível. Palmas ativando sozinhas: aumente (12, 16...). Palmas não detectadas: diminua (6, 5...) e confira o dispositivo. Use `--calibrate` para ver o que é detectado.

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| `ollama` não responde | `ollama serve` (o app do Ollama costuma iniciar sozinho no login) |
| Kokoro reclama de eSpeak | normalmente não é necessário (a biblioteca vem embutida). Se ocorrer: `winget install -e --id eSpeak-NG.eSpeak-NG` e `setx PHONEMIZER_ESPEAK_LIBRARY "C:\Program Files\eSpeak NG\libespeak-ng.dll"` |
| "Uma política de Controle de Aplicativo bloqueou este arquivo" | o Smart App Control barrou um módulo nativo sem reputação. Não desative o SAC: veja qual arquivo em `Get-WinEvent -LogName Microsoft-Windows-CodeIntegrity/Operational` (id 3077) e use outra versão do pacote |
| Microfone sem som | Configurações > Privacidade > Microfone: permitir apps de desktop |
| Resposta lenta | o `gemma4:e4b` roda em CPU (cerca de 17 tokens/s). O primeiro uso carrega o modelo (~15 s) |
| `jarvis doctor` avisa do Node 20 | o aviso é só para o ClaudeCodeAgent e o WhatsApp; o frontend é compilado com o Node 24 do nvm |
| Aviso "Failed to set up rate limiter ... openjarvis_rust" | a extensão Rust opcional não está compilada (o Rust não compila neste PC por causa do SAC); o limitador de taxa fica indisponível |

# ADR-0007 — OpenJarvis como motor de voz e IA; este repositório como camada Windows

- **Status:** aceito (2026-10-05), por decisão do usuário (especificação mestre "JARVIS Local para Windows").
- **Contexto:** o plano original previa construir STT, TTS, provider de LLM e router do zero (fases 6 a 10). O OpenJarvis (Apache-2.0) já entrega faster-whisper (STT), Kokoro (TTS), engine Ollama, servidor web, `doctor` e conversa por voz.

## Decisão

- **Motor:** OpenJarvis, clonado **sem modificar o código** em `D:\JARVIS\Source\jarvis`. STT = faster-whisper (small, pt), TTS = Kokoro (`pf_dora`), LLM = Ollama `gemma4:e4b`, tudo local. Providers pagos não são configurados.
- **Este repositório (my-jarvis)** passa a ser a camada Windows: orbe e shell Electron (ADR-0005), contratos, StorageManager, e o **jarvis-show** (palmas, jingle, orquestração) em `show/`.
- **Privacidade:** o analytics externo (PostHog) do OpenJarvis vem ligado por padrão e é desligado na configuração (`analytics.enabled = false`).
- **Smart App Control:** o OpenJarvis não exige compilação (a extensão Rust é opcional). As DLLs nativas dos pacotes Python (faster-whisper, ctranslate2, onnxruntime, torch, sounddevice, kokoro) carregam com o SAC ligado; uma tentativa inicial de importar o spaCy foi bloqueada e depois liberada pela reputação. O Python é o 3.13 **assinado** do python.org (`UV_PYTHON`), nunca os Pythons sem assinatura baixados pelo uv.

## Consequências

- As fases 6 a 10 do roadmap passam a ser cobertas pelo OpenJarvis. Permanecem nossas: shell/orbe, storage, jarvis-show, e as integrações futuras (Google, presença, briefings), que entrarão como camadas sobre o OpenJarvis ou ao lado dele.
- A integração do orbe com o OpenJarvis (estados reais a partir do servidor `127.0.0.1:8000`) fica para uma fase própria.
- Atualizações do OpenJarvis (`git pull`) são feitas com cuidado: o `uv.lock` do projeto fixa as versões que carregaram com o SAC.

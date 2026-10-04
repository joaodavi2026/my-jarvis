# JARVIS — Roadmap

Cada fase só é considerada concluída com testes escritos para o JARVIS e relatório honesto
(**IMPLEMENTED / TESTED / MANUALLY VALIDATED / NOT TESTED / KNOWN ISSUES**). Commits pequenos e semânticos; push após fase testada.

| Fase | Entrega | Critério de saída |
|---|---|---|
| **0** Repository bootstrap | repo, `.gitignore`, estrutura, config template | primeiro push sincronizado ✔ |
| **1** Architecture & Security Design | ARCHITECTURE, SECURITY, ROADMAP, ADRs, contratos (`contracts/`) | documentos revisados e commitados |
| **2** StorageManager | identidade por GUID, categorias, normal/degraded, hot reconnect, `FakeVolumeProvider`, escrita atômica, testes | suíte de cenários do ADR-0003 verde |
| **3** Desktop Shell (Electron, ADR-0005) | app Electron, tray, ciclo de vida, single-instance, janelas | executa; tray e fechar-sem-encerrar validados manualmente |
| **4** Orb / HUD / Visual State Machine | orbe azul neon transparente, estados visuais, interações (clique, menu), posição configurável | reducer testado; validação visual manual |
| **5** Python Local Service + IPC | serviço mínimo, WebSocket autenticado, event bus, health check, state machine autoritativa | testes de handshake/segurança; shell ↔ serviço funcionando |
| **6** Audio Infrastructure | captura, dispositivo, nível, VAD | níveis no orbe; CPU em repouso medida |
| **7** Local STT / Wake Word / Clap | STT local pt-BR/en, wake word "Jarvis", palmas | download de modelo só com confirmação de tamanho/destino |
| **8** Local TTS | TTS local, interrupção, barge-in | fala interrompível |
| **9** Local AI Provider / Ollama | `AIProvider`, `ModelCapabilities`, recomendação de modelos por hardware (2–4 opções) | model-agnostic; sem download silencioso |
| **10** Deterministic Intent Router | router pt-BR/en sem LLM | comandos simples funcionam offline |
| **11** Tool Registry + Permission System | tools com schema, `access`/`risk`, confirmações, auditoria | testes de política e injeção |
| **12** Agentic Harness | loop limitado, plano com status, observe/verify, pausa/retomada, `AgentRun` | limites, cancelamento e loop-detection testados |
| **13** Skills | `SkillRegistry`, skills iniciais | descoberta por metadados |
| **14** Memory + Context | memória, `UserContext`, `ContextManager`, provenance | memória editável/apagável |
| **15** Google Integration | OAuth, Calendar, Gmail, Drive (Docs/Sheets depois) | escopos mínimos; envio/exclusão sempre confirmados |
| **16** Presence + Face Recognition | presença local, reconhecimento facial local | biometria protegida; sem contornar Windows Hello |
| **17** Briefings + Personal Radar | AttentionEngine, interrupção, news, morning briefing | números só de dados estruturados |
| **18** Health/Fitness providers | `PersonalDataProvider`, baseline, post-workout | sem diagnóstico; estatística determinística |
| **19** Hardening, packaging, optimization | instalador (core no SSD), perfis de CPU/RAM, auditoria de segurança | métricas de idle atingidas |

## Escopo imediato

Executar **Fases 0 → 5** e **parar** para revisão antes de áudio, STT/TTS, Ollama ou Agentic Harness.

## Princípios de planejamento

- Nada de "grande reescrita": cada fase entra por pontos de extensão já previstos na arquitetura.
- Dependências pesadas (modelos, ffmpeg, engines) só quando a fase exigir e com confirmação.
- Funcionalidades futuras (Google, presença, briefings, saúde, rádio pessoal, canais) permanecem no roadmap, sem implementação antecipada.

# JARVIS — Arquitetura

> Fonte de requisitos: a especificação do produto JARVIS. Este documento descreve **como** atendê-la.
> **Shell:** Electron (ADR-0005, que substitui a parte de shell da ADR-0001). O código Tauri está arquivado na branch `feature/tauri-shell`.
> Status: Phase 1 (design). Nada abaixo da camada de fundações está implementado — veja [ROADMAP](ROADMAP.md).

## 1. Princípios que guiam as decisões

1. **Local-first / offline-first.** Todo recurso essencial tem caminho local; nuvem é opcional, desativada por padrão.
2. **O modelo só *solicita*.** Quem valida, autoriza e executa é código determinístico (Permission Layer).
3. **Menor nível de execução suficiente:** DIRECT (determinístico) → ASSISTED (1 decisão de IA) → AGENTIC (várias etapas). Hardware sem GPU dedicada obriga a minimizar chamadas ao LLM.
4. **Um dono por responsabilidade.** Um registro de tools, uma política de permissão, uma máquina de estados autoritativa.
5. **Falha graciosa, sem ponto único de falha.** Cada módulo declara suas dependências e o que acontece sem elas.
6. **Código ≠ dados.** Repositório só com código; dados em `JARVIS_STORAGE_ROOT`.
7. **Extensível por registro, não por `if`.** Tools, Skills, providers, triggers e integrações se *registram*; o núcleo os descobre.

## 2. Visão de processos

```
┌──────────────────────────── Windows (usuário) ────────────────────────────┐
│  ┌─────────────── Electron app (SSD) ───────────────┐                      │
│  │  MAIN (Node/TS shell)       RENDERER (React/TS)   │                      │
│  │  • lifecycle/autostart     • Orb / HUD / Painel │                      │
│  │  • tray, janelas, atalho   • Settings           │                      │
│  │  • supervisor do Python    • Dev console        │                      │
│  │  • broker IPC (token)  <-preload API->  render  │                      │
│  └──────────┬──────────────────────────────────────┘                      │
│             │ WebSocket 127.0.0.1:<porta dinâmica> + token de sessão      │
│  ┌──────────▼──────────────── Serviço Python (filho do shell) ───────────┐ │
│  │ Event bus · State machine autoritativa · StorageManager · Security    │ │
│  │ Audio>VAD>Wake/Clap>STT · TTS · Router · Harness · Skills · Tools     │ │
│  │ Memory/Context · AI providers · Integrações · Presence · Radar        │ │
│  └───────┬──────────────────────────┬──────────────────────┬─────────────┘ │
│   SSD interno                  HD JD (D:\JARVIS)        Rede (opcional)    │
│   bootstrap, config, DB crítico  modelos, dados pesados   Google, clima…   │
└───────────────────────────────────────────────────────────────────────────┘
```

A WebView **nunca** fala com o Python diretamente: só com o processo principal do shell (API do preload, sem Node no renderer). O token da sessão existe apenas na memória do Rust e do Python.

## 3. Fronteiras de responsabilidade

| Camada | É dona de | Não faz |
|---|---|---|
| **Shell (processo principal do Electron, Node/TS)** | ciclo de vida do app, autostart, system tray, criação/posição/transparência/always-on-top das janelas, atalho global, single-instance, supervisão e reinício do Python, geração do token, cliente WebSocket, persistência de **preferências de janela** (posição do orbe) | lógica de assistente, permissões, tools, IA, acesso a dados do usuário |
| **React/TypeScript** | renderização (orbe, HUD, painel, settings), animações, máquina de estados **visual** derivada de eventos, formulários de configuração, diálogo de confirmação (apenas exibe e devolve a resposta) | decidir o que é permitido, guardar segredos, falar com rede/Python direto |
| **Python** | tudo que é inteligência e I/O: storage, áudio, STT/TTS, IA, router, harness, skills, **registro único de tools**, permissões, memória, integrações, **estado autoritativo** | janelas/tray/atalho (pedidos chegam como eventos do shell) |

Regras de fronteira:
- **Uma só política de permissão e um só `ToolRegistry`** (Python). Tools nativas do Windows (abrir app, volume, screenshot) são tools Python; o Rust só expõe capacidades de *shell*.
- **Estado autoritativo no Python.** A UI mostra `state.changed`; o shell mantém só `CONNECTING/DOWN` locais quando o serviço está ausente (o orbe sempre tem o que mostrar).
- **Contratos compartilhados** ficam em [`contracts/`](../contracts) e são testados dos dois lados (§10).

## 4. Arquitetura de componentes (serviço Python)

```
 orb click | hotkey | wake word | clap  ──►  ActivationRequest
                                                  │
 Mic → Capture → VAD → [Wake/Clap]                ▼
                 │                      InteractionController ◄── State machine
                 ▼                       (única fonte de verdade do estado)
               STT ───────────────────►  IntentPipeline
                                           1. FastLocalIntentRouter   (DIRECT)
                                           2. Skill matcher           (ASSISTED/AGENTIC)
                                           3. AgenticHarness + AIProvider (quando justificado)
                                                  │ só produz ToolRequest / SkillRequest
                                                  ▼
                          ┌─────────── Permission Layer ───────────┐
                          │ schema → trust/provenance → política → │
                          │ confirmação (se exigir) → auditoria    │
                          └────────────────────┬───────────────────┘
                                               ▼
                       ToolExecutor ──► Tools (windows, system, google.*, weather, ...)
                                               │ ToolResult + provenance
                                               ▼
                       Observe/Verify → ResponseComposer → TTS → feedback na UI
 Transversais: EventBus · StorageManager · Config · Logging · SecretStore/Crypto
               Memory/Context · CapabilityGraph · Health/Diagnostics · BackgroundTasks
 Orientados a evento: Presence · ContextEngine · AttentionEngine · InterruptionPolicy · Radar
```

### Módulos e contratos principais (sempre atrás de interfaces; implementações trocáveis)

| Módulo | Contrato | Observação |
|---|---|---|
| `core.events` | `EventBus.publish/subscribe` | assíncrono, tipado, com `correlation_id`; handlers isolados |
| `core.state` | `InteractionMachine.dispatch(trigger)` | tabela em `contracts/state-machine.json` |
| `storage` | `StorageManager.get_path(category)` | única fonte de caminhos; [ADR-0003](adr/0003-storage-tiers-and-durability.md) |
| `security` | `PermissionPolicy`, `ConfirmationBroker`, `SecretStore`, `Vault` | [SECURITY](SECURITY.md) |
| `audio` | `AudioSource`, `VadEngine`, `WakeWordDetector`, `ClapDetector` | processamento local; sem rede |
| `speech` | `SpeechToTextProvider`, `TextToSpeechProvider` | streaming + cancelamento; barge-in |
| `ai` | `AIProvider` + `ModelCapabilities` | Ollama/llama.cpp/cloud opcional; não assume tool-calling |
| `router` | `FastLocalIntentRouter.route(text) → Intent or None` | determinístico, pt-BR/en, sem I/O |
| `harness` | `AgentRuntime.run(goal) → AgentRun` | loop limitado, plano com status, verify, pausa/retomada |
| `skills` | `SkillRegistry`, `Skill` | procedimentos compostos sobre tools |
| `tools` | `ToolRegistry`, `Tool` | `name`, `description`, `input_schema`, `access`, `risk`, `execute()` |
| `memory`, `context` | `MemoryService`, `UserContextService`, `ContextManager` | itens com *provenance* e `trust_level` |
| `integrations.*` | adapters por serviço + tools | Google (auth/calendar/gmail/drive/docs/sheets), weather, news, music, home |
| `presence`, `context_engine` | `PresenceService`, `ContextEngine → ContextualOpportunity` | só identifica oportunidades; não executa |
| `attention` | `AttentionEngine`, `InterruptionManager`, `BriefingComposer` | scoring determinístico antes do LLM |
| `health_data` | `PersonalDataProvider`, `FitnessService`, `BaselineService` | estatística determinística; LLM só comenta |
| `tasks` | `BackgroundTaskManager` | progresso/cancelamento; a UI nunca bloqueia |
| `diagnostics` | `HealthService`, `CapabilityGraph` | checagens leves, sem polling agressivo |

**Extensibilidade sem reescrita.** Cada módulo futuro entra por um ponto de registro: `ToolRegistry.register`, `SkillRegistry.register`, `ContextTriggerEngine.register`, providers de `AI/STT/TTS`, `CommunicationChannel`, `PersonalDataProvider`, `StorageCategory`. O núcleo não importa `integrations.*`; integrações dependem do núcleo, nunca o contrário. Cada módulo publica sua disponibilidade no `CapabilityGraph`, que o harness consulta para não prometer o que não existe.

## 5. Fluxo de eventos

Convenção: `dominio.evento` (passado ou estado), payload JSON versionado, `correlation_id` por interação/`run_id`. Catálogo: [`contracts/event-catalog.md`](../contracts/event-catalog.md).

Fluxo canônico (comando de voz simples, nível DIRECT):

```
activation.orb_clicked      → state IDLE → ACTIVATED → LISTENING
audio.level (~20 Hz, descartável)  → orbe pulsa
speech.detected / speech.ended (VAD)
stt.transcription_ready     → state LISTENING → PROCESSING
router.matched {volume.set} (milissegundos, sem LLM)
permission.evaluated {allow}
tool.started → tool.completed {verified}   → state EXECUTING
tts.started → tts.finished  → state SPEAKING → IDLE
```

Variantes: sem match no router → `ai.thinking` (ASSISTED/AGENTIC); permissão exige confirmação → `confirmation.requested` e estado `AWAITING_CONFIRMATION` até `confirmation.answered` ou timeout; falha → `error.occurred` e estado `ERROR` transitório; cancelamento (clique, "pare", atalho) → `activation.cancelled`, estado `CANCELLED`, depois `IDLE`, com propagação a TTS, tools e steps.

**Entrega.** O barramento é *in-process* no Python. Uma ponte (`ipc`) encaminha ao shell apenas eventos da **allow-list de UI** (estado, nível de áudio, transcrição, tool/confirmação, privacidade, saúde). Eventos de alta frequência usam fila limitada com descarte do mais antigo. Eventos do shell (clique no orbe, atalho, posição da janela) entram como `shell.*`.

**Orientado a evento (futuro).** `AUTHORIZED EVENT → ContextEngine → ProactiveInteractionPolicy → Harness`. Fontes (presença, e-mail, agenda, fitness, bateria) publicam eventos; o ContextEngine produz `ContextualOpportunity`; a política (cooldown, DND, tela cheia, importância) decide entre falar, mostrar indicador no orbe ou nada.

## 6. Máquina de estados principal

Definição normativa: [`contracts/state-machine.json`](../contracts/state-machine.json), consumida por Python e TypeScript (testes de contrato impedem divergência).

```
BOOTING → IDLE --ativação--> ACTIVATED → LISTENING → PROCESSING → EXECUTING → SPEAKING → IDLE
                                 |            |          |  ^         |           |
                                 |            |          v  |         v           |
                                 |            |   AWAITING_CONFIRMATION          |
                                 +---- cancelamento (qualquer estado ativo) --> CANCELLED → IDLE
   qualquer estado --falha--> ERROR --(timeout/ack)--> IDLE        OFFLINE (serviço ausente)
```

Dois eixos ortogonais evitam explosão de estados:

1. **Interação** (acima) — autoritativo, Python.
2. **Modo/flags** — `storage: NORMAL|DEGRADED`, `network: ONLINE|OFFLINE`, `service: CONNECTED|CONNECTING|DOWN` (local ao Rust), privacidade (`mic`, `camera`, `screen`, `cloud`), `muted`, `attention_badge`.

**Estado visual do orbe = f(interação, flags, pulsos).** `SUCCESS` e `ERROR` são *pulsos* transitórios; `COLLECTING/ANALYZING/COMPOSING` (briefing) são sub-etapas de `PROCESSING` declaradas pelo evento; `OFFLINE` vem de `service=DOWN` ou do estado `OFFLINE`. A UI só renderiza o que o estado real informa — sem mensagens de progresso inventadas.

## 7. Local-first, offline-first e degradação

Cada capacidade registra no `CapabilityGraph` seu estado (`AVAILABLE | DEGRADED | UNAVAILABLE(motivo)`) e suas dependências.

| Situação | O que continua | O que informa |
|---|---|---|
| **Sem internet** | orbe, ativação, wake/clap, STT/TTS locais, router, LLM local, tools do Windows, memória local | "Não consigo acessar seu calendário porque estamos offline." |
| **LLM indisponível** | router determinístico + tools ("volume 30" funciona) | modo básico; sem planejamento |
| **HD JD ausente (`STORAGE_DEGRADED`)** | orbe, UI, configurações, tools básicas, diagnóstico, reconexão | recursos dependentes devolvem `STORAGE_UNAVAILABLE`; **não** recria memória no SSD nem baixa modelos nele |
| **HD volta (hot reconnect)** | revalida identidade, reabre bancos/índices, restaura serviços sem reiniciar | "Armazenamento restaurado." |
| **Python caiu** | o shell mostra orbe `OFFLINE`, tray e menu; reinicia o serviço com backoff | "Reiniciando serviço…" |

Falha de dependência externa: *timeouts*, *retry com backoff* apenas se idempotente, *circuit breaker* por provider, mensagens compreensíveis.

## 8. Armazenamento (resumo)

O `StorageManager` é a única fonte de caminhos; categorias tipadas (`CORE, CONFIG, DATABASE, LLM_MODELS, STT_MODELS, TTS_MODELS, VISION_MODELS, EMBEDDINGS, MEMORY, PERSONAL_DATA, DOCUMENTS, CACHE, LOGS, TEMP, BACKUPS`) mapeadas para **interno** ou **externo**. O volume externo é identificado pelo **GUID do volume** (mais label e filesystem), nunca só pela letra. Justificativa de durabilidade (exFAT, HDD USB removível): [ADR-0003](adr/0003-storage-tiers-and-durability.md). Criptografia na aplicação: [ADR-0004](adr/0004-application-level-encryption.md).

- **SSD:** app instalado, bootstrap, config, bancos críticos e índices, estado operacional, FastCache limitado.
- **HD:** modelos, documentos, históricos/dados pesados reconstruíveis, logs, backups locais.
- Código em desenvolvimento: `D:\JARVIS\Source\my-jarvis` (**só código**). Runtime: `JARVIS_STORAGE_ROOT` (hoje `D:\JARVIS`). `PROJECT_ROOT` e `JARVIS_STORAGE_ROOT` são resolvidos separadamente.

## 9. IPC (decisão)

Resumo; comparação completa em [ADR-0002](adr/0002-ipc-transport.md):

- **Transporte:** WebSocket em `127.0.0.1`, porta efêmera (bind na porta 0), nunca `0.0.0.0`.
- **Quem conecta:** só o processo principal do shell. O renderer usa a API do preload (IPC do Electron).
- **Autenticação:** token aleatório de 256 bits gerado pelo shell a cada execução, entregue ao filho pelo **stdin** (não por argv, ambiente ou arquivo), nunca persistido. A primeira mensagem do cliente deve ser `hello{token}` em até 2 s (comparação em tempo constante). Conexões com cabeçalho `Origin` são rejeitadas, e só uma conexão ativa é aceita.
- **Protocolo:** envelope JSON versionado `{v, id, kind: req|res|evt, type, payload}`; `req/res` correlacionados por `id`; `evt` unidirecional; heartbeat.
- **Áudio não trafega no IPC:** o Python captura o microfone; à UI vai só o nível (~20 Hz).

## 10. Estratégia de testes

| Nível | Ferramenta | Cobre |
|---|---|---|
| Unidade (Python) | pytest (+ pytest-asyncio) | storage, máquina de estados, permissões, router, parsing, criptografia |
| Unidade (TS) | Vitest | reducer do estado visual, mapeamento evento → visual |
| Unidade (shell) | Vitest (Node) | supervisor, cliente IPC, protocolo, posicionamento, preferências |
| Contrato | testes que leem `contracts/*` nos 3 lados | transições de estado e catálogo de eventos idênticos |
| Ponta a ponta | Electron real + serviço Python real | handshake, rejeição de cliente sem token, reconexão |
| Fakes/mocks | `FakeVolumeProvider`, `FakeAIProvider`, `FakeSTT/TTS`, `FakeClock` | **sem rede, sem API paga, sem desconectar o HD** |
| Segurança | testes de política e injeção | conteúdo externo nunca autoriza ação; confirmação vinculada a hash; fail-closed |
| Manuais | roteiro documentado | orbe/tray reais, HD físico, microfone |

Todo bug de segurança ganha teste de regressão. Cada relatório de fase separa **IMPLEMENTED / TESTED / MANUALLY VALIDATED / NOT TESTED**.

## 11. Estrutura de diretórios (alvo)

```
my-jarvis/
├─ contracts/        state-machine.json · event-catalog.md · protocol.md (fonte compartilhada)
├─ app/              Electron + React/TS
│  ├─ src/           React/TS: orb/ hud/ panel/ settings/ devconsole/ state/ ipc/
│  └─ electron/      main · preload · windows · menus · supervisor · ipcClient · launch · prefs
├─ service/          Python
│  ├─ pyproject.toml
│  ├─ src/jarvis/    core/ ipc/ storage/ security/ audio/ speech/ ai/ router/ harness/
│  │                 skills/ tools/ memory/ context/ integrations/ presence/ attention/
│  │                 health_data/ tasks/ diagnostics/ channels/
│  └─ tests/         espelha src/ + integration/ + contract/
├─ config/           config.example.json (a config real não é versionada)
├─ docs/             ARCHITECTURE · SECURITY · ROADMAP · DEVELOPMENT · adr/
└─ scripts/          dev, build, test
```

Evitar pastas chamadas `secrets/`, `credentials/` ou `tokens/` no código (o `.gitignore` as bloqueia de propósito).

## 12. Distribuição

Desenvolvimento: código em `D:\JARVIS\Source\my-jarvis`. Produção: **core instalado no SSD** (executável, bootstrap, config crítica, FastCache); dados pesados no HD via `StorageManager`. O build Rust usa `CARGO_TARGET_DIR` no SSD (o exFAT não suporta *hard links* e é lento).

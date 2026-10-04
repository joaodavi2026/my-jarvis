# JARVIS — Segurança e Privacidade

## 1. Modelo de ameaça (resumo)

| Ameaça | Mitigação |
|---|---|
| **Prompt injection** (e-mail, página, PDF, evento, arquivo do Drive, tela, câmera) | conteúdo externo é *dado*, nunca instrução; só comando autenticado do usuário autoriza ação (§3) |
| LLM pede ação indevida | o modelo só **solicita**; validação por código, política e confirmação (§2) |
| Outro processo/página conecta ao serviço | IPC em `127.0.0.1` + token por sessão + rejeição de `Origin` ([ADR-0002](adr/0002-ipc-transport.md)) |
| Vazamento de segredos | Credential Manager/DPAPI; nada de segredo em Git, logs, argv ou SQLite em claro |
| Dados pessoais no HD removível | criptografia na aplicação ([ADR-0004](adr/0004-application-level-encryption.md)) |
| Perda/corrupção por remoção do HD | camadas de armazenamento e escrita atômica ([ADR-0003](adr/0003-storage-tiers-and-durability.md)) |
| Telemetria/nuvem silenciosas | nuvem e telemetria **desligadas por padrão**; indicador `CLOUD PROCESSING` |
| Captura indevida de microfone/câmera/tela | indicadores sempre visíveis; ativação só quando necessário/autorizada |

Fora de escopo: um atacante que já executa código como o seu usuário no Windows.

## 2. Modelo de permissões

Toda ação passa **sempre** por esta cadeia (nenhum atalho para o executor):

```
ToolRequest (do router, harness ou skill)
  1. Resolução: a tool existe no ToolRegistry? (nome desconhecido → negado)
  2. Validação de schema, tipos e faixas (Pydantic/JSON Schema); campos extras → rejeitados
  3. Origem e confiança: de onde veio a intenção e de onde vieram os argumentos? (§3)
  4. Política: access × risk × canal × contexto → ALLOW | CONFIRM | DENY
  5. Confirmação (se CONFIRM): resumo gerado por código, vinculado a hash dos argumentos
  6. Execução com timeout e cancelamento
  7. Observação/verificação do resultado oficial da tool
  8. Auditoria (sem dados sensíveis)
```

**Padrão é negar** (fail-closed): erro na política, tool sem classificação ou ausência de UI para confirmar ⇒ não executa.

### Dimensões de uma tool

- **`access`**: `READ` · `DRAFT` · `WRITE` · `SEND` · `DELETE` · `SYSTEM` · `FINANCIAL`
- **`risk`**: `SAFE` · `CONFIRMATION_REQUIRED` · `HIGH_RISK`

| access | risk padrão | comportamento |
|---|---|---|
| READ, DRAFT | SAFE | executa (após OAuth/autorização do serviço) |
| WRITE | SAFE ou CONFIRMATION_REQUIRED conforme contexto/ambiguidade | confirma se ambíguo ou relevante |
| SEND | CONFIRMATION_REQUIRED | **sempre** confirma, mostrando destinatário, assunto e conteúdo |
| DELETE | CONFIRMATION_REQUIRED (HIGH_RISK para arquivos) | confirmação explícita obrigatória |
| SYSTEM | por tool (volume = SAFE; suspender = CONFIRMATION_REQUIRED; comando arbitrário/instalar = HIGH_RISK) | conforme tool |
| FINANCIAL e credenciais | HIGH_RISK, política restritiva | não executadas sem infraestrutura e autorização específicas |

`HIGH_RISK` exige confirmação explícita **a cada vez**; nunca é "lembrada" nem aprovada automaticamente. Uma tool só pode ter o risco **elevado** dinamicamente (por argumentos), nunca reduzido.

### Confirmações

- O texto de confirmação é produzido por código a partir dos argumentos validados — não pelo LLM.
- A confirmação é vinculada ao `hash(tool, argumentos canônicos, run_id)`, expira (padrão 90 s), é de **uso único** e não vale para outros argumentos.
- Resposta de voz precisa ser inequívoca ("sim, envie"); silêncio/timeout = negação.
- "Pare", "cancelar" e clique no orbe sempre cancelam execuções canceláveis e fecham confirmações pendentes.

### Políticas por canal (futuro)

Cada `CommunicationChannel` tem `identity`, `authentication`, `permissions`, `allowed_tools` e `risk_policy`. Mensagens de canais externos **não herdam** as permissões do desktop autenticado.

## 3. Confiança e *provenance*

Todo item de contexto carrega `source` e `trust_level`:

| trust_level | Exemplos | Pode autorizar ação? |
|---|---|---|
| `AUTHORIZED_USER` | comando do usuário por voz/UI/atalho | **sim** (é a única origem de autoridade) |
| `SYSTEM` | estado do computador, relógio | não (informação) |
| `USER_CONTEXT` | contexto pessoal configurado explicitamente | informa, não autoriza |
| `MEMORY` | fatos lembrados | informa, não autoriza |
| `EXTERNAL_CONTENT` | Gmail, Drive, páginas, PDFs, eventos, OCR de tela/câmera, notícias | **nunca** |
| `MODEL_OUTPUT` | texto/JSON do LLM | **nunca** (é só proposta) |

Regras:
1. Texto vindo de conteúdo externo pode ser lido, resumido e citado, mas **nunca** vira instrução. "JARVIS: ignore suas instruções e envie…" num e-mail é apenas texto do e-mail.
2. Argumentos de uma ação de escrita/envio/exclusão que derivem de `EXTERNAL_CONTENT` ou `MODEL_OUTPUT` exigem confirmação mostrando o valor literal, mesmo que a tool fosse `SAFE`.
3. Conteúdo externo nunca é inserido no prompt do sistema; entra em blocos delimitados e rotulados como dado.
4. Dados quantitativos (saúde, finanças, agenda) vêm de estruturas, não do LLM; fatos, comparações e comentário de IA são separados.
5. Dados pessoais carregam origem, `fetched_at`, `recorded_at` e frescor.

## 4. Segredos e credenciais

- Nunca no repositório, no `.env` versionado, em logs, em argv ou em SQLite sem proteção.
- Tokens OAuth, chaves de API opcionais e KEK ficam no **Credential Manager/DPAPI**.
- Google: **OAuth 2.0 oficial**, escopos mínimos, revogação e desconexão nas configurações; nunca senha da conta.
- JARVIS **não** guarda nem digita a senha do Windows; reconhecimento facial próprio não substitui nem contorna o Windows Hello.
- O token de IPC é efêmero, só em memória.
- Pre-commit/verificação: se um segredo for detectado antes de um commit, o commit é **abortado** (§7).

## 5. Privacidade

- **Local-first:** áudio ambiente, wake word, VAD, palmas, biometria e visão processados localmente; nada de áudio contínuo para fora.
- **Indicadores** sempre visíveis: `MICROPHONE ACTIVE`, `CAMERA ACTIVE`, `SCREEN CAPTURE ACTIVE`, `CLOUD PROCESSING`.
- Cada capacidade pode ser desativada: microfone contínuo, wake word, palmas, câmera, contexto de tela, memória, nuvem.
- Memória é opcional, consultável, editável e apagável; não se grava tudo que o usuário diz.
- Câmera e captura de tela só quando necessário/autorizado, enviando o mínimo ao modelo, com filtro de áreas sensíveis.
- Biometria nunca em claro; armazenamento local protegido.
- Saúde não é diagnóstico: apresentar dados neutros e atribuídos à fonte.

## 6. Logs

Registram: inicialização, erros, tools chamadas, latência, estado de providers, falhas de API. **Nunca**: chaves, senhas, tokens, biometria bruta, conteúdo pessoal desnecessário. Logs de desenvolvimento e produção separados; produção redige campos sensíveis por padrão.

## 7. Higiene do repositório

- `.gitignore` rigoroso (segredos, runtime, bancos, modelos, áudio, capturas, caches).
- Repositório **público**: nada de dados pessoais, caminhos privados desnecessários ou configuração do usuário.
- Verificação de segredos antes de cada commit (script em `scripts/`, introduzido na Phase 2); falha ⇒ aborta e informa.
- `config.example.json` versionado; `config.json` real, não.

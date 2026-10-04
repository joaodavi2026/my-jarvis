# JARVIS

Assistente pessoal de IA **local-first** para Windows: orbe flutuante, voz, automação do Windows,
integrações Google e memória — com privacidade e custo operacional próximo de zero.

> **Status:** em desenvolvimento inicial (fundações). Veja [`docs/ROADMAP.md`](docs/ROADMAP.md).
> Nada de IA/voz está implementado ainda.

## Princípios

- **Local-first:** STT, TTS, LLM, wake word e visão rodam na máquina; nuvem é opcional e desligada por padrão.
- **Sem API de IA paga obrigatória.**
- **O modelo só *solicita* ferramentas;** a aplicação valida, aplica permissões e executa.
- **Código ≠ dados:** este repositório contém só código. Modelos, memória e dados pessoais vivem em `JARVIS_STORAGE_ROOT`, fora do Git.

## Estrutura

```
app/       Tauri 2 + React + TypeScript (orbe, HUD, painel, tray, ciclo de vida)
service/   Serviço Python (storage, IPC, e futuramente STT/TTS/IA/Skills)
config/    config.example.json (template; config real não é versionada)
docs/      ARCHITECTURE, SECURITY, ROADMAP, DEVELOPMENT, ADRs
scripts/   utilitários de desenvolvimento
```

## Documentação

[ARCHITECTURE](docs/ARCHITECTURE.md) · [SECURITY](docs/SECURITY.md) · [ROADMAP](docs/ROADMAP.md) ·
[DEVELOPMENT](docs/DEVELOPMENT.md) · [ADRs](docs/adr/)

## Privacidade

Nenhum dado pessoal, segredo, token, modelo ou banco é versionado. Veja [SECURITY](docs/SECURITY.md).

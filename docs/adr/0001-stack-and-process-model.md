# ADR-0001 — Stack e modelo de processos

- **Status:** aceito (2026-10-04)
- **Contexto:** desktop residente no Windows, com orbe transparente sempre no topo, uso mínimo de CPU/RAM em repouso, e carga pesada de IA/áudio/visão. Hardware: Ryzen 7 5825U, ~15 GB de RAM, sem GPU dedicada.

## Alternativas

| Opção | Prós | Contras |
|---|---|---|
| **A. Tauri 2 (Rust) + React/TS + serviço Python** | UI leve (WebView2), janelas transparentes/tray/atalho/autostart nativos, ecossistema Python para áudio/IA/visão, processo de IA isolado | 3 linguagens; protocolo de IPC a manter |
| B. Tudo em Python (Qt/PySide6) | uma linguagem; menos peças | animações do orbe e transparência mais trabalhosas; UI e IA competem pelo mesmo processo |
| C. Electron + Node + Python | UI web rica | RAM em idle bem maior que Tauri; mesma complexidade multi-processo |
| D. Tudo em Rust | performance, um binário | ecossistema de STT/TTS/visão/IA local bem menos maduro |

## Decisão

**Opção A.** Responsabilidades em [ARCHITECTURE §3](../ARCHITECTURE.md): Rust = shell/supervisor; React = renderização; Python = inteligência e I/O, dono do estado e do registro único de tools.

## Consequências

- O Python é processo filho supervisionado; se cair, o orbe segue vivo em `OFFLINE`.
- Contratos compartilhados (`contracts/`) evitam divergência entre as 3 linguagens.
- Dependências de IA pesadas só entram em fases posteriores, sob demanda.

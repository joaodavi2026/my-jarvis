# ADR-0002 — Transporte de IPC entre shell (Rust) e serviço (Python)

- **Status:** aceito (2026-10-04)
- **Contexto:** o shell precisa de requisição/resposta e de **streaming bidirecional de eventos** com o serviço Python, com baixa latência, depuração simples e superfície de ataque mínima. Outros processos locais do mesmo usuário podem tentar se conectar.

## Alternativas

| Critério | WebSocket localhost | Named pipe | Tauri IPC (Rust-WebView) | stdio do processo filho |
|---|---|---|---|---|
| Segurança | porta TCP visível a processos locais; **exige token** e verificação de Origin | ACL do Windows; nome aleatório; processos do mesmo usuário ainda podem abrir | só dentro do app (não liga ao Python) | **sem porta nem nome**: só o pai tem o pipe |
| Streaming bidirecional | sim, nativo | sim | sim, mas só Rust-UI | sim, mas um único canal |
| Latência | sub-ms em loopback | baixa | baixa | baixa |
| Depuração | excelente (ferramentas padrão; console de dev como 2º cliente) | difícil | boa na UI | ruim (misturado com logs; sem 2º cliente) |
| Complexidade | baixa (`websockets` assíncrono maduro; `tokio-tungstenite`) | média/alta no asyncio do Windows | baixa, mas **não resolve** Rust-Python | baixa, porém frágil (framing, saída contaminada) |
| Outro processo conectar | possível, mitigado por token | possível, mitigado por ACL | n/a | impossível |

## Decisão

1. **Rust-Python:** WebSocket em `127.0.0.1` (porta efêmera) com autenticação por token. Bidirecional, com streaming de eventos, permite um cliente de desenvolvimento adicional (Dev console) e é fácil de testar e depurar. Stdio é descartado como canal principal por fragilidade; named pipe, por custo no asyncio do Windows sem ganho decisivo.
2. **React-Rust:** Tauri IPC (`invoke`/eventos). A WebView **não** conhece o token nem a porta.
3. **Handshake de bootstrap por stdio (uma vez):** o Rust gera o token e o entrega ao filho pelo **stdin**; o filho abre o servidor na porta 0 e informa a porta por **stdout** (uma linha JSON com a porta), nunca o token.

## Requisitos de segurança (todos obrigatórios)

- bind **somente** `127.0.0.1` (nunca `0.0.0.0`); porta dinâmica;
- token de 256 bits via CSPRNG, **novo a cada execução, não persistido**, fora de argv/env/arquivos/logs;
- autenticação no handshake: primeira mensagem `hello` com o token em até 2 s, comparação em tempo constante; falhou → fecha (código 4401) sem processar nada;
- rejeitar qualquer requisição com cabeçalho `Origin` (impede páginas web no navegador de se conectarem);
- **uma única conexão autenticada** por vez; tamanho máximo de mensagem limitado (1 MiB);
- timeouts de handshake e heartbeat; logs nunca contêm o token.

## Risco residual (documentado)

Um processo malicioso **do mesmo usuário** com acesso à memória do Rust/Python ou ao stdin do filho já comprometeu a conta do usuário; este desenho não defende contra isso. Defende contra: outros usuários, páginas web, varredura de portas locais e clientes sem token.

## Consequências

- Protocolo versionado em [`contracts/protocol.md`](../../contracts/protocol.md).
- Testes de integração: sem token, token errado, com `Origin`, segunda conexão, mensagem grande, reconexão.
- Trocar o transporte no futuro exige alterar só a camada `ipc` (o envelope é independente do transporte).

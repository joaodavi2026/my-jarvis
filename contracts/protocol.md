# Protocolo IPC Rust ⇄ Python (v1)

Transporte: WebSocket em `127.0.0.1` (ver [ADR-0002](../docs/adr/0002-ipc-transport.md)). O envelope é independente do transporte.

## Bootstrap

1. Rust gera token (256 bits, CSPRNG) e inicia o serviço Python.
2. Rust escreve o token no **stdin** do filho (uma linha) e fecha o stdin.
3. O serviço liga em `127.0.0.1:0` e escreve em **stdout** uma linha JSON: `{"ready":true,"port":<n>,"protocol":1}`. O token nunca é impresso.
4. Rust conecta em `ws://127.0.0.1:<port>/` **sem** cabeçalho `Origin`.

## Handshake

Primeira mensagem do cliente (em até 2 s): `{"v":1,"kind":"req","id":"1","type":"hello","payload":{"token":"..."}}`.
Sucesso: resposta `res` com `{"ok":true,"server":"jarvis-service","protocol":1}`. Falha ou timeout: fecha com código **4401**. Segunda conexão simultânea: fecha com **4409**. Mensagem > 1 MiB: fecha com **1009**.

## Envelope

```json
{ "v": 1, "kind": "req|res|evt", "id": "string?", "type": "dominio.nome", "ts": "ISO-8601", "payload": {} }
```

- `req`: exige `id`; recebe exatamente um `res` com o mesmo `id` (`payload.ok`, `payload.error?`).
- `evt`: unidirecional, sem `id`; `payload.correlation_id` opcional.
- `ping`/`pong` a cada 10 s; sem pong em 30 s ⇒ o lado detecta falha e reconecta/reinicia.
- Versão desconhecida ou tipo desconhecido em `req` ⇒ `res` com `ok:false, error:"unsupported"`; em `evt` ⇒ ignorado.

## Erros (`payload.error`)

`unauthorized` · `unsupported` · `invalid_payload` · `timeout` · `internal` · `storage_unavailable`.

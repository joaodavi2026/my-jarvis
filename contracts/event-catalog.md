# Catálogo de eventos (v1)

Formato: `dominio.evento` — origem → destinos — payload (campos principais). Eventos marcados **UI** são encaminhados ao shell.
Todos podem carregar `correlation_id`. Frequência alta ⇒ fila limitada com descarte do mais antigo.

## Estado e ciclo de vida
- `state.changed` **UI** — core → UI — `{state, previous, substage?, reason?}`
- `service.ready` / `service.stopping` **UI** — core
- `health.changed` **UI** — diagnostics — `{component, status}`
- `capability.changed` **UI** — CapabilityGraph — `{capability, status, reason?}`

## Ativação
- `activation.orb_clicked` — shell → core
- `activation.hotkey_pressed` — shell → core
- `activation.wake_word_detected` — audio → core
- `activation.clap_detected` — audio → core
- `activation.cancelled` — qualquer → core — `{source}`

## Áudio e fala
- `listening.started` / `listening.stopped` **UI**
- `audio.level` **UI** (~20 Hz, descartável) — `{level: 0..1}`
- `speech.detected` / `speech.ended` — VAD
- `stt.partial` / `stt.transcription_ready` **UI** — `{text, language}`
- `tts.started` / `tts.finished` / `tts.interrupted` **UI**

## Raciocínio e execução
- `router.matched` / `router.missed`
- `ai.thinking` **UI** — `{substage?}`
- `plan.created` / `plan.step_updated` **UI**
- `permission.evaluated` — `{tool, decision}` (sem argumentos sensíveis)
- `confirmation.requested` **UI** — `{id, summary, risk, expires_at}`
- `confirmation.answered` — UI → core — `{id, approved}`
- `tool.started` / `tool.completed` / `tool.failed` **UI** — `{tool, label, verified?}`

## Privacidade
- `privacy.changed` **UI** — `{microphone, camera, screen, cloud}` (booleanos de atividade)

## Armazenamento
- `storage.found` / `storage.validated` / `storage.missing` / `storage.removed` / `storage.reconnected` / `storage.low_space` / `storage.write_error` / `storage.recovery`
- `storage.status_changed` **UI** — `{mode: NORMAL|DEGRADED, reason?}`

## Erros
- `error.occurred` **UI** — `{code, message}` (mensagem compreensível; sem dados sensíveis)

## Shell → core
- `shell.window_moved`, `shell.menu_action {action}`, `shell.quit_requested`

## Reservados (fases futuras)
`presence.*`, `context.opportunity`, `attention.item`, `briefing.*`, `memory.*`, `task.*`, `integration.*`.

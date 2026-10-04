# JARVIS — Desenvolvimento

## Pré-requisitos (Windows 10/11)

Node 20+, Rust (toolchain MSVC) + VS Build Tools, WebView2, Python 3.13, Git. Nenhuma dependência de IA é necessária nas fases iniciais.

## Caminhos

- **Código:** `D:\JARVIS\Source\my-jarvis` (este repositório). Detectado pelo build/projeto, nunca fixo no código.
- **Runtime/dados pesados:** `JARVIS_STORAGE_ROOT` (hoje `D:\JARVIS`). Nunca versionado.
- **SSD (core/bootstrap/config crítica):** `%LOCALAPPDATA%\JARVIS`.
- **Build Rust:** defina `CARGO_TARGET_DIR=%LOCALAPPDATA%\JARVIS\build\target` (o exFAT não suporta hard links e é lento).

## Convenções

- Commits pequenos e semânticos (`feat(storage): ...`, `test(...)`, `docs(...)`, `fix(...)`).
- Não commitar segredos, dados pessoais, modelos, bancos, logs, áudio ou capturas.
- Não usar nomes de pasta `secrets/`, `credentials/`, `tokens/` no código-fonte.
- Testes sem rede e sem APIs pagas; usar fakes.
- Antes de qualquer operação Git destrutiva, verificar diretório e escopo (`git rev-parse --show-toplevel`).
- No exFAT o Git exige `safe.directory` para esta pasta.

## Execução e testes

Os comandos concretos são adicionados junto de cada fase (Python: `pytest`; TS: `vitest`; Rust: `cargo test`).

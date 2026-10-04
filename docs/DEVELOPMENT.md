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

## Python (serviço)

```
py -3.13 -m venv %LOCALAPPDATA%\JARVIS\venv          (venv no SSD, fora do exFAT)
%LOCALAPPDATA%\JARVIS\venv\Scripts\python -m pip install pytest pytest-asyncio
cd service && %LOCALAPPDATA%\JARVIS\venv\Scripts\python -m pytest
```

Diagnóstico de armazenamento (somente leitura por padrão):
`python scripts/storage_check.py --internal-root <pasta>`; `--bind <guid>` adota o volume (cria a raiz de runtime).

Nota: o app desktop do Claude virtualiza `%LOCALAPPDATA%` em alguns caminhos; o JARVIS instalado não é afetado.

## Bloqueio conhecido: Smart App Control e o compilador Rust

Em máquinas com o **Smart App Control** ativo, o Windows pode impedir o `rustc.exe` de carregar o `std-*.dll` (não assinado): `rustc -vV` falha com o código `0xC0E90002` e o Code Integrity registra o evento 3077. Sem um compilador Rust funcional não é possível compilar o shell Tauri (`app/src-tauri`). Alterar essa configuração de segurança é decisão do usuário (e o Smart App Control, uma vez desligado, não pode ser religado sem reinstalar o Windows). Enquanto isso, o frontend (`npm test`) e o serviço Python (`pytest`) são desenvolvidos e testados normalmente.

## Serviço Python (Phase 5)

`python -m jarvis` (executar a partir de `service/src`, ou com `PYTHONPATH`): lê o token da primeira linha do stdin, imprime uma linha JSON `{"ready":true,"port":N,"protocol":1}` no stdout e encerra quando o stdin fecha. Dependência de runtime: `websockets` (BSD-3, local, sem custo/API key).

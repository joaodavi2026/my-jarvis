# ADR-0005 — Shell desktop em Electron (substitui o shell da ADR-0001)

- **Status:** aceito (2026-10-04). A parte de shell da [ADR-0001](0001-stack-and-process-model.md) é substituída; o resto (React/TS, Python, contratos) segue valendo.
- **Contexto:** o Smart App Control (SAC) está em modo de bloqueio neste PC e o usuário não quer desativá-lo.

## Evidências (medidas nesta máquina)

- `rustc.exe` não consegue carregar `std-*.dll` (sem assinatura e sem reputação): código `0xC0E90002` e evento 3077 do Code Integrity.
- Um `hello.exe` compilado pelo `cl.exe` assinado da Microsoft também é **bloqueado**: qualquer executável novo e sem assinatura confiável é negado. Logo, builds locais do Tauri são inviáveis (scripts de build, DLLs de macros e o `.exe` final seriam bloqueados).
- O `electron.exe` oficial 41.7.1 (sem assinatura, mas com reputação) **executa** com o SAC ligado; uma cópia renomeada executa; uma cópia com 1 byte alterado é bloqueada.
- POC: janela transparente, sem moldura e always-on-top; cerca de 120 MB de RAM privada em idle (4 processos), 0,35 a 0,43 s de startup a quente, 344 MB de runtime.

## Alternativas

| Opção | Resultado |
|---|---|
| Tauri com build local | inviável sob SAC |
| Tauri com CI e assinatura | exige certificado de CA confiável (custo recorrente; Azure Artifact Signing só atende indivíduos nos EUA e Canadá); sem desenvolvimento local rápido |
| Desligar o SAC | vetado pelo usuário |
| **Electron (escolhido)** | roda sem alterar a segurança, custo zero, desenvolvimento local rápido |

## Decisão

Shell em **Electron**, escrito em TypeScript (processo principal compilado com `tsc`, sem binários novos). Frontend React/TS, contratos e serviço Python permanecem. O código Tauri fica arquivado em `feature/tauri-shell`, sem merge.

## Regras que decorrem do SAC

1. Usar o `electron.exe` oficial **sem modificações** e com **versão fixada**; versões novas têm hash novo e podem demorar a ganhar reputação.
2. Sem módulos nativos do Node que exijam compilação; o trabalho nativo vai para o serviço Python (ou para binários já assinados).
3. Empacotadores que editam o exe (ícone, versão) e instaladores novos geram binários bloqueáveis. A distribuição inicial é uma pasta com o exe oficial renomeado e o app em JS.

## Segurança do shell

`contextIsolation`, `sandbox`, sem Node no renderer, sem navegação nem pop-ups, CSP no HTML de produção, API do preload mínima e explícita, validação da origem de cada mensagem IPC e allow-list do que o renderer pode enviar ao serviço. O token e a porta do serviço **nunca** chegam ao renderer.

## Consequências

Mais RAM em idle (cerca de 120 MB privados) e mais disco (344 MB) que o Tauri. Reavaliar o Tauri se houver certificado de assinatura ou uma forma oficial de alternar o SAC.

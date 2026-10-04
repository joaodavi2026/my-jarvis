# ADR-0006 — Agentes de código como providers opcionais

- **Status:** aceito (2026-10-04)
- **Contexto:** o JARVIS é um assistente pessoal completo (voz, orbe, Windows, Google, memória, briefings, visão e presença), com **IA local como padrão**. Ele também deve poder delegar trabalho de programação ("trabalhe no projeto X e corrija esse bug") a agentes de código.

## Decisão

- Criar uma abstração própria, `CodingAgentProvider`, separada de `AIProvider` (que é o raciocínio do assistente). As implementações são **opcionais e desligadas por padrão**: `ClaudeCodeProvider` e, no futuro, `CodexProvider` e outros. Nenhuma é obrigatória e o núcleo não depende de nenhuma.
- A delegação é uma Skill/Tool como qualquer outra: passa pelo Permission Layer (escrever no computador exige confirmação clara do projeto e do pedido), roda como `AgentRun` rastreado (estado terminal garantido, cancelável) e seu resultado é conteúdo **não confiável** (`EXTERNAL_CONTENT`): a saída do agente nunca autoriza novas ações.
- Segurança do provider: ambiente do processo filho sem variáveis de API de IA herdadas, sem `--dangerously-skip-permissions` por padrão e diretório de trabalho restrito ao projeto escolhido.
- Antes de implementar: verificar os termos de uso do provedor para uso automatizado por assinatura e o custo, sem custo recorrente obrigatório.

## Consequências

Quando o Agentic Harness e o ToolRegistry existirem (fases 11 a 13), o provider entra por registro, sem alterar o núcleo. Fica fora do escopo das fases atuais.

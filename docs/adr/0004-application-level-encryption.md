# ADR-0004 — Criptografia na camada da aplicação

- **Status:** aceito (2026-10-04)
- **Contexto:** o HD é exFAT, removível e sem criptografia nativa. Decisão do usuário: **não** formatar, converter nem ativar BitLocker To Go; proteger dados sensíveis na aplicação.

## Decisão

- **Algoritmo:** AES-256-GCM (autenticada). Nonce aleatório de 96 bits por mensagem; formato versionado (magic, versão, key_id, nonce, ciphertext com tag); *associated data* liga o dado ao seu caminho lógico/categoria (evita troca de arquivos).
- **Hierarquia (envelope):** uma chave mestra (KEK) protege chaves de dados (DEK) por categoria (dados pessoais, memória etc.). Rotação por troca de DEK com recriptografia.
- **Custódia da KEK:** **nunca no HD**. Protegida pelo Windows (DPAPI no escopo do usuário, via Credential Manager ou blob DPAPI no SSD, fora do Git). Proibido: chave embutida, `key.txt`, derivação de valor previsível.
- **O que criptografar:** dados pessoais/sensíveis (memória, contexto do usuário, saúde/fitness, cache de Gmail/Drive, histórico). **Não** criptografar modelos públicos de IA (overhead sem benefício).
- **Segredos** (tokens OAuth, API keys opcionais) ficam no Credential Manager/DPAPI, nunca em SQLite em texto claro.
- **Biblioteca:** `cryptography` (pyca), pública e auditada; nada de criptografia caseira.
- **Limitações assumidas:** quem executa código como o usuário logado consegue usar a DPAPI; backups criptografados exigem procedimento de recuperação da KEK (a definir antes de qualquer backup real).

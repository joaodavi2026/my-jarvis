# ADR-0003 — Camadas de armazenamento e durabilidade

- **Status:** aceito (2026-10-04)
- **Contexto (medido nesta máquina):** HD externo **HD JD**, **exFAT**, **HDD USB** (~298 GB), removível; SSD interno NVMe com NTFS. O exFAT **não tem journaling, ACLs nem criptografia nativa**, e não suporta *hard links*/symlinks. HDD USB é lento para carregar modelos.

## Decisões

1. **Identidade do volume:** GUID do volume (mais label e filesystem esperados), nunca só a letra. Outro disco em `D:` é recusado.
2. **Bancos SQLite críticos ficam no SSD:** bootstrap, configuração, estado operacional, índices necessários à recuperação. **WAL não torna SQLite seguro contra remoção física no exFAT**, então nenhum banco crítico fica no HD.
3. **No HD:** modelos, documentos, logs, histórico e dados pesados *reconstruíveis*, backups locais. Se a memória de longo prazo precisar residir no HD: escrita atômica (arquivo temporário, `fsync`, *rename*), arquivos de dados de apenas-acréscimo com checksum, recuperação a partir do SSD e detecção de arquivo truncado na abertura. Cada abordagem terá teste de durabilidade com injeção de falha antes de ser adotada.
4. **Modo degradado (`STORAGE_DEGRADED`):** HD ausente → sem crash, sem apagar configuração, sem recriar memória no SSD, sem baixar modelos no SSD; recursos dependentes retornam `STORAGE_UNAVAILABLE`.
5. **Hot reconnect:** REMOVED, DEGRADED, AVAILABLE, VALIDATE, reabrir bancos/índices, restaurar serviços, NORMAL.
6. **Validação** não destrutiva: volume correto, diretório raiz, leitura, escrita (arquivo de teste pequeno, removido em seguida), espaço livre, filesystem.
7. **Modelos no HDD:** `Models` continua no HD. Suporte futuro (nunca automático) a `MODEL STORAGE LOCATION` e `FAST MODEL CACHE` no SSD por decisão do usuário, com limite configurável.
8. **Caminhos:** sempre via `StorageManager.get_path(StorageCategory.X)`; `JARVIS_STORAGE_ROOT` resolvido em runtime; `PROJECT_ROOT` separado.
9. **Migração futura de volume:** validar destino, calcular espaço, copiar, verificar, trocar config, verificar de novo, remover o original só com confirmação.
10. **Backup real** exige outro dispositivo; `Backups` no mesmo HD é só cópia local.
11. **Build:** `CARGO_TARGET_DIR` e caches de build no SSD.

## Consequências

Um componente a mais (StorageManager) e uma abstração de volume (`VolumeProvider`) com `FakeVolumeProvider`, para testar ausência, troca de letra, disco errado, somente leitura, espaço baixo, desconexão e reconexão **sem desconectar o HD fisicamente**.

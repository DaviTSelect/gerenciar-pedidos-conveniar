# Changelog

## [1.1.7] - 2026-11-09

### Alterado
- Altura da janela aumentada em 60px (745→795)
- Notas de release removem referência ao `.env`

## [1.1.6] - 2026-11-09

### Alterado
- Credenciais (usuário/senha) inseridas diretamente na interface, sem arquivo `.env`
- Removido suporte a `.env` e `.env.example` do projeto

## [1.1.5] - 2026-11-09

### Alterado
- Tentativa de migração para `.env` (revertida em 1.1.6)

## [1.1.4] - 2026-11-09

### Corrigido
- Auto-update exibia indicador cinza: `instalar()` lia campo `digest` que a API do GitHub não fornece
- Fix: SHA-256 lido do arquivo `.sha256` publicado junto com o `.exe` na release
- Adicionado `tests/test_auto_update.py` com 28 testes cobrindo todos os cenários

## [1.1.3] - 2026-11-09

### Adicionado
- Opção "Ocultar janela Chrome" (modo headless)
- Supressão do console do chromedriver (`CREATE_NO_WINDOW`)

## [1.1.2] - 2026-11-09

### Adicionado
- Interface reescrita: layout dois painéis, ícones vetoriais, seletor de 3 abas
- Worker de atualização automática com indicador colorido no cabeçalho

## [1.0.0] - 2026-11-09

### Adicionado
- Interface gráfica PySide6 para seleção de planilha e ação
- Automação Selenium para Reabrir, Cancelar e Encerrar pedidos no Conveniar
- Escrita imediata do status na planilha ao processar cada pedido
- Coluna "Status" marcada como "ok" apenas após conclusão completa
- Retomada automática: linhas com Status=ok são ignoradas ao reiniciar
- Atualização automática via GitHub Releases
- Logs passo a passo no painel de progresso

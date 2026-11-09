# Changelog

## [1.0.0] - 2026-11-09

### Adicionado
- Interface gráfica PySide6 para seleção de planilha e ação
- Automação Selenium para Reabrir, Cancelar e Encerrar pedidos no Conveniar
- Escrita imediata do Item PT na planilha ao encontrar
- Coluna "Status" marcada como "ok" apenas após conclusão completa
- Retomada automática: linhas com Status=ok são ignoradas ao reiniciar
- Carregamento de credenciais via arquivo `.env` (sem dependências externas)
- Atualização automática via GitHub Releases
- Logs passo a passo no painel de progresso

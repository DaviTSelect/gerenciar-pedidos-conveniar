# Gerenciar Pedidos Conveniar — Guia do Agente

## O que faz

Automatiza o processamento em lote de pedidos de pagamento no sistema Conveniar (Facto), executando uma das três ações em cada pedido:

- **Reabrir** — reabre um pedido encerrado ou cancelado
- **Cancelar** — cancela um pedido em aberto
- **Encerrar** — encerra um pedido aprovado

## Como usar

1. Preencha a planilha `planilha_modelo.xlsx` com os números dos pedidos na coluna **Nº Pedido** (formato `NNNNN/AAAA`)
2. Execute `GerenciarPedidos.exe`
3. Informe usuário e senha (ou configure no `.env`)
4. Selecione a planilha e a ação desejada
5. Clique em **Processar**

## Estrutura da planilha

| Coluna   | Preenchido por | Descrição                          |
|----------|----------------|------------------------------------|
| Nº Pedido | Usuário        | Número do pedido (ex: 12345/2026)  |
| Item PT   | Automação      | Código do item do Plano de Trabalho |
| Status    | Automação      | `ok` quando processado com sucesso  |

## Retomada após interrupção

Linhas com `Status = ok` são ignoradas ao reprocessar. Basta executar novamente com a mesma planilha.

## Credenciais (.env)

Crie um arquivo `.env` na mesma pasta do `.exe`:

```
CONVENIAR_USERNAME=seu_usuario
CONVENIAR_PASSWORD=sua_senha
```

## Atualização automática

O programa verifica a versão mais recente em `https://github.com/DaviTSelect/gerenciar-pedidos-conveniar/releases` a cada inicialização. Se houver nova versão, atualiza automaticamente.

## Estrutura do projeto

```
src/pedidos/
  config.py       — seletores XPath e configurações
  automacao.py    — lógica de automação Selenium
  interface.py    — interface gráfica PySide6
  auto_update.py  — atualização automática via GitHub
  version.py      — versão atual do app
  main.py         — ponto de entrada
main.py           — entrypoint raiz
GerenciarPedidos.spec — spec PyInstaller
builder.bat       — script de build
planilha_modelo.xlsx  — modelo de planilha
```

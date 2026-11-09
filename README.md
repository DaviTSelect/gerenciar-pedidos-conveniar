# Processamento de pedidos

Aplicativo Windows com PySide6 para selecionar uma planilha Excel e processar os
pedidos, em sequência, no Conveniar de produção. A planilha deve conter a coluna
`Nº Pedido`.

## Preparação

No PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

O Selenium Manager tenta localizar/preparar o ChromeDriver automaticamente. O
navegador é aberto visivelmente.

## Configuração da tela

Antes de processar, preencha os XPath dos três botões finais em
`pedidos/config.py`. Os nomes exibidos no listbox são Reabrir, Cancelar e Encerrar;
os XPath ainda precisam ser identificados na página de produção. O painel bloqueia
a automação se a ação escolhida não tiver XPath.

O login e os XPath da consulta, filtros, abertura do pedido, estornos e
lançamentos foram montados a partir do HTML e do script fornecidos. Esses elementos
devem ser testados no ambiente autorizado antes de executar a planilha completa.

O login é feito uma vez por execução. Os pedidos são processados sequencialmente,
em lotes de uma linha (`QUANTIDADE_LINHAS_PARA_PROCESSAMENTO = 1`), sem pausas
para confirmação no terminal. Use o botão "Parar após o pedido atual" para solicitar
a interrupção do processamento.

Ao reabrir, se a pesquisa mostrar `Nenhum registro encontrado.`, o pedido é tratado
como já reaberto: o status `ok` é salvo na planilha, sem abrir o pedido novamente.

Usuário e senha são solicitados no painel; a senha fica mascarada e não é salva em
arquivo. O ambiente configurado é `facto.conveniar.com.br`.

Consulte [CONTEXTO_PROJETO.md](./CONTEXTO_PROJETO.md) para o fluxo detalhado,
decisões e pendências atuais.

# ShopFlow - Grupo 2404826

Marketplace fictício com microsserviços e arquitetura orientada a eventos.

## Descrição

O **ShopFlow** simula um e-commerce moderno dividido em serviços independentes. A comunicação entre eles acontece por **eventos** usando **RabbitMQ** como broker de mensagens. Este repositório contém a infraestrutura do **Módulo 2**, o fluxo completo de eventos do **Módulo 3** e o **dashboard dinâmico** do **Módulo 4**.

## Tecnologias usadas

- Python 3.11
- FastAPI + Uvicorn
- Pydantic v2
- RabbitMQ (com painel de gerenciamento)
- PostgreSQL + SQLAlchemy
- Streamlit
- Docker e Docker Compose
- pika (cliente RabbitMQ)

## Estrutura do projeto

```
shopflow-grupo-Z/
├── docker-compose.yml
├── .env.example
├── servicos/          # APIs reais: pedido, pagamento, logistica
├── mocks/             # Simulações: antifraude e catálogo
├── gerador/           # Script de carga (gerar.py)
├── dashboard/         # Interface Streamlit
└── docs/              # Documentação de arquitetura
```

## Como executar

### Pré-requisitos

1. Instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/) no seu computador.
2. Certifique-se de que o Docker está rodando (ícone ativo na bandeja do sistema).
3. Clone este repositório:

```bash
git clone <url-do-repositorio>
cd shopflow-grupo-Z
```

### Passo a passo

1. **Copie o arquivo de variáveis de ambiente:**

```bash
cp .env.example .env
```

No Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

2. **Suba todos os containers:**

```bash
docker-compose up --build
```

> **Observação:** Em versões mais recentes do Docker, o comando pode ser `docker compose up --build` (sem hífen). Se `docker-compose` não funcionar na sua máquina, use essa alternativa.

3. **Aguarde** todos os serviços iniciarem. Você verá logs do RabbitMQ, dos serviços FastAPI, dos mocks e do dashboard.

4. **Acesse os endpoints** listados abaixo.

Para parar o projeto, pressione `Ctrl+C` no terminal e depois execute:

```bash
docker-compose down
```

## URLs úteis

| Recurso | URL |
|---------|-----|
| Pedido (health) | http://localhost:8001/health |
| Pagamento (health) | http://localhost:8002/health |
| Logística (health) | http://localhost:8003/health |
| Dashboard Streamlit | http://localhost:8050 |
| Pedido (metrics) | http://localhost:8001/metrics |
| Pagamento (metrics) | http://localhost:8002/metrics |
| Logística (metrics) | http://localhost:8003/metrics |
| RabbitMQ Management | http://localhost:15672 |

### Login do RabbitMQ

- **Usuário:** `guest`
- **Senha:** `guest`

## O que foi implementado no Módulo 2

- **Infraestrutura Docker** com 10 containers: RabbitMQ, 3 bancos PostgreSQL, 3 serviços FastAPI, 2 mocks e dashboard.
- **Endpoints `/health`** nos três serviços reais, retornando status e nome do serviço.
- **Esqueletos** de `producer.py`, `consumer.py` e `models.py` (com `EnvelopeEvento` e `PayloadBase`) prontos para o Módulo 3.
- **Mock Antifraude:** consome `pedido.criado` e publica `pedido.aprovado_fraude` (~90%) ou `pedido.bloqueado_fraude` (~10%).
- **Mock Catálogo:** consome `pedido.confirmado` e publica `estoque.atualizado`.
- **Exchanges topic** declaradas para todos os domínios de eventos.
- **Dashboard Streamlit** com título, mensagem de construção e lista de serviços.
- **Documentação** em `docs/arquitetura.md`.

## Módulo 3 — Serviços e Comunicação

No **Módulo 3** o fluxo completo de eventos foi implementado. Ao criar um pedido via API, o sistema percorre automaticamente toda a saga.

### O que foi implementado

- **POST /pedidos** e **GET /pedidos/{pedido_id}** no serviço de Pedido
- **Persistência** com SQLAlchemy em cada banco PostgreSQL
- **Consumers** em thread separada em cada serviço real
- **Saga orquestrada** pelo serviço de Pedido (confirma ou cancela conforme pagamento e antifraude)
- **Idempotência** via tabela `eventos_processados` em cada serviço
- **Validação Pydantic** de todos os envelopes e payloads
- **Gerador de carga** em `gerador/gerar.py`
- **Mocks atualizados** com payloads conforme especificação

### Como funciona a saga

1. Cliente chama `POST /pedidos` → Pedido salva no banco e publica `pedido.criado`
2. **Em paralelo:**
   - Mock Antifraude analisa e publica `pedido.aprovado_fraude` ou `pedido.bloqueado_fraude`
   - Serviço Pagamento cobra e publica `pagamento.aprovado` ou `pagamento.recusado`
3. Serviço Pedido aguarda **ambas** as respostas:
   - Se pagamento recusado **ou** fraude bloqueada → publica `pedido.cancelado`
   - Se ambos aprovados → publica `pedido.confirmado`
4. Serviço Logística consome `pedido.confirmado` → publica `pedido.despachado` e, após 5–15 s, `pedido.entregue`
5. Mock Catálogo consome `pedido.confirmado` → publica `estoque.atualizado`

O mesmo `correlation_id` acompanha todos os eventos do fluxo.

### Como criar um pedido manualmente

```bash
curl -X POST http://localhost:8001/pedidos \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_id": "0fa85f64-5717-4562-b3fc-2c963f66afa6",
    "itens": [
      {
        "produto_id": "1fa85f64-5717-4562-b3fc-2c963f66afa6",
        "quantidade": 2,
        "preco_unitario": 99.90
      }
    ],
    "forma_pagamento": "pix",
    "endereco_entrega": {
      "cep": "01310-100",
      "cidade": "Sao Paulo",
      "uf": "SP"
    }
  }'
```

No PowerShell:

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8001/pedidos -ContentType "application/json" -Body '{"cliente_id":"0fa85f64-5717-4562-b3fc-2c963f66afa6","itens":[{"produto_id":"1fa85f64-5717-4562-b3fc-2c963f66afa6","quantidade":2,"preco_unitario":99.90}],"forma_pagamento":"pix","endereco_entrega":{"cep":"01310-100","cidade":"Sao Paulo","uf":"SP"}}'
```

### Como consultar um pedido

Substitua `{pedido_id}` pelo ID retornado na criação:

```
GET http://localhost:8001/pedidos/{pedido_id}
```

O status evolui: `criado` → `confirmado` ou `cancelado` → `despachado` → `entregue`.

### Como rodar o gerador de carga

Instale Python 3.11 localmente e as dependências:

```bash
pip install -r gerador/requirements.txt
python gerador/gerar.py --total 10 --taxa 2
```

- `--total`: quantidade de pedidos a criar
- `--taxa`: pedidos por segundo (padrão: 1)

Saída esperada:

```
[gerador] pedido criado pedido_id=... correlation_id=...
```

### Como validar os logs

Com `docker compose up --build` rodando, observe os logs. Fluxo de sucesso:

```
[pedido] pedido.criado publicado correlation_id=...
[antifraude] pedido.aprovado_fraude publicado correlation_id=...
[pagamento] pagamento.aprovado publicado correlation_id=...
[pedido] pedido.confirmado publicado correlation_id=...
[logistica] pedido.despachado publicado correlation_id=...
[logistica] pedido.entregue publicado correlation_id=...
[catalogo] estoque.atualizado publicado correlation_id=...
```

Fluxos de cancelamento também são normais (~20% pagamento recusado, ~10% fraude bloqueada).

### Como criar a tag modulo-3

```bash
git add .
git commit -m "modulo-3: fluxo completo de eventos e saga"
git tag modulo-3
git push origin main --tags
```

## Módulo 4 — Dashboard

O **Módulo 4** adiciona um dashboard visual e dinâmico em **http://localhost:8050** com 3 abas.

### Arquitetura do dashboard

O dashboard **não acessa os bancos PostgreSQL** diretamente. Ele consulta os microsserviços via HTTP:

- `GET /health` — status operacional
- `GET /metrics` — métricas e KPIs

Dentro do Docker, o dashboard usa:

- `http://pedido:8001`
- `http://pagamento:8002`
- `http://logistica:8003`

### Abas do dashboard

1. **Saúde dos Serviços** — status OK/Fora, eventos publicados, taxa de erro, últimos 10 eventos
2. **Comunicação ao Vivo** — throughput por minuto, tabela de pedidos recentes, contadores
3. **KPIs de Negócio** — GMV, taxa de aprovação, conversão, bloqueio antifraude, entregues no prazo, gráfico GMV/hora

O dashboard atualiza automaticamente a cada **5 segundos** (`streamlit-autorefresh`).

### Como ver os números mudarem

1. Suba o projeto: `docker compose up --build`
2. Em outro terminal, rode o gerador:

```bash
python gerador/gerar.py --total 30 --taxa 2
```

3. Abra http://localhost:8050 e observe os contadores e gráficos atualizando

### Como validar os KPIs

| KPI | Onde verificar |
|-----|----------------|
| GMV | Aba 3 — soma dos pedidos confirmados |
| Taxa de aprovação | Aba 3 — dados do serviço Pagamento |
| Taxa de conversão | Aba 3 — confirmados / criados |
| Bloqueio antifraude | Aba 3 — cancelados por fraude |
| Entregues no prazo | Aba 3 — dados do serviço Logística |

### Como criar a tag modulo-4

```bash
git add .
git commit -m "modulo-4: dashboard"
git tag modulo-4
git push origin main --tags
```

Se a tag já existir localmente:

```bash
git tag -d modulo-4
git tag modulo-4
git push origin main --tags
```

## Comandos Git para entrega (Módulo 2)

```bash
git add .
git commit -m "modulo-2: infraestrutura e mocks"
git tag modulo-2
git push origin main --tags
```

## Documentação adicional
Consulte [docs/arquitetura.md](docs/arquitetura.md) para entender a arquitetura completa, os eventos, o dashboard e os KPIs.

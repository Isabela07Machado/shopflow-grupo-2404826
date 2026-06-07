# ShopFlow - Grupo 2404826

Marketplace fictício com microsserviços e arquitetura orientada a eventos.

## Descrição

O **ShopFlow** simula um e-commerce moderno dividido em serviços independentes. A comunicação entre eles acontece por **eventos** usando **RabbitMQ** como broker de mensagens. Este repositório contém a infraestrutura do **Módulo 2**: Docker, bancos PostgreSQL, três APIs FastAPI, dois mocks em Python e um dashboard inicial em Streamlit.

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

## Comandos Git para entrega

```bash
git add .
git commit -m "modulo-2: infraestrutura e mocks"
git tag modulo-2
git push origin main --tags
```

## Documentação adicional

Consulte [docs/arquitetura.md](docs/arquitetura.md) para entender a arquitetura completa, os eventos e a evolução prevista no Módulo 3.

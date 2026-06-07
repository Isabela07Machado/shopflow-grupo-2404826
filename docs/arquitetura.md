# Arquitetura do ShopFlow — Grupo 2404826

## 1. Visão geral

O **ShopFlow** é um marketplace fictício construído com **microsserviços** e **arquitetura orientada a eventos**. Cada serviço é responsável por uma parte do fluxo de compra e se comunica de forma assíncrona por meio do **RabbitMQ**.

```
Cliente / Dashboard
        |
        v
+------------------+     eventos      +------------------+
|  Serviço Pedido  | <--------------> |     RabbitMQ     |
+------------------+                  +------------------+
        |                                      ^
        v                                      |
+------------------+                           |
| Serviço Pagamento| <-------------------------+
+------------------+
        |
        v
+------------------+
|Serviço Logística |
+------------------+

Mocks: Antifraude e Catálogo (simulam serviços externos)
```

No **Módulo 2**, o foco é a infraestrutura: containers Docker, bancos PostgreSQL separados, broker de mensagens, endpoints de saúde (`/health`) e mocks básicos aguardando eventos.

## 2. Por que RabbitMQ?

O **RabbitMQ** foi escolhido porque:

- Suporta o padrão **publish/subscribe** com exchanges do tipo **topic**, ideal para roteamento por tipo de evento (ex.: `pedido.criado`).
- Garante **desacoplamento** entre serviços: quem publica não precisa conhecer quem consome.
- Oferece **painel de gerenciamento** (porta 15672) para visualizar filas, exchanges e mensagens durante o desenvolvimento.
- É amplamente usado em projetos acadêmicos e profissionais, com boa documentação e integração com Python via biblioteca **pika**.

## 3. Função de cada serviço

| Serviço | Tipo | Responsabilidade |
|---------|------|------------------|
| **Pedido** | Real (FastAPI) | Criar pedidos, confirmar compras e orquestrar o fluxo principal |
| **Pagamento** | Real (FastAPI) | Processar cobranças e informar aprovação ou recusa |
| **Logística** | Real (FastAPI) | Despachar e registrar entrega dos pedidos |
| **Antifraude** | Mock | Simular análise de risco após criação do pedido |
| **Catálogo** | Mock | Simular atualização de estoque após confirmação |

## 4. Eventos publicados e consumidos

### Pedido (`pedido.eventos`)

| Evento | Publica | Consome |
|--------|---------|---------|
| `pedido.criado` | Pedido | Antifraude (mock) |
| `pedido.confirmado` | Pedido | Catálogo (mock) |
| `pedido.cancelado` | Pedido | — |

### Pagamento (`pagamento.eventos`)

| Evento | Publica | Consome |
|--------|---------|---------|
| `pagamento.aprovado` | Pagamento | Logística |
| `pagamento.recusado` | Pagamento | Pedido |

### Logística (`logistica.eventos`)

| Evento | Publica | Consome |
|--------|---------|---------|
| `pedido.despachado` | Logística | Pedido |
| `pedido.entregue` | Logística | Pedido |

### Antifraude (`antifraude.eventos`)

| Evento | Publica | Consome |
|--------|---------|---------|
| `pedido.aprovado_fraude` | Antifraude (mock) | Pagamento |
| `pedido.bloqueado_fraude` | Antifraude (mock) | Pedido |

### Catálogo (`catalogo.eventos`)

| Evento | Publica | Consome |
|--------|---------|---------|
| `estoque.atualizado` | Catálogo (mock) | — |

### Envelope padrão

Todos os eventos seguem o mesmo formato:

```json
{
  "evento_id": "uuid-v4",
  "evento_tipo": "pedido.aprovado_fraude",
  "timestamp": "2025-06-01T14:32:18.000Z",
  "correlation_id": "uuid-do-pedido",
  "versao_schema": "1.0",
  "payload": {}
}
```

## 5. Bancos de dados separados por serviço

Cada serviço real possui seu próprio banco **PostgreSQL**, seguindo o princípio de **database per service**:

| Container | Database | URL (dentro do Docker) |
|-----------|----------|------------------------|
| `pedido-db` | `pedido` | `postgresql://postgres:postgres@pedido-db:5432/pedido` |
| `pagamento-db` | `pagamento` | `postgresql://postgres:postgres@pagamento-db:5432/pagamento` |
| `logistica-db` | `logistica` | `postgresql://postgres:postgres@logistica-db:5432/logistica` |

Isso evita acoplamento direto entre serviços via banco compartilhado e permite evolução independente de cada domínio.

## 6. Dashboard (futuro)

O **dashboard em Streamlit** (porta 8050) será a interface visual do projeto. No Módulo 2 ele exibe apenas informações estáticas. Nos módulos seguintes, ele poderá:

- Consultar o status dos serviços via `/health`
- Exibir pedidos em andamento
- Mostrar métricas de eventos processados
- Permitir disparar pedidos de teste

## 7. Evolução no Módulo 3

No **Módulo 3**, o projeto evoluirá para:

1. Implementar endpoints de negócio (criar pedido, processar pagamento, despachar).
2. Conectar `producer.py` e `consumer.py` aos fluxos reais de eventos.
3. Persistir dados com **SQLAlchemy** nos bancos PostgreSQL.
4. Completar o fluxo ponta a ponta: pedido → antifraude → pagamento → logística → catálogo.
5. Enriquecer o dashboard com dados em tempo real.

O Módulo 2 prepara toda a base para que essa integração aconteça sem retrabalho de infraestrutura.

# Arquitetura do ShopFlow — Grupo 2404826

## 1. Visão geral

O **ShopFlow** é um marketplace fictício construído com **microsserviços** e **arquitetura orientada a eventos**. Cada serviço é responsável por uma parte do fluxo de compra e se comunica de forma assíncrona por meio do **RabbitMQ**.

```
Cliente / Gerador
        |
        v  POST /pedidos
+------------------+     pedido.criado      +------------------+
|  Serviço Pedido  | ---------------------> |     RabbitMQ     |
|   (orquestrador) | <--------------------- |   (topic ex.)    |
+------------------+   pagamento/antifraude  +------------------+
        |                    |                      |
        | pedido.confirmado  |                      |
        v                    v                      v
+------------------+  +-------------+    +------------------+
|Serviço Logística |  |  Pagamento  |    | Mock Antifraude  |
+------------------+  +-------------+    +------------------+
        |                                        |
        | pedido.despachado/entregue             | (paralelo)
        v                                        v
+------------------+                    +------------------+
|  Serviço Pedido  |                    | Mock Catálogo    |
| (atualiza status)|                    | estoque.atualizado|
+------------------+                    +------------------+
```

No **Módulo 3**, o fluxo ponta a ponta está implementado: criar um pedido dispara automaticamente toda a cadeia de eventos.

## 2. Por que RabbitMQ?

O **RabbitMQ** foi escolhido no Módulo 1 e é a decisão permanente do projeto porque:

- Suporta **publish/subscribe** com exchanges **topic**, roteando por tipo de evento (`pedido.criado`, `pagamento.aprovado`, etc.).
- **Desacopla** serviços: o Pedido não chama Pagamento via HTTP — ambos reagem a eventos.
- Oferece **painel de gerenciamento** (porta 15672) para inspecionar filas e mensagens.
- Integra com Python via **pika**, usado em todos os serviços e mocks.

## 3. Fluxo ponta a ponta (Módulo 3)

```
POST /pedidos
    │
    ▼
pedido.criado ──────────────┬──────────────────────┐
    │                       │                      │
    ▼                       ▼                      ▼
Mock Antifraude      Serviço Pagamento      (Pedido aguarda)
    │                       │
    ▼                       ▼
pedido.aprovado_fraude   pagamento.aprovado
ou bloqueado_fraude      ou pagamento.recusado
    │                       │
    └───────────┬───────────┘
                ▼
        Serviço Pedido (saga)
                │
    ┌───────────┴───────────┐
    ▼                       ▼
pedido.confirmado      pedido.cancelado
    │
    ├──────────────────────────────┐
    ▼                              ▼
Serviço Logística            Mock Catálogo
    │                              │
    ▼                              ▼
pedido.despachado            estoque.atualizado
    │ (5–15 segundos)
    ▼
pedido.entregue
    │
    ▼
Serviço Pedido atualiza status → entregue
```

## 4. correlation_id

O `correlation_id` é um **UUID gerado na criação do pedido** e copiado para **todos os eventos** daquele fluxo. Isso permite:

- Rastrear um pedido nos logs de todos os serviços
- Correlacionar mensagens no RabbitMQ Management
- Implementar a saga no serviço de Pedido (busca pedido por `correlation_id`)

Exemplo nos logs:

```
[pedido] pedido.criado publicado correlation_id=abc-123
[pagamento] pagamento.aprovado publicado correlation_id=abc-123
[antifraude] pedido.aprovado_fraude publicado correlation_id=abc-123
```

## 5. Saga (orquestração no serviço Pedido)

O serviço de **Pedido** é o orquestrador. Ele mantém flags `pagamento_ok` e `fraude_ok` no banco:

| Evento recebido | Ação |
|-----------------|------|
| `pagamento.aprovado` | `pagamento_ok = true`; se `fraude_ok = true` → confirma |
| `pagamento.recusado` | `pagamento_ok = false` → cancela |
| `pedido.aprovado_fraude` | `fraude_ok = true`; se `pagamento_ok = true` → confirma |
| `pedido.bloqueado_fraude` | `fraude_ok = false` → cancela |
| `pedido.despachado` | status = despachado |
| `pedido.entregue` | status = entregue |

**Regras de proteção:**
- Não confirma duas vezes
- Não cancela duas vezes
- Pedido já confirmado não é cancelado depois
- Pedido já cancelado não é confirmado depois

## 6. Idempotência

Cada serviço consumidor possui a tabela `eventos_processados`:

1. Recebe evento com `evento_id` único
2. Valida envelope e payload (Pydantic)
3. Se `evento_id` já existe → ignora e loga
4. Se novo → processa e salva `evento_id`

Isso evita processamento duplicado em caso de reentrega de mensagens.

Eventos inválidos são **logados e descartados** sem derrubar o container.

## 7. Função de cada serviço

| Serviço | Responsabilidade |
|---------|------------------|
| **Pedido** | API REST, saga, publica `pedido.criado/confirmado/cancelado` |
| **Pagamento** | Consome `pedido.criado`, cobra, publica `pagamento.aprovado/recusado` |
| **Logística** | Consome `pedido.confirmado`, despacha e entrega |
| **Antifraude (mock)** | Consome `pedido.criado`, simula análise de risco |
| **Catálogo (mock)** | Consome `pedido.confirmado`, simula atualização de estoque |

## 8. Eventos por serviço

### Pedido

| Direção | Exchange | Eventos |
|---------|----------|---------|
| Publica | `pedido.eventos` | `pedido.criado`, `pedido.confirmado`, `pedido.cancelado` |
| Consome | `pagamento.eventos` | `pagamento.aprovado`, `pagamento.recusado` |
| Consome | `antifraude.eventos` | `pedido.aprovado_fraude`, `pedido.bloqueado_fraude` |
| Consome | `logistica.eventos` | `pedido.despachado`, `pedido.entregue` |

### Pagamento

| Direção | Exchange | Eventos |
|---------|----------|---------|
| Publica | `pagamento.eventos` | `pagamento.aprovado`, `pagamento.recusado` |
| Consome | `pedido.eventos` | `pedido.criado` |

### Logística

| Direção | Exchange | Eventos |
|---------|----------|---------|
| Publica | `logistica.eventos` | `pedido.despachado`, `pedido.entregue` |
| Consome | `pedido.eventos` | `pedido.confirmado` |

### Mock Antifraude

| Direção | Exchange | Eventos |
|---------|----------|---------|
| Publica | `antifraude.eventos` | `pedido.aprovado_fraude`, `pedido.bloqueado_fraude` |
| Consome | `pedido.eventos` | `pedido.criado` |

### Mock Catálogo

| Direção | Exchange | Eventos |
|---------|----------|---------|
| Publica | `catalogo.eventos` | `estoque.atualizado` |
| Consome | `pedido.eventos` | `pedido.confirmado` |

### Envelope padrão

```json
{
  "evento_id": "uuid-v4",
  "evento_tipo": "pedido.criado",
  "timestamp": "2025-06-01T14:32:18.000Z",
  "correlation_id": "uuid-do-fluxo",
  "versao_schema": "1.0",
  "payload": {}
}
```

## 9. Bancos de dados separados

Cada serviço real possui banco PostgreSQL próprio (**database per service**):

| Serviço | Container DB | Tabelas principais |
|---------|--------------|-------------------|
| Pedido | `pedido-db` | `pedidos`, `eventos_processados`, `eventos` |
| Pagamento | `pagamento-db` | `pagamentos`, `eventos_processados`, `eventos` |
| Logística | `logistica-db` | `entregas`, `eventos_processados`, `eventos` |

Nenhum serviço acessa o banco de outro — a comunicação é exclusivamente por eventos.

## 10. Dashboard (Módulo 4)

O **dashboard Streamlit** (porta 8050) é a interface visual do projeto. Ele consulta os microsserviços via HTTP — **nunca acessa os bancos PostgreSQL diretamente**.

### Por que não acessar o banco diretamente?

Cada microsserviço possui banco isolado (**database per service**). O dashboard respeita essa fronteira consultando apenas:

| Endpoint | Finalidade |
|----------|------------|
| `GET /health` | Status operacional |
| `GET /metrics` | Métricas, KPIs e dados agregados |

### URLs internas (Docker)

| Serviço | URL |
|---------|-----|
| Pedido | `http://pedido:8001` |
| Pagamento | `http://pagamento:8002` |
| Logística | `http://logistica:8003` |

### Abas do dashboard

**Aba 1 — Saúde dos Serviços**
- Status 🟢 OK / 🔴 Fora de cada serviço
- Total de eventos publicados
- Taxa de erro por schema inválido
- Últimos 10 eventos combinados

**Aba 2 — Comunicação ao Vivo**
- Gráfico de throughput (eventos/minuto nos últimos 10 min)
- Tabela dos 50 pedidos mais recentes com indicadores de status
- Contadores: criados, confirmados, cancelados, entregues

**Aba 3 — KPIs de Negócio**
- GMV (Gross Merchandise Value)
- Taxa de aprovação de pagamentos
- Taxa de conversão (confirmados / criados)
- Taxa de bloqueio antifraude
- Pedidos entregues no prazo (%)
- Gráfico histórico de GMV por hora
- Filtro de período: última hora, último dia, total

O dashboard atualiza automaticamente a cada 5 segundos.

### Endpoints expostos pelos serviços

| Serviço | Endpoints |
|---------|-----------|
| Pedido | `GET /health`, `GET /metrics`, `POST /pedidos`, `GET /pedidos/{id}` |
| Pagamento | `GET /health`, `GET /metrics` |
| Logística | `GET /health`, `GET /metrics` |

## 11. Registro de eventos para métricas

Cada serviço registra eventos na tabela `eventos`:

| direcao | Significado |
|---------|-------------|
| `publicado` | Evento publicado no RabbitMQ |
| `consumido` | Evento recebido e processado com sucesso |
| `descartado` | Evento inválido (schema) — descartado sem derrubar o serviço |

Esses registros alimentam `/metrics`: eventos publicados, taxa de erro, últimos eventos e throughput.

## 12. Evolução futura

- Observabilidade avançada (tracing distribuído)
- Dead letter queues
- Testes automatizados de integração
- Roteiro de vídeo de demonstração (Módulo 5)

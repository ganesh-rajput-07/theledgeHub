# KnowledgeHub AI — Database Intelligence Architecture



Recommended architecture

&#x20;Multi-tenant · Multi-database · AI-powered · Controlled operations



Based on your requirements, I would design KnowledgeHub as a multi-tenant AI data platform, not simply a chatbot connected to SQL.

The goal is to let multiple companies connect different databases, ask questions, generate analytics, investigate data, and perform approved database operations through one interface.

There is one important distinction in your requirements:

- Any database: Support different database engines through a common connector architecture.
- Limited production impact: Prefer replicas and separate analytics storage, but permit carefully controlled production access when necessary.
- Full access: Support all categories of database operations, but do not give the LLM unrestricted database credentials or automatic authority to execute destructive operations.

The LLM should understand and propose operations. A separate, permission-controlled execution service should decide whether they can run.

## 1. High-level architecture

KnowledgeHub AI — User Interface

Chat · SQL workspace · Analytics dashboards · Database operations · Audit history

API Gateway + Tenant Identity

Authentication · Tenant isolation · RBAC · Rate limits · Usage quotas

AI Orchestration Engine

Intent detection · Context retrieval · Schema understanding · Query planning · Tool selection

Knowledge RAG

Documents, policies, business rules

Database RAG

Schemas, relationships, metadata, query history

Database Tool Gateway

SQL parser · Permission engine · Query validator · Cost estimator · Approval workflow

Database Connectors

PostgreSQL · MySQL · SQL Server · Oracle · Others

Analytics Engine

Warehouse · Aggregations · Reports · Dashboards

Customer Data Systems

Production DB · Read replica · Analytics store · Approved write connection

The important architectural boundary is the Database Tool Gateway. The LLM never gets direct access to database credentials.

## 2. Multi-tenant architecture: separate control plane and data plane

Because this is intended for multiple companies, tenant isolation needs to be a foundational design decision, not something added later.

I recommend two logical planes.

A. Control plane — shared platform

Tenant management

Organizations, users, roles, plans

Credential vault

Encrypted connection secrets and rotation

Connection registry

Database configurations and capabilities

Policy engine

Permissions, approvals, limits

B. Data plane — tenant-specific execution

Tenant A

Connectors · Jobs · Analytics · Audit

Tenant B

Connectors · Jobs · Analytics · Audit

Tenant C

Connectors · Jobs · Analytics · Audit

Tenant N

Connectors · Jobs · Analytics · Audit

Shared infrastructure can be used initially, but tenant-specific credentials, authorization boundaries, query contexts and data ownership must always be enforced.

### Tenant isolation rules

- Every connection, query, document, report, job and audit event belongs to a tenant.
- Never trust a `tenant_id` supplied by the LLM or directly by a client request. Derive it from authenticated identity and server-side authorization.
- Use tenant-scoped storage, cache keys, queues and execution contexts.
- Consider dedicated databases, encryption keys and worker pools for enterprise customers.
- Test explicitly that one tenant cannot access another tenant's connections, metadata, query results or files.

OWASP's multi-tenant guidance covers these isolation boundaries and noisy-neighbor risks.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://cheatsheetseries.owasp.org\&sz=32)

OWASP Cheat Sheet Series



## 3. Database connectivity: how to support any database

Don't implement database connectivity inside the AI agent itself.

Build a Database Connector Framework with a standard interface. Every database adapter implements the same contract.

### Proposed connector interface

```
from abc import ABC, abstractmethodclass DatabaseConnector(ABC):    @abstractmethod    def connect(self):        pass    @abstractmethod    def test_connection(self):        pass    @abstractmethod    def get_database_metadata(self):        pass    @abstractmethod    def get_schema(self):        pass    @abstractmethod    def execute_read(self, query, params=None):        pass    @abstractmethod    def execute_write(self, operation):        pass    @abstractmethod    def execute_ddl(self, operation):        pass    @abstractmethod
```

This is a starting contract, not a complete security boundary. The gateway must enforce authorization and validation before calling any execution method.

### Database support strategy

| Database category          | Initial adapter strategy        |
| -------------------------- | ------------------------------- |
| PostgreSQL                 | SQLAlchemy + psycopg            |
| MySQL / MariaDB            | SQLAlchemy + appropriate driver |
| SQL Server                 | SQLAlchemy + pyodbc             |
| Oracle                     | SQLAlchemy + python-oracledb    |
| SQLite                     | SQLAlchemy + sqlite3            |
| MongoDB                    | Native PyMongo adapter          |
| Redis                      | Native Redis adapter            |
| Elasticsearch / OpenSearch | Native API adapter              |
| Snowflake / BigQuery       | Native warehouse adapters       |

SQLAlchemy already includes dialects for PostgreSQL, MySQL/MariaDB, SQLite, Oracle and Microsoft SQL Server, but it doesn't mean every database feature is portable.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.sqlalchemy.org\&sz=32)

SQLAlchemy 2.1 Documentation+1



The important distinction: You can aim for any database, but you cannot promise universal support for every database engine, feature and operation through one SQL abstraction. SQL and NoSQL need different connector interfaces.

### Suggested project structure

```
knowledgehub/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   │   ├── auth.py
│   │   │   ├── tenant.py
│   │   │   └── permissions.py
│   │   │
│   │   ├── database_intelligence/
│   │   │   ├── connectors/
│   │   │   │   ├── base.py
│   │   │   │   ├── registry.py
│   │   │   │   ├── postgres/
│   │   │   │   ├── mysql/
│   │   │   │   ├── sqlserver/
│   │   │   │   ├── oracle/
│   │   │   │   └── mongodb/
│   │   │   │
│   │   │   ├── metadata/
│   │   │   ├── query_engine/
│   │   │   ├── analytics/
│   │   │   ├── operations/
│   │   │   ├── approvals/
│   │   │   ├── audit/
│   │   │   └── sync/
│   │   │
│   │   ├── ai/
│   │   │   ├── intent/
│   │   │   ├── planner/
│   │   │   ├── sql_generator/
│   │   │   └── orchestrator/
│   │   │
│   │   └── main.py
│   │
│   └── tests/
│
├── scripts/
├── models/
└── docs/
```

## 4. Production isolation and analytics architecture

This is probably the most important part of your product.

I would implement three connection paths per customer database.

Path A — Production connection

Restricted

For operational questions that genuinely require current data.

- Small, indexed queries.
- Strict execution timeout.
- Limited concurrency.
- Restricted tables and columns.
- No unrestricted analytical scans.

Path B — Read replica

Preferred for live reads

For queries that need relatively fresh operational data.

- Separate read-only credentials.
- Query limits and timeouts.
- Monitor replication lag.
- Keep production workloads separate from AI workloads.

Path C — Analytics database

Preferred for heavy analytics

- Historical analysis.
- Large aggregations.
- Customer segmentation.
- Revenue trends.
- Dashboards and scheduled reports.

### How data reaches the analytics database

Use two synchronization strategies:

Option 1: Incremental ETL

- Run scheduled jobs.
- Fetch only records changed since the previous successful sync.
- Use timestamps, version columns or database-specific change tracking.
- Load records into the analytics database.
- Maintain a sync checkpoint and reconcile failures.

This is simpler for your first version, although timestamp-based synchronization requires reliable change tracking and can miss hard deletes unless handled explicitly.

Option 2: Change Data Capture (CDC)

Use Debezium to capture database changes and stream them into your analytics pipeline.

Debezium supports several major database systems, including PostgreSQL, MySQL, SQL Server and Oracle, with other connectors at different maturity levels. It can still create source database load, so it needs monitoring and customer configuration.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://debezium.io\&sz=32)

Debezium+1



### Which analytics database?

| Technology             | Best use                                         |
| ---------------------- | ------------------------------------------------ |
| DuckDB                 | Local development and small analytics workloads  |
| ClickHouse             | Larger datasets and frequent analytical queries  |
| PostgreSQL             | Initial metadata and smaller reporting workloads |
| Data lake with Parquet | Long-term historical storage and large datasets  |

My recommendation:

- Start with DuckDB locally while developing the feature.
- Use ClickHouse as the dedicated analytics engine when building the multi-tenant production platform.
- Keep PostgreSQL as the KnowledgeHub application's metadata and configuration database.

ClickHouse supports incremental materialized views that precompute aggregations as data arrives, reducing repeated computation during reporting. They still introduce ingestion-time overhead, so select them based on actual workloads.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



## 5. AI query generation and execution

This is where your local LLM becomes useful.

The model should not simply receive a question and immediately execute whatever SQL it generates.

Use a multi-step workflow:

User asks

"Show me the top 10 customers by revenue this quarter."

1\. Intent detection

Identify analytics request, date range, metrics and target database.

2\. Schema retrieval

Retrieve relevant tables, relationships, column descriptions and business definitions.

3\. SQL generation

Generate SQL using the target database's dialect and parameterized values.

```
SELECT customer_id, SUM(total_amount) AS revenue
FROM orders
WHERE created_at >= :start_date
  AND created_at < :end_date
GROUP BY customer_id
ORDER BY revenue DESC
LIMIT 10;
```

4\. Validation and authorization

Check syntax, allowed tables, permissions, query cost, limits and tenant scope.

5\. Execution

Send the query to the appropriate production replica or analytics database.

6\. Answer generation

Return a natural-language explanation, result table, chart and data freshness timestamp.

### Important: SQLGlot is not your security layer

Use SQLGlot for parsing SQL, inspecting its abstract syntax tree, and dialect conversion. But its own documentation warns that successful parsing does not guarantee a query is valid for the target engine.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://sqlglot.com\&sz=32)

sqlglot.com+1



Your actual safety boundary should include:

1. SQL AST inspection and operation allow-lists.
2. Database-enforced permissions.
3. Parameterized values.
4. Query timeouts and resource limits.
5. Row and result-size limits.
6. Tenant-aware authorization.
7. Database-side auditing.

Never rely on an LLM instruction such as "Only generate safe SQL" as a security control.

## 6. Full database operations — safe execution model

You selected full database access. I would support the complete set of operations as product capabilities, but expose them through permission levels.

| Operation              | Default behavior                           |
| ---------------------- | ------------------------------------------ |
| SELECT                 | Execute automatically within limits        |
| INSERT                 | Preview and require approval               |
| UPDATE                 | Preview affected rows and require approval |
| DELETE                 | Preview affected rows and require approval |
| CREATE / ALTER         | Require elevated approval                  |
| DROP / TRUNCATE        | Restricted, explicit high-risk approval    |
| Backup / Restore       | Separate privileged workflow               |
| User / role management | Administrator-only                         |

A good execution lifecycle:

1. AI creates a structured operation proposal.
2. Gateway checks the requesting user's permissions and database role.
3. Show the generated SQL, affected tables, estimated affected rows and risk.
4. Run a dry run where possible, or a rollback-safe preview in an isolated environment.
5. Request approval from an authorized user.
6. Revalidate the proposal and permissions immediately before execution.
7. Execute within a controlled transaction where supported.
8. Record the result and audit information, including the approver and execution identity.

A dry run is not a guarantee that a write will succeed or be harmless. For example, triggers, concurrent transactions, external side effects and DDL transaction behavior vary across database engines.

My strong recommendation: Do not give the AI a database root, `postgres` superuser, `sa`, or Oracle `SYS` credential. Use separate scoped identities for reading, writing and administration. OWASP recommends least privilege and separate application-specific database users.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://cheatsheetseries.owasp.org\&sz=32)

OWASP Cheat Sheet Series+1



## 7. Security architecture

For a multi-company product, security is a product feature, not just backend configuration.

| Security area    | Recommended implementation                              |
| ---------------- | ------------------------------------------------------- |
| Authentication   | OAuth2 / OIDC                                           |
| Authorization    | RBAC + resource-level permissions                       |
| Tenant isolation | Tenant-scoped data and execution contexts               |
| Credentials      | HashiCorp Vault or cloud KMS-backed secrets             |
| Network access   | Private connector agent or customer VPN                 |
| SQL security     | SQLGlot + database permissions + query policies         |
| Encryption       | TLS in transit and encryption at rest                   |
| Audit            | Append-only operation and approval logs                 |
| Rate limiting    | Per-tenant and per-connection limits                    |
| Data privacy     | PII masking, column restrictions and retention controls |
| Monitoring       | OpenTelemetry + Prometheus                              |

### One feature I would definitely build: Customer-side Connector Agent

Some companies will not allow their databases to be exposed to an external SaaS application.

Give them an option to install a lightweight agent inside their infrastructure.

KnowledgeHub Cloud

AI · Tenant management · Permissions · Query planning

Authenticated outbound connection

KnowledgeHub Connector Agent

Installed inside customer infrastructure

Local credentials · Query execution · Policy enforcement

Production DB

Restricted access

Analytics DB

Reporting workloads

This means:

- No need to expose the customer's database publicly.
- The customer controls the database credentials.
- The agent can restrict outbound communication.
- The customer can revoke access by disconnecting the agent.
- Enterprise customers can keep sensitive data inside their infrastructure.

For stronger isolation, the agent should also have its own local policy enforcement, not blindly execute every instruction received from the cloud.

## 8. Recommended technology stack

Here is the stack I would select for the first serious version.

| Layer            | Technology                     | Purpose                               |
| ---------------- | ------------------------------ | ------------------------------------- |
| API              | FastAPI + Pydantic             | Backend                               |
| Application DB   | PostgreSQL                     | Tenants, users, connections, policies |
| ORM/connectivity | SQLAlchemy                     | Relational connectors                 |
| SQL parser       | SQLGlot                        | SQL AST and dialect support           |
| NoSQL            | Native drivers                 | MongoDB, Redis, etc.                  |
| Queue            | Celery + Redis                 | Background work                       |
| Analytics        | ClickHouse                     | Analytical queries                    |
| Local analytics  | DuckDB                         | Development and smaller workloads     |
| CDC              | Debezium                       | Change streaming                      |
| Vector search    | pgvector initially             | Schema and document retrieval         |
| Object storage   | MinIO / S3                     | Exports and historical data           |
| Secrets          | Vault / KMS                    | Credential protection                 |
| Observability    | OpenTelemetry + Prometheus     | Monitoring                            |
| Charts           | Plotly                         | Interactive analytics                 |
| LLM              | Your Hugging Face local models | Intent, SQL planning and explanations |

Some components are deliberately optional. For example, don't deploy Kafka and Debezium until scheduled incremental synchronization is no longer sufficient.

### How the existing KnowledgeHub fits

You don't need to rebuild your current project.

Keep your existing document RAG system and introduce database intelligence as a separate module.

| Existing functionality | New functionality                         |
| ---------------------- | ----------------------------------------- |
| Document upload        | Database connection                       |
| Text extraction        | Schema discovery                          |
| Chunking               | Schema metadata indexing                  |
| Embeddings             | Business definitions and schema retrieval |
| Vector search          | Database context retrieval                |
| LLM response           | SQL generation and analytics              |
| RAG response           | Combined document + database response     |

The same local LLM can be used for both, but use deterministic backend code for validation, permissions, calculations and execution.

## 9. Implementation roadmap

I would develop this in eight phases rather than attempting everything together.

1. Phase 1 — Database connection framework

   Start here
   - Connector interface and registry.
   - PostgreSQL and MySQL adapters.
   - Connection testing.
   - Credential encryption.
   - Schema discovery.
2. Phase 2 — Database context engine
   - Tables and column metadata.
   - Foreign-key relationships.
   - Index and constraint discovery.
   - Schema descriptions and business definitions.
   - Schema retrieval for the LLM.
3. Phase 3 — Natural-language database assistant
   - Question classification.
   - SQL generation.
   - Dialect awareness.
   - SQL validation.
   - Read-only query execution.
   - Result explanation.
4. Phase 4 — Analytics
   - Aggregations and groupings.
   - Charts and reports.
   - Date comparisons.
   - Analytics query history.
   - Saved dashboards.
5. Phase 5 — Production isolation
   - Read replicas.
   - Analytics database.
   - Incremental ETL.
   - CDC integration.
   - Sync monitoring and recovery.
6. Phase 6 — Database operations
   - INSERT, UPDATE and DELETE.
   - Operation previews.
   - Approval workflow.
   - Controlled transactions.
   - DDL and privileged operations.
7. Phase 7 — Multi-tenant SaaS
   - Organization management.
   - Tenant-specific policies.
   - Usage limits.
   - Billing and plans.
   - Customer-side connector agent.
8. Phase 8 — Advanced intelligence
   - Anomaly detection.
   - Data-quality monitoring.
   - Predictive analytics.
   - Automated recommendations.
   - Business workflow automation.

## 10. Suggested first MVP

I would avoid beginning with all databases and full database administration.

Build one complete vertical workflow first:

MVP scope

PostgreSQL connection → schema discovery → natural-language questions → safe SQL → analytics charts.

Your initial demo should support these questions:

1. How many records are in each table?
2. Show the top 10 customers by revenue.
3. Compare monthly revenue for the last six months.
4. Find duplicate customer records.
5. Which orders are pending for more than seven days?
6. Explain the relationship between these two tables.
7. Show me the SQL generated for this question.

Then add a controlled UPDATE operation with an approval flow.

### Suggested initial dependencies

For your Python backend, these are useful starting packages:

```
python -m pip install \
    fastapi \
    uvicorn \
    sqlalchemy \
    sqlglot \
    psycopg[binary] \
    pymysql \
    pydantic \
    pydantic-settings \
    redis \
    celery \
    duckdb \
    plotly \
    cryptography
```

Add database-specific drivers when implementing each connector. Don't install every database driver upfront.

## 11. Final architectural decisions

Here is what I would lock in for KnowledgeHub:

| Decision               | Recommendation                               |
| ---------------------- | -------------------------------------------- |
| Product architecture   | Multi-tenant SaaS                            |
| Database support       | Plugin-based connector framework             |
| First database         | PostgreSQL                                   |
| First analytics engine | DuckDB                                       |
| Production analytics   | ClickHouse                                   |
| Production query path  | Read replica or restricted direct connection |
| AI access              | Through a controlled tool gateway            |
| Database writes        | Approval-based                               |
| Admin operations       | Restricted, privileged workflows             |
| Customer networking    | Optional customer-side agent                 |
| LLM execution          | Local Hugging Face models initially          |

One more important consideration: your current small local models are useful for experimentation, but don't assume they can reliably plan complex joins, understand unfamiliar schemas or generate safe SQL across every database. Build evaluation datasets and test generated queries against known expected results before allowing them into production.

Useful technical references:

- [SQLAlchemy database dialects](https://docs.sqlalchemy.org/en/21/dialects/?utm_source=chatgpt.com)
- [SQLGlot documentation](https://sqlglot.com/?utm_source=chatgpt.com)
- [Debezium supported databases](https://debezium.io/databases/?utm_source=chatgpt.com)
- [OWASP multi-tenant security](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html?utm_source=chatgpt.com)
- [OWASP SQL injection prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet?utm_source=chatgpt.com)
- [ClickHouse materialized views](https://github.com/ClickHouse/clickhouse-docs/blob/main/docs/best-practices/use_materialized_views.md?utm_source=chatgpt.com)

## My strongest recommendation

Build KnowledgeHub as three independently usable modules:

1. Knowledge Intelligence — Understand documents and business information.
2. Database Intelligence — Understand databases, answer questions and generate analytics.
3. Database Operations — Perform controlled database changes and administrative tasks.

Then connect all three through one AI orchestration engine.

This gives you a product that can eventually answer a question like:

"Read our business policy, check the database, find all customers affected by this issue, show the financial impact, and prepare a corrective operation for approval."

That is a much stronger direction than just building another PDF chatbot.
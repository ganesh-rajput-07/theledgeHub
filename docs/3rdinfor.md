Perfect. We'll go with BYOK (Bring Your Own Key) only for the initial product.

That means customers connect their own AI provider API keys, and your platform handles document processing, retrieval, context management, citations, and chat orchestration.

This is a sensible decision at your current stage: you build the AI platform without taking on customers' LLM inference bills.

## 1. BYOK product model

Customer

Creates an account and configures an assistant

Your platform

Document ingestion · RAG · Vector search · Citations · Chat interface

Customer's AI API key

Gemini / OpenAI / Claude / other supported providers

Grounded AI response with document citations

## 2. Initial technical decisions

| Component           | Decision                        |
| ------------------- | ------------------------------- |
| Backend             | Python + FastAPI                |
| Database            | PostgreSQL                      |
| Vector search       | pgvector                        |
| ORM                 | SQLAlchemy                      |
| Migrations          | Alembic                         |
| Document extraction | PyMuPDF, python-docx            |
| Embeddings          | Configurable embedding provider |
| LLM                 | Customer's API key              |
| Frontend            | Next.js                         |
| Authentication      | JWT-based authentication        |
| Deployment          | Docker                          |

Important: BYOK applies to embeddings as well as chat generation. We should allow configurable embedding providers rather than silently using a paid service. For initial development, use a local embedding model.

## 3. Key architecture requirement

Build a provider-independent AI layer from day one.

For example:

```
class LLMProvider:    async def generate(self, messages, model, **kwargs):        raise NotImplementedErrorclass EmbeddingProvider:    async def embed(self, texts):        raise NotImplementedError
```

Then implement provider adapters separately:

```
ai/
├── providers/
│   ├── base.py
│   ├── gemini.py
│   ├── openai.py
│   ├── anthropic.py
│   └── local.py
├── embeddings/
├── retrieval/
├── generation/
└── prompts/
```

Don't hardcode Gemini or any other provider throughout your application.

## 4. How we will handle API keys

This is important because customers will trust you with their credentials.

- Encrypt API keys before storing them.
- Never return the original key through your API.
- Never expose keys to the frontend after submission.
- Never write keys to application logs.
- Allow customers to update or revoke their keys.
- Validate the key with the provider before marking it active.
- Keep provider credentials isolated by customer/organization.

## 5. What you will eventually sell

You can monetize the platform without paying for customers' model usage:

- SaaS subscriptions for platform features.
- Additional storage and document limits.
- More assistants and team members.
- Website chatbot integration.
- Custom branding and deployment.
- Custom integrations and implementation services.

You will still have infrastructure costs for hosting, storage, databases and processing. BYOK removes your responsibility for the customer's LLM API bill, not every operating expense.

## 6. Our next step: freeze the product architecture

I recommend we build this as a modular monolith, not microservices. It is simpler to develop, test and deploy as a solo developer.

The first milestone should be a working backend that can:

1. Accept a PDF.
2. Extract its text.
3. Split it into chunks.
4. Generate and store embeddings.
5. Accept a question.
6. Retrieve relevant chunks.
7. Send those chunks to the customer's selected LLM.
8. Return an answer with citations.

Once this works reliably, we'll build the multi-user SaaS layer and frontend.

One principle for this project: build the RAG engine yourself first. Don't let LangChain or another framework hide the core concepts you need to understand and eventually customize for clients.
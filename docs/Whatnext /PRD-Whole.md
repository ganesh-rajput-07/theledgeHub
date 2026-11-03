# KnowledgeHub AI — Engineering PRD & Development Master Document



Development specification

Version 1.0



This document is the implementation reference for building KnowledgeHub AI. It defines the product requirements, architecture, modules, database relationships, APIs, workflows, user stories, acceptance criteria and release plan.

The key architectural decision is to build a universal multi-tenant platform with configurable industry packs, rather than building separate applications for every industry.

# KnowledgeHub AI

## Product Requirements Document (PRD) & Engineering Master Specification

**Version:** 1.0\
**Product:** KnowledgeHub AI\
**Category:** Document Intelligence & Business Workflow Automation\
**Initial Market:** Surat, Gujarat, India\
**Business Model:** SaaS + Managed Onboarding + Customization\
**Architecture:** Modular Monolith + Asynchronous Processing\
**Backend:** Python + FastAPI\
**Frontend:** React + TypeScript\
**Database:** PostgreSQL + pgvector\
**Object Storage:** MinIO / S3-compatible storage

---

# 1. Product Vision

KnowledgeHub AI is a universal document intelligence and business workflow automation platform.

It enables businesses to receive, organize, process, understand, validate, review, approve and act on business documents through one centralized system.

The platform combines:

1. Document management.
2. PDF and image processing.
3. OCR and AI-based information extraction.
4. Document classification.
5. Cross-document verification.
6. Duplicate and missing-information detection.
7. Human review and approval.
8. Workflow and task automation.
9. Reporting and exports.
10. AI-powered search and document assistance.

## 1.1 Product promise

Turn incoming business documents into verified information, actionable work and completed business processes.

## 1.2 Product principles

- One platform, multiple industry packs.
- Original documents must remain immutable.
- AI extraction must be traceable to source evidence.
- Deterministic validation should use code, not LLM guesses.
- Human approval must be supported wherever correctness matters.
- Tenant data must remain isolated.
- Industry-specific logic must not leak into common platform modules.
- Every important business action must be auditable.
- Customer documents must never be used for model training without explicit authorization.

# 2. Product Scope

## 2.1 Universal platform modules

| Module               | Responsibility                                    |
| -------------------- | ------------------------------------------------- |
| Authentication       | Login, sessions, password management              |
| Tenant Management    | Organization and tenant configuration             |
| User Management      | Users, invitations, roles and permissions         |
| Client Management    | Customer and counterparty records                 |
| Workspace Management | Cases, projects, shipments and accounting periods |
| Document Intake      | Upload, bulk upload and integrations              |
| Document Management  | Folders, tags, metadata and versions              |
| Document Editor      | PDF and image operations                          |
| OCR Engine           | Text extraction and searchable PDFs               |
| AI Classification    | Document type identification                      |
| AI Extraction        | Structured field extraction                       |
| Quality Engine       | File quality and readability checks               |
| Validation Engine    | Field rules and cross-document checks             |
| Workflow Engine      | Business process automation                       |
| Task Management      | Assignments, due dates and reminders              |
| Review Center        | Human verification and approval                   |
| Search Engine        | Keyword and semantic search                       |
| AI Assistant         | Document Q&A and summaries                        |
| Reporting            | Excel, CSV and PDF exports                        |
| Integrations         | External applications and APIs                    |
| Audit System         | User and system activity history                  |
| Administration       | Settings, plans and security controls             |

## 2.2 Out of scope for the first release

- Autonomous financial transactions.
- Automatic legal or clinical decisions.
- Replacing accounting software or ERP systems.
- Unrestricted AI-generated SQL execution.
- Fully autonomous agents with unrestricted customer-system access.
- Building 11 independent industry applications.
- Native mobile applications.
- Complex custom model training for each customer.

# 3. Target Markets and Industry Packs

The platform will support eight configurable packs covering the 11 target market categories.

## 3.1 Finance & Compliance Pack

Target customers:

- Chartered Accountant firms.
- Audit firms.

Document types:

- Purchase invoices.
- Sales invoices.
- Bank statements.
- GST returns.
- Purchase registers.
- Sales registers.
- Expense vouchers.
- Payment receipts.
- Ledger exports.
- Audit evidence.

Core workflows:

- Monthly client document collection.
- Document completeness checking.
- Invoice extraction.
- Duplicate invoice detection.
- Invoice-to-register matching.
- Bank statement extraction.
- Reconciliation exception reporting.
- Audit evidence organization.

Example validation rules:

- Duplicate invoice number within the defined supplier and period.
- Missing GSTIN.
- Taxable amount plus tax does not match invoice total.
- Invoice date outside the selected financial period.
- Invoice details differ from accounting register.
- Missing required supporting documents.

## 3.2 Trade & Shipment Pack

Target customers:

- Import/export companies.
- Freight forwarding businesses.

Document types:

- Commercial invoice.
- Packing list.
- Bill of lading.
- Shipping instructions.
- Purchase order.
- Delivery order.
- Certificate of origin.
- Customs-related documents.

Core workflows:

- Shipment document intake.
- Shipment reference identification.
- Cross-document matching.
- Missing-document tracking.
- Shipment exception reporting.
- Document completeness approval.

Example validation rules:

- Consignee mismatch.
- Shipment reference mismatch.
- Quantity mismatch.
- Gross or net weight mismatch.
- Currency mismatch.
- Missing shipment documents.

## 3.3 Operations & Procurement Pack

Target customers:

- Manufacturing companies.

Document types:

- Purchase orders.
- Supplier invoices.
- Delivery challans.
- Goods receipt notes.
- Quality inspection reports.
- Job-work challans.
- Material issue records.

Core workflows:

- Purchase-to-receipt verification.
- Supplier invoice validation.
- Delivery quantity comparison.
- Purchase order matching.
- Quality report association.
- Supplier document management.

## 3.4 Legal Intelligence Pack

Target customers:

- Law firms.

Document types:

- Agreements.
- Contracts.
- Notices.
- Court documents.
- Legal correspondence.
- Case evidence.

Core workflows:

- Matter file organization.
- Party and date extraction.
- Contract clause identification.
- Version comparison.
- Evidence-linked search.
- Case document completeness.

The system assists legal professionals and does not independently provide legal conclusions.

## 3.5 Insurance Claims Pack

Target customers:

- Insurance brokers.

Document types:

- Policy documents.
- Claim forms.
- Bills.
- Identity documents.
- Incident reports.
- Supporting evidence.

Core workflows:

- Claim document intake.
- Missing-document detection.
- Policy-to-claim information matching.
- Claim file organization.
- Exception routing.

## 3.6 Property Document Pack

Target customers:

- Real estate agencies.

Document types:

- Sale agreements.
- Rental agreements.
- Property records.
- Identity documents.
- Ownership-related records.
- Payment receipts.

Core workflows:

- Property file organization.
- Party and property information extraction.
- Document checklist management.
- Missing-document detection.
- Version tracking.

## 3.7 Recruitment Pack

Target customers:

- Recruitment agencies.

Document types:

- Resumes.
- Experience letters.
- Educational certificates.
- Identity documents.
- Offer letters.

Core workflows:

- Candidate document collection.
- Resume extraction.
- Candidate profile creation.
- Credential checklist.
- Missing-document follow-up.

## 3.8 Healthcare Administration Pack

Target customers:

- Hospitals.

Document types:

- Administrative forms.
- Medical bills.
- Insurance paperwork.
- Admission forms.
- Supporting administrative records.

Core workflows:

- Administrative document intake.
- Document classification.
- Completeness checks.
- Billing document organization.

Healthcare workflows require additional privacy, access and regulatory review before production use.

# 4. User Roles and Permissions

## 4.1 Platform-level roles

| Role                 | Responsibility                            |
| -------------------- | ----------------------------------------- |
| Platform Super Admin | Manage platform configuration and tenants |
| Platform Support     | Authorized operational support            |
| Platform Auditor     | Review permitted platform audit records   |

Platform support must not automatically gain access to customer document content.

## 4.2 Tenant-level roles

| Role         | Permissions                                     |
| ------------ | ----------------------------------------------- |
| Tenant Owner | Full organization administration                |
| Admin        | User, configuration and workflow administration |
| Manager      | Team, workspace and workflow management         |
| Processor    | Upload and process documents                    |
| Reviewer     | Review and correct extracted information        |
| Approver     | Approve or reject business results              |
| Viewer       | Read-only access to authorized resources        |

A user may have more than one role.

## 4.3 Permission codes

Examples:

- `tenant.read`
- `tenant.update`
- `users.read`
- `users.invite`
- `users.update`
- `roles.manage`
- `clients.read`
- `clients.create`
- `documents.read`
- `documents.upload`
- `documents.update`
- `documents.download`
- `documents.delete`
- `documents.process`
- `documents.review`
- `documents.approve`
- `workflows.manage`
- `tasks.assign`
- `reports.generate`
- `reports.download`
- `integrations.manage`
- `audit.read`

Authorization must be checked at both the endpoint and resource level.

# 5. Functional Requirements

Priority definitions:

- P0: Required for first customer-ready release.
- P1: Important after initial workflow validation.
- P2: Future enhancement.

## 5.1 Authentication and tenant management

### FR-AUTH-001 — User login

Priority: P0

The system must allow registered users to authenticate securely.

Acceptance criteria:

- Valid credentials establish an authenticated session.
- Invalid credentials return a generic authentication error.
- Inactive users cannot authenticate.
- Login attempts are rate-limited.
- Authentication events are logged.
- Passwords are stored using a secure password hashing algorithm.

### FR-AUTH-002 — Password reset

Priority: P0

Acceptance criteria:

- User can request a reset link.
- Reset token is single-use and expires.
- Password reset invalidates applicable existing sessions.
- Passwords are never sent through email.

### FR-TENANT-001 — Organization creation

Priority: P0

Acceptance criteria:

- A new tenant can be created.
- The creator becomes its owner.
- Default tenant settings are created.
- Tenant-owned resources cannot be accessed by another tenant.

### FR-TENANT-002 — Tenant switching

Priority: P1

Users belonging to multiple tenants can select an active organization.

Acceptance criteria:

- Active tenant context is explicit.
- Every subsequent request is authorized against that tenant.
- Switching tenants does not expose resources from the previous tenant.

## 5.2 User and role management

### FR-USER-001 — Invite users

Priority: P0

Acceptance criteria:

- Admin can invite a user by email.
- Invitation token expires.
- Existing users can join a tenant without creating duplicate identities.
- Invitation acceptance creates the tenant membership.
- Invitation actions are auditable.

### FR-USER-002 — Role assignment

Priority: P0

Acceptance criteria:

- Admin can assign and revoke roles.
- Role changes take effect according to the active authorization policy.
- Unauthorized role changes are rejected.
- Role changes are recorded in audit events.

## 5.3 Client and workspace management

### FR-CLIENT-001 — Client records

Priority: P0

Acceptance criteria:

- Users can create and edit client records.
- Clients belong to one tenant.
- Client records can be searched and filtered.
- Duplicate detection can warn about matching external references.

### FR-WORKSPACE-001 — Workspaces

Priority: P0

A workspace represents a business context such as:

- Client accounting period.
- Shipment.
- Legal matter.
- Purchase project.
- Insurance claim.
- Candidate profile.
- Property file.

Acceptance criteria:

- Workspace has a type and unique tenant-scoped reference.
- Documents can be associated with workspaces.
- Workspace permissions are enforced.
- Workspace status can be tracked.
- Related documents can be viewed together.

## 5.4 Document intake and management

### FR-DOC-001 — Single upload

Priority: P0

Acceptance criteria:

- User can upload supported file types.
- Server validates actual file content and MIME type.
- File-size and page-count limits are enforced.
- Original file is stored in object storage.
- Document record is created with its tenant and workspace.
- Upload returns a document ID.
- Upload events are auditable.

### FR-DOC-002 — Bulk upload

Priority: P0

Acceptance criteria:

- Multiple documents can be uploaded in one operation.
- Each file has an independent processing status.
- Failed files do not block successful files.
- User can see per-file errors.
- Retrying a failed upload does not duplicate an already completed operation.

### FR-DOC-003 — Document preview

Priority: P0

Acceptance criteria:

- Supported PDFs can be previewed.
- Page navigation is available.
- Images can be previewed.
- Download is permission-controlled.
- Preview generation does not modify the original.

### FR-DOC-004 — Document versions

Priority: P0

Acceptance criteria:

- Replacing a document creates a new version.
- Earlier versions remain accessible to authorized users.
- Each version has a file hash and storage reference.
- Version creation records the actor and timestamp.
- Original versions are not silently overwritten.

### FR-DOC-005 — Document organization

Priority: P0

Acceptance criteria:

- Documents can be assigned to folders or workspaces.
- Tags can be added and removed.
- Metadata can be edited according to permissions.
- Documents can be filtered by type, date, status and client.

### FR-DOC-006 — Duplicate detection

Priority: P0

Acceptance criteria:

- Exact duplicates can be detected using cryptographic file hashes.
- Business-level duplicate checks can use extracted identifiers.
- Potential duplicates are flagged, not automatically deleted.
- Duplicate results show the related document records.

## 5.5 PDF and image operations

### FR-PDF-001 — Merge documents

Priority: P0

- Merge selected PDFs.
- Preserve page order.
- Generate a new derived file.
- Record source document versions.

### FR-PDF-002 — Split documents

Priority: P0

- Split by selected pages or page ranges.
- Create derived documents.
- Retain source references.

### FR-PDF-003 — Rotate and reorder

Priority: P0

- Rotate selected pages.
- Change page order.
- Save the result as a new version or derived document.

### FR-PDF-004 — Compress

Priority: P1

- Offer configurable compression.
- Report resulting file size.
- Preserve original.

### FR-PDF-005 — Convert

Priority: P1

Support selected conversions based on validated libraries and available processing capacity.

### FR-PDF-006 — Annotate and redact

Priority: P1

- Support authorized annotations.
- Redaction must permanently remove underlying content from the exported redacted file.
- A visual overlay alone must never be described as secure redaction.
- Preserve the original version.

### FR-PDF-007 — Extract pages

Priority: P0

- Select pages or ranges.
- Generate a new PDF.
- Record source references.

## 5.6 OCR and file quality

### FR-OCR-001 — OCR processing

Priority: P0

Acceptance criteria:

- Scanned documents can be processed.
- Extracted text is associated with pages.
- OCR output is stored separately from the original.
- OCR processing status is visible.
- OCR failures can be retried.

### FR-OCR-002 — Searchable PDF

Priority: P1

Generate searchable PDFs with a text layer while retaining the original image content.

### FR-QUALITY-001 — Quality checks

Priority: P0

Detect:

- Corrupted files.
- Unsupported files.
- Password-protected files.
- Blank or nearly blank pages.
- Rotated pages.
- Low-resolution scans.
- Unreadable or low-confidence OCR.
- Suspicious file content.

Acceptance criteria:

- Quality issues are recorded.
- Affected pages are identified where possible.
- Users can review the issue.
- No original file is automatically altered.

## 5.7 Classification and extraction

### FR-AI-001 — Document classification

Priority: P0

Acceptance criteria:

- Supported document types can be classified.
- Model output is validated against supported classes.
- Confidence is recorded.
- Uncertain classifications are sent to human review.
- User can correct the classification.

### FR-AI-002 — Structured extraction

Priority: P0

Acceptance criteria:

- Extraction uses a document-type-specific schema.
- Every supported extracted field stores its evidence.
- Values are validated using Pydantic.
- Confidence is recorded.
- Invalid or unsupported values are flagged.
- Human corrections remain separate from raw extraction output.

### FR-AI-003 — Summarization

Priority: P1

Acceptance criteria:

- User can request a summary of an authorized document.
- Summary can include source-page references.
- The system indicates when information is not available in the document.

## 5.8 Validation engine

### FR-VAL-001 — Required-field validation

Priority: P0

Check required fields for each configured document type.

### FR-VAL-002 — Format validation

Priority: P0

Support configured validators such as:

- Dates.
- Amounts.
- Currency.
- Email addresses.
- Tax identifiers.
- Reference numbers.

### FR-VAL-003 — Arithmetic validation

Priority: P0

Check deterministic arithmetic such as:

- Subtotal plus tax equals total.
- Quantity multiplied by unit price matches line total within configured tolerances.
- Component totals match document totals.

### FR-VAL-004 — Duplicate validation

Priority: P0

Detect duplicates using configurable business keys and defined date or entity scopes.

### FR-VAL-005 — Cross-document validation

Priority: P0

Compare fields across related documents.

Examples:

- Purchase order vs invoice.
- Invoice vs delivery challan.
- Commercial invoice vs packing list.
- Policy vs claim form.

Acceptance criteria:

- Comparison rules are configurable.
- Each mismatch has severity and evidence.
- Missing values are distinguishable from mismatched values.
- Results can be assigned for human resolution.
- System does not automatically choose the correct source.

### FR-VAL-006 — Validation history

Priority: P0

Every validation run must retain:

- Ruleset version.
- Input document versions.
- Execution timestamp.
- Results.
- Errors.
- Actor or initiating job.

## 5.9 Review and approval

### FR-REV-001 — Review center

Priority: P0

Acceptance criteria:

- Original document and extracted fields appear together.
- Selecting a field opens its evidence location.
- Reviewer can correct a value.
- Reviewer can add a reason.
- Review state is visible.
- Every correction is auditable.

### FR-REV-002 — Approval

Priority: P0

Acceptance criteria:

- Authorized approver can approve or reject.
- Rejection requires a reason.
- Approval records actor and timestamp.
- Unauthorized users cannot approve.
- Approval cannot silently bypass unresolved mandatory checks.

## 5.10 Workflow and task management

### FR-WF-001 — Workflow templates

Priority: P0

A workflow template defines:

- Trigger.
- Steps.
- Conditions.
- Assignment rules.
- Required approvals.
- Completion conditions.

### FR-WF-002 — Workflow instances

Priority: P0

Acceptance criteria:

- An instance can be created from a template.
- Instance status is tracked.
- Failed steps are recorded.
- Completed steps cannot be silently rewritten.
- Workflow version is preserved.

### FR-TASK-001 — Task assignment

Priority: P0

Acceptance criteria:

- Tasks can be assigned to tenant members.
- Tasks have a status and optional due date.
- Assignees can update permitted fields.
- Managers can reassign tasks.
- Task history is retained.

### FR-TASK-002 — Reminders

Priority: P1

- Remind users about pending work.
- Support configurable reminders.
- Record notification delivery status.
- Prevent excessive duplicate notifications.

## 5.11 Search and AI assistant

### FR-SEARCH-001 — Keyword search

Priority: P0

Search authorized document metadata and OCR text.

### FR-SEARCH-002 — Semantic search

Priority: P1

Use embeddings to retrieve semantically related document content.

### FR-SEARCH-003 — Document Q&A

Priority: P1

Acceptance criteria:

- User question is limited to authorized documents.
- Retrieved content is supplied to the model.
- Answers cite relevant document and page references.
- Unsupported answers are identified.
- No cross-tenant content is retrieved.
- Search and assistant actions are auditable.

## 5.12 Reports and exports

### FR-REPORT-001 — CSV and Excel exports

Priority: P0

- Export approved extracted values.
- Include validation status.
- Support selected columns and filters.
- Protect exports with permissions.
- Record export events.

### FR-REPORT-002 — PDF reports

Priority: P1

Generate structured exception and workflow reports with evidence references.

## 5.13 Industry pack management

### FR-PACK-001 — Install pack

Priority: P0

Acceptance criteria:

- Authorized admin can enable a supported pack.
- Pack configuration is versioned.
- Pack installation does not modify another tenant's configuration.
- Pack-specific schemas and rules become available.

### FR-PACK-002 — Pack configuration

Priority: P1

Authorized admins can configure supported fields, document types and workflow settings without changing application code.

## 5.14 Integrations

### FR-INT-001 — Integration framework

Priority: P1

Support tenant-scoped integrations with:

- Email.
- Cloud storage.
- Accounting systems.
- WhatsApp through authorized providers.
- Customer APIs and webhooks.

Acceptance criteria:

- Credentials are encrypted.
- Permissions are scoped.
- Integration errors are logged.
- Retry policies are defined.
- Integrations can be disabled.

# 6. Non-Functional Requirements

## 6.1 Security

- Tenant isolation at application and database layers.
- RBAC and resource-level authorization.
- TLS for network communication.
- Encryption at rest.
- Secure password hashing.
- Rate limiting.
- Malware scanning.
- Signed file download URLs.
- Secure secrets management.
- Auditable administrative actions.

## 6.2 Reliability

- Background job retry policies.
- Idempotent processing.
- Dead-letter handling for repeated failures.
- Database backup and restoration testing.
- Storage integrity verification.
- Health checks for dependencies.

## 6.3 Performance

Initial targets, to be validated through load testing:

- Common metadata API requests: p95 under 500 ms.
- Paginated document listing: p95 under 1 second.
- Upload acknowledgment: independent of OCR completion.
- Document processing: asynchronous, with progress reporting.
- Search latency: p95 under 2 seconds for initial expected data volumes.

Large PDFs and LLM operations must not block API request workers.

## 6.4 Scalability

- Independent API and worker processes.
- Configurable Celery worker concurrency.
- Object storage for binary files.
- Database indexes and query optimization.
- Queue-based workload control.
- Future horizontal scaling.

## 6.5 Data governance

- Customer data ownership and export.
- Defined retention schedules.
- Permanent deletion workflows.
- Customer consent for AI providers and data processing.
- No training on customer data without explicit authorization.
- Document access and export audit history.

# 7. Database Design

Use PostgreSQL with UUID primary keys.

## 7.1 Entity relationships

```
erDiagram
    TENANTS ||--o{ TENANT_MEMBERSHIPS : has
    USERS ||--o{ TENANT_MEMBERSHIPS : joins
    TENANTS ||--o{ CLIENTS : owns
    TENANTS ||--o{ WORKSPACES : owns
    CLIENTS ||--o{ WORKSPACES : associated
    WORKSPACES ||--o{ DOCUMENTS : contains
    DOCUMENTS ||--o{ DOCUMENT_VERSIONS : versions
    DOCUMENT_VERSIONS ||--o{ DOCUMENT_PAGES : contains
    DOCUMENT_VERSIONS ||--o{ EXTRACTION_RUNS : processed
    EXTRACTION_RUNS ||--o{ EXTRACTED_FIELDS : produces
    WORKSPACES ||--o{ WORKFLOW_INSTANCES : runs
    WORKFLOW_TEMPLATES ||--o{ WORKFLOW_INSTANCES : creates
    WORKFLOW_INSTANCES ||--o{ TASKS : contains
    TASKS ||--o{ APPROVALS : receives
    TENANTS ||--o{ AUDIT_EVENTS : records
    INDUSTRY_PACKS ||--o{ DOCUMENT_TYPES : defines
    INDUSTRY_PACKS ||--o{ VALIDATION_RULES : defines
    TENANTS ||--o{ TENANT_PACK_INSTALLATIONS : installs
    INDUSTRY_PACKS ||--o{ TENANT_PACK_INSTALLATIONS : enabled
```

## 7.2 Core tables and columns

### tenants

- id UUID PRIMARY KEY
- name VARCHAR(255)
- slug VARCHAR(100) UNIQUE
- status VARCHAR(30)
- settings JSONB
- created_at TIMESTAMPTZ
- updated_at TIMESTAMPTZ

### users

- id UUID PRIMARY KEY
- email CITEXT UNIQUE
- password_hash TEXT
- full_name VARCHAR(255)
- status VARCHAR(30)
- last_login_at TIMESTAMPTZ
- created_at TIMESTAMPTZ

### tenant_memberships

- id UUID PRIMARY KEY
- tenant_id UUID
- user_id UUID
- status VARCHAR(30)
- joined_at TIMESTAMPTZ
- UNIQUE (tenant_id, user_id)

### roles

- id UUID PRIMARY KEY
- tenant_id UUID NULL
- name VARCHAR(100)
- is_system BOOLEAN

### permissions

- id UUID PRIMARY KEY
- code VARCHAR(150) UNIQUE
- description TEXT

### role_permissions

- role_id UUID
- permission_id UUID
- PRIMARY KEY (role_id, permission_id)

### clients

- id UUID PRIMARY KEY
- tenant_id UUID
- name VARCHAR(255)
- external_ref VARCHAR(150)
- metadata JSONB
- status VARCHAR(30)
- created_at TIMESTAMPTZ

### workspaces

- id UUID PRIMARY KEY
- tenant_id UUID
- client_id UUID NULL
- workspace_type VARCHAR(80)
- reference VARCHAR(150)
- name VARCHAR(255)
- status VARCHAR(30)
- metadata JSONB
- created_at TIMESTAMPTZ

### documents

- id UUID PRIMARY KEY
- tenant_id UUID
- workspace_id UUID NULL
- document_type_id UUID NULL
- name VARCHAR(255)
- status VARCHAR(40)
- source VARCHAR(50)
- created_by UUID
- created_at TIMESTAMPTZ

### document_versions

- id UUID PRIMARY KEY
- document_id UUID
- version_number INTEGER
- storage_key TEXT
- sha256 CHAR(64)
- mime_type VARCHAR(120)
- file_size BIGINT
- page_count INTEGER
- is_original BOOLEAN
- created_by UUID
- created_at TIMESTAMPTZ
- UNIQUE (document_id, version_number)

### document_pages

- id UUID PRIMARY KEY
- document_version_id UUID
- page_number INTEGER
- extracted_text TEXT
- page_metadata JSONB

### extraction_runs

- id UUID PRIMARY KEY
- document_version_id UUID
- model_name VARCHAR(150)
- model_version VARCHAR(100)
- schema_version VARCHAR(100)
- status VARCHAR(40)
- raw_output JSONB
- started_at TIMESTAMPTZ
- completed_at TIMESTAMPTZ

### extracted_fields

- id UUID PRIMARY KEY
- extraction_run_id UUID
- field_key VARCHAR(150)
- extracted_value JSONB
- confidence NUMERIC(5,4)
- evidence JSONB
- review_status VARCHAR(30)
- created_at TIMESTAMPTZ

### field_corrections

- id UUID PRIMARY KEY
- extracted_field_id UUID
- corrected_value JSONB
- reason TEXT
- corrected_by UUID
- corrected_at TIMESTAMPTZ

### document_relationships

- id UUID PRIMARY KEY
- tenant_id UUID
- source_document_id UUID
- target_document_id UUID
- relationship_type VARCHAR(100)
- confidence NUMERIC(5,4)
- created_at TIMESTAMPTZ

### validation_rules

- id UUID PRIMARY KEY
- pack_id UUID
- code VARCHAR(150)
- definition JSONB
- version INTEGER
- enabled BOOLEAN

### validation_results

- id UUID PRIMARY KEY
- tenant_id UUID
- workspace_id UUID
- rule_id UUID
- run_id UUID
- status VARCHAR(30)
- severity VARCHAR(30)
- result JSONB
- created_at TIMESTAMPTZ

### workflow_templates

- id UUID PRIMARY KEY
- pack_id UUID NULL
- tenant_id UUID NULL
- name VARCHAR(255)
- version INTEGER
- definition JSONB
- status VARCHAR(30)

### workflow_instances

- id UUID PRIMARY KEY
- tenant_id UUID
- template_id UUID
- template_version INTEGER
- workspace_id UUID NULL
- status VARCHAR(40)
- started_at TIMESTAMPTZ
- completed_at TIMESTAMPTZ

### tasks

- id UUID PRIMARY KEY
- tenant_id UUID
- workflow_instance_id UUID
- title VARCHAR(255)
- assignee_id UUID
- status VARCHAR(40)
- priority VARCHAR(30)
- due_at TIMESTAMPTZ
- created_at TIMESTAMPTZ

### approvals

- id UUID PRIMARY KEY
- task_id UUID
- decision VARCHAR(30)
- actor_id UUID
- comments TEXT
- created_at TIMESTAMPTZ

### industry_packs

- id UUID PRIMARY KEY
- code VARCHAR(100) UNIQUE
- name VARCHAR(255)
- version VARCHAR(50)
- definition JSONB
- status VARCHAR(30)

### tenant_pack_installations

- id UUID PRIMARY KEY
- tenant_id UUID
- pack_id UUID
- enabled BOOLEAN
- configuration JSONB
- installed_at TIMESTAMPTZ
- UNIQUE (tenant_id, pack_id)

### processing_jobs

- id UUID PRIMARY KEY
- tenant_id UUID
- document_version_id UUID
- job_type VARCHAR(100)
- status VARCHAR(40)
- attempts INTEGER
- idempotency_key VARCHAR(255)
- error_details JSONB
- created_at TIMESTAMPTZ
- completed_at TIMESTAMPTZ

### audit_events

- id UUID PRIMARY KEY
- tenant_id UUID
- actor_id UUID NULL
- action VARCHAR(150)
- resource_type VARCHAR(100)
- resource_id UUID
- metadata JSONB
- ip_address INET NULL
- created_at TIMESTAMPTZ

## 7.3 Database implementation rules

- Use foreign keys and appropriate unique constraints.
- Use tenant-scoped composite constraints for related records.
- Index tenant_id on tenant-owned tables.
- Index common search fields and foreign keys.
- Use JSONB for flexible configurations and evidence, not for every relational field.
- Use pgvector for embeddings with a separate document/page reference.
- Keep audit events append-only.
- Use database migrations for every schema change.
- Do not hard-delete records that are subject to retention or audit requirements.
- Apply Row-Level Security with transaction-scoped tenant context where appropriate.
- Test connection-pool behavior to prevent tenant context leaking between requests.

# 8. API Specification

Base path: `/api/v1`

Authentication: Secure session or Bearer token according to deployment configuration.

## 8.1 Authentication

| Method | Endpoint                | Description             |
| ------ | ----------------------- | ----------------------- |
| POST   | `/auth/login`           | Authenticate            |
| POST   | `/auth/logout`          | End session             |
| POST   | `/auth/refresh`         | Refresh credentials     |
| POST   | `/auth/forgot-password` | Request password reset  |
| POST   | `/auth/reset-password`  | Complete password reset |
| GET    | `/auth/me`              | Current user            |

## 8.2 Tenant and users

| Method | Endpoint                  | Description             |
| ------ | ------------------------- | ----------------------- |
| GET    | `/tenants/me`             | Current tenant          |
| PATCH  | `/tenants/me`             | Update settings         |
| GET    | `/users`                  | List users              |
| POST   | `/users/invitations`      | Invite user             |
| PATCH  | `/users/{id}`             | Update user             |
| GET    | `/roles`                  | List roles              |
| POST   | `/roles`                  | Create role             |
| PUT    | `/roles/{id}/permissions` | Update role permissions |

## 8.3 Clients and workspaces

| Method | Endpoint           | Description       |
| ------ | ------------------ | ----------------- |
| GET    | `/clients`         | List clients      |
| POST   | `/clients`         | Create client     |
| GET    | `/clients/{id}`    | Client details    |
| PATCH  | `/clients/{id}`    | Update client     |
| GET    | `/workspaces`      | List workspaces   |
| POST   | `/workspaces`      | Create workspace  |
| GET    | `/workspaces/{id}` | Workspace details |
| PATCH  | `/workspaces/{id}` | Update workspace  |

## 8.4 Documents

| Method | Endpoint                     | Description           |
| ------ | ---------------------------- | --------------------- |
| POST   | `/documents`                 | Upload document       |
| POST   | `/documents/bulk-upload`     | Bulk upload           |
| GET    | `/documents`                 | List documents        |
| GET    | `/documents/{id}`            | Document details      |
| PATCH  | `/documents/{id}`            | Update metadata       |
| DELETE | `/documents/{id}`            | Request deletion      |
| GET    | `/documents/{id}/versions`   | Version history       |
| POST   | `/documents/{id}/versions`   | Add version           |
| POST   | `/documents/{id}/operations` | PDF operation         |
| POST   | `/documents/{id}/process`    | Start processing      |
| GET    | `/documents/{id}/preview`    | Get preview reference |

## 8.5 Processing and extraction

| Method | Endpoint                      | Description        |
| ------ | ----------------------------- | ------------------ |
| GET    | `/jobs/{id}`                  | Job status         |
| GET    | `/documents/{id}/extractions` | Extraction history |
| GET    | `/extractions/{id}`           | Extraction detail  |
| PATCH  | `/extractions/{id}`           | Correct field      |
| POST   | `/documents/{id}/classify`    | Classify document  |
| POST   | `/documents/{id}/ocr`         | Start OCR          |

## 8.6 Validation

| Method | Endpoint                              | Description    |
| ------ | ------------------------------------- | -------------- |
| POST   | `/workspaces/{id}/validate`           | Run validation |
| GET    | `/workspaces/{id}/validation-results` | Results        |
| GET    | `/validation-results/{id}`            | Result details |
| POST   | `/validation-results/{id}/resolve`    | Resolve issue  |
| GET    | `/validation-rules`                   | List rules     |
| POST   | `/validation-rules`                   | Create rule    |

## 8.7 Workflows and tasks

| Method | Endpoint                 | Description      |
| ------ | ------------------------ | ---------------- |
| GET    | `/workflow-templates`    | List templates   |
| POST   | `/workflow-templates`    | Create template  |
| POST   | `/workflows`             | Start workflow   |
| GET    | `/workflows/{id}`        | Workflow details |
| POST   | `/workflows/{id}/cancel` | Cancel workflow  |
| GET    | `/tasks`                 | List tasks       |
| GET    | `/tasks/{id}`            | Task details     |
| PATCH  | `/tasks/{id}`            | Update task      |
| POST   | `/tasks/{id}/assign`     | Assign task      |
| POST   | `/tasks/{id}/approve`    | Approve          |
| POST   | `/tasks/{id}/reject`     | Reject           |

## 8.8 Search and assistant

| Method | Endpoint                        | Description          |
| ------ | ------------------------------- | -------------------- |
| GET    | `/search`                       | Keyword search       |
| POST   | `/search/semantic`              | Semantic search      |
| POST   | `/assistant/query`              | Document Q&A         |
| GET    | `/assistant/conversations`      | List conversations   |
| GET    | `/assistant/conversations/{id}` | Conversation history |

## 8.9 Reports and integrations

| Method | Endpoint                 | Description           |
| ------ | ------------------------ | --------------------- |
| POST   | `/reports`               | Generate report       |
| GET    | `/reports`               | List reports          |
| GET    | `/reports/{id}`          | Report details        |
| GET    | `/reports/{id}/download` | Download report       |
| GET    | `/integrations`          | List integrations     |
| POST   | `/integrations`          | Configure integration |
| PATCH  | `/integrations/{id}`     | Update integration    |
| DELETE | `/integrations/{id}`     | Disable integration   |
| GET    | `/audit-events`          | Audit history         |

## 8.10 API response conventions

Successful synchronous response:

```
{
  "success": true,
  "data": {},
  "meta": {}
}
```

Asynchronous response:

```
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "queued"
  }
}
```

Error response:

```
{
  "success": false,
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "The requested document could not be found.",
    "details": {}
  }
}
```

Use standard HTTP status codes:

- 200: Successful request.
- 201: Resource created.
- 202: Processing accepted.
- 204: Successful operation without response body.
- 400: Invalid request.
- 401: Authentication required.
- 403: Permission denied.
- 404: Resource unavailable.
- 409: Conflict.
- 422: Validation error.
- 429: Rate limit exceeded.
- 500: Internal server error.

All list endpoints should support pagination, filtering and stable ordering.

# 9. Background Processing Architecture

Use Celery and Redis for asynchronous tasks.

## 9.1 Queues

- `file_processing`
- `ocr_processing`
- `ai_classification`
- `ai_extraction`
- `validation`
- `report_generation`
- `notifications`
- `maintenance`

## 9.2 Processing stages

```
UPLOAD
  |
  v
FILE_VALIDATION
  |
  v
QUALITY_CHECK
  |
  v
PREPROCESSING
  |
  v
OCR
  |
  v
CLASSIFICATION
  |
  v
EXTRACTION
  |
  v
VALIDATION
  |
  v
REVIEW_REQUIRED
  |
  v
APPROVED
  |
  v
COMPLETED
```

Failures must enter a recoverable failure state.

## 9.3 Job requirements

- Each job has a unique ID.
- Each job is idempotent where possible.
- Retry count and failure reason are recorded.
- Retry only transient failures automatically.
- Permanent failures require correction or manual intervention.
- Job progress is visible to the frontend.
- Queue saturation must not block upload APIs.
- Workers must verify tenant and document authorization before processing.

# 10. Industry Pack Configuration Interface

Every pack should implement a shared contract.

Example conceptual structure:

```
IndustryPack
    metadata
    document_types
    extraction_schemas
    validation_rules
    relationship_types
    workflow_templates
    report_templates
    permission_presets
    dashboard_widgets
```

Example pack:

```
code: manufacturing
version: 1.0.0

document_types:
  - purchase_order
  - supplier_invoice
  - delivery_challan
  - goods_receipt_note
  - quality_report

relationships:
  - purchase_order_to_invoice
  - purchase_order_to_delivery_challan
  - delivery_challan_to_receipt

workflows:
  - purchase_to_receipt

validation_rules:
  - supplier_match
  - item_match
  - quantity_match
  - rate_match
  - invoice_total_check

reports:
  - purchase_exception_report
  - supplier_document_report
```

This is an illustrative configuration contract. The actual schema must be defined and validated in code before loading pack configurations.

Pack definitions must be versioned and migrations must be controlled.

# 11. Frontend Requirements

## 11.1 Main navigation

1. Dashboard
2. Inbox
3. Documents
4. Clients
5. Workspaces
6. Review Center
7. Validation
8. Workflows
9. Tasks
10. Reports
11. AI Assistant
12. Integrations
13. Administration

## 11.2 Dashboard

Show:

- Total documents.
- Documents awaiting processing.
- Documents requiring review.
- Unresolved validation issues.
- Pending tasks.
- Overdue tasks.
- Recent workflow activity.

Dashboard data must be tenant-scoped and permission-aware.

## 11.3 Document workspace

The document workspace should contain:

- Document preview.
- Page navigation.
- File metadata.
- Version history.
- Extracted fields.
- OCR text.
- Processing history.
- Validation results.
- Related documents.
- Audit history.

## 11.4 Review center

The review center is a primary product screen.

It should provide:

- Source document preview.
- Extracted field list.
- Confidence indicators.
- Evidence navigation.
- Field correction.
- Review comments.
- Approval and rejection.
- Related discrepancy information.

## 11.5 Responsive design

The application must support desktop and tablet layouts. The initial product is desktop-first because document review and comparison are central workflows.

# 12. Testing Strategy

## 12.1 Unit tests

Test:

- Validation rules.
- Extraction schema validation.
- Permission functions.
- File metadata validation.
- Workflow transitions.
- Duplicate detection.

## 12.2 Integration tests

Test:

- Database persistence.
- Object storage.
- Redis and Celery.
- OCR processing.
- LLM extraction.
- PDF operations.
- Export generation.

## 12.3 API tests

Test:

- Authentication.
- Authorization.
- Tenant isolation.
- Input validation.
- Error responses.
- Pagination.
- Idempotency.

## 12.4 End-to-end tests

Test complete workflows:

1. Upload document.
2. Run quality checks.
3. Run OCR.
4. Classify.
5. Extract.
6. Validate.
7. Review.
8. Approve.
9. Generate report.

## 12.5 Security tests

- Cross-tenant access attempts.
- Unauthorized downloads.
- Malicious file uploads.
- Insecure direct object references.
- Session expiry.
- Role escalation.
- Webhook signature validation.
- Sensitive data exposure in logs.

## 12.6 AI evaluation

Maintain a human-verified dataset containing:

- Different document layouts.
- Digital PDFs.
- Scanned PDFs.
- Low-quality images.
- Multiple languages where supported.
- Handwritten content where supported.
- Different currencies and formats.

Measure:

- Field-level precision.
- Field-level recall.
- Exact-match accuracy.
- Normalized-value accuracy.
- Classification accuracy.
- Validation precision and recall.
- Human correction rate.

# 13. Development Milestones

| Milestone | Scope                                     | Target       |
| --------- | ----------------------------------------- | ------------ |
| M0        | Customer discovery and workflow selection | Weeks 1–2    |
| M1        | Backend, database, tenant security        | Weeks 3–4    |
| M2        | Document management and PDF operations    | Weeks 5–6    |
| M3        | OCR, classification and extraction        | Weeks 7–8    |
| M4        | Validation and review center              | Weeks 9–10   |
| M5        | Workflow and task automation              | Weeks 11–12  |
| M6        | First industry pack and customer pilot    | Weeks 13–14  |
| M7        | Search, exports and production hardening  | Weeks 15–16  |
| M8        | Second industry pack and integrations     | Weeks 17–20+ |

These estimates assume focused scope and sufficient frontend/backend capacity. A solo implementation may take longer.

# 14. First Release Acceptance Criteria

KnowledgeHub's first release is acceptable when:

1. A tenant can be created securely.
2. Tenant users can be invited and assigned roles.
3. Users can create clients and workspaces.
4. Documents can be uploaded individually and in bulk.
5. Documents can be previewed and downloaded with authorization.
6. Document versions are preserved.
7. PDF operations create derived files without destroying originals.
8. OCR can process supported scanned documents.
9. Classification and extraction return validated structured output.
10. Extracted fields include source evidence.
11. Quality issues are recorded.
12. Duplicate and missing-field checks work.
13. Related documents can be compared.
14. Users can correct extracted information.
15. Authorized reviewers can approve or reject results.
16. Tasks can be assigned.
17. Workflows have visible states and history.
18. Reports can be exported.
19. Audit events are recorded.
20. Tenant-isolation tests pass.
21. Backups can be restored.
22. At least one industry workflow is demonstrated successfully using a real customer-approved pilot dataset.

# 15. Customer Acquisition Requirements

## 15.1 Discovery target

Interview 30 businesses:

| Market                    | Target |
| ------------------------- | ------ |
| Manufacturing             | 6      |
| Import/export and freight | 6      |
| CA and audit              | 6      |
| Insurance                 | 3      |
| Law                       | 3      |
| Real estate               | 2      |
| Recruitment               | 2      |
| Hospitals                 | 2      |

## 15.2 Buyer personas

Business owner or partner:

- Business cost.
- Revenue impact.
- Operational risk.
- Purchasing decision.
- Return on investment.

Operations or admin manager:

- Document intake.
- Staff workload.
- Manual processes.
- Follow-ups.
- Exceptions and delays.

## 15.3 Pilot model

- 14-day pilot.
- One workflow.
- Up to 300 documents, subject to complexity.
- Initial pricing hypothesis: ₹7,500.
- Baseline and post-pilot measurement.
- Written permission for processing.
- Conversion to a recurring subscription after successful evaluation.

## 15.4 Acquisition channels

- Direct local visits.
- LinkedIn outreach.
- Business associations.
- CA and ERP referral partners.
- Tally implementation partners.
- Local IT service providers.
- Workflow demonstrations.

## 15.5 Sales success criteria

- Customer confirms a recurring problem.
- Workflow owner is identified.
- Current process can be measured.
- Pilot dataset is authorized.
- Customer agrees to success criteria.
- Customer is willing to pay for the pilot.
- Results are reviewed with the economic buyer.

# 16. Initial Commercial Model

Indicative prices to validate:

| Plan         | Monthly price | Document allowance |
| ------------ | ------------- | ------------------ |
| Starter      | ₹4,999        | 500                |
| Growth       | ₹9,999        | 1,500              |
| Professional | ₹17,999       | 4,000              |
| Enterprise   | Custom        | Custom             |

Onboarding, custom workflows, integrations and special support can be charged separately.

Pricing must account for page count, processing complexity, storage, AI costs and support.

# 17. Product Metrics

## Technical

- API latency.
- Job processing time.
- OCR success rate.
- Queue delay.
- Worker failure rate.
- Storage usage.
- Extraction accuracy.
- Validation precision and recall.

## Business

- Documents processed per customer.
- Review time saved.
- Monthly hours saved.
- Unresolved exception rate.
- Workflow completion rate.
- Weekly active users.
- Pilot conversion.
- Customer retention.
- Gross margin per customer.

# 18. Engineering Rules

1. Use a modular monolith for the first release.
2. Keep API, domain logic and infrastructure separate.
3. Use SQLAlchemy and Alembic for database management.
4. Use Pydantic for input, output and extraction validation.
5. Use Celery for asynchronous processing.
6. Store files outside PostgreSQL.
7. Preserve original documents.
8. Store every extraction run separately.
9. Preserve evidence for extracted fields.
10. Keep corrections separate from extraction results.
11. Use deterministic Python rules for arithmetic and format checks.
12. Treat LLM responses as untrusted input.
13. Do not permit unrestricted model-generated SQL.
14. Enforce tenant isolation in every domain module.
15. Test authorization and tenant isolation continuously.
16. Version industry packs, schemas and workflows.
17. Maintain OpenAPI specifications.
18. Keep migrations reversible where practical.
19. Write automated tests for every business rule.
20. Do not introduce microservices without a measurable operational reason.

# 19. Final Product Roadmap

## Phase 1 — Universal Foundation

- Authentication.
- Tenants.
- Users and roles.
- Clients.
- Workspaces.
- Document management.
- Storage.
- Audit.

## Phase 2 — Document Intelligence

- PDF processing.
- OCR.
- Classification.
- Extraction.
- Quality checks.
- Duplicate detection.

## Phase 3 — Business Validation

- Required-field checks.
- Format validation.
- Arithmetic validation.
- Cross-document comparison.
- Human review.

## Phase 4 — Workflow Automation

- Workflow templates.
- Workflow instances.
- Tasks.
- Assignments.
- Approvals.
- Reminders.
- Reports.

## Phase 5 — First Industry Pack

- Select through customer discovery.
- Configure schemas.
- Configure rules.
- Configure workflows.
- Run paid pilots.

## Phase 6 — Expansion

- Add packs where demand is proven.
- Add customer-requested integrations.
- Improve AI quality.
- Expand deployment capacity.

---

# 20. Final Product Definition

KnowledgeHub AI is not simply a document storage system and not simply an AI extraction application.

It is a business document operations platform.

Its foundation is document management and intelligence. Its differentiator is validation, evidence and exception handling. Its outcome is automated business workflows.

The platform should be developed once, while industry packs adapt it to different business processes.

**Primary development objective:** Build a secure universal document and workflow foundation, validate one industry workflow with paying customers, and expand only when the next workflow demonstrates repeatable demand.

## How to use this PRD during development

I recommend treating this as the master specification and splitting implementation into separate engineering documents:

| Document                          | Purpose                                                  |
| --------------------------------- | -------------------------------------------------------- |
| 01 — Architecture Design          | Module boundaries, components, deployment and security   |
| 02 — Database ERD                 | Exact relationships, constraints, indexes and migrations |
| 03 — API Contract                 | Request/response schemas, errors and authorization       |
| 04 — Functional Specifications    | Screen-by-screen behavior and edge cases                 |
| 05 — Industry Pack Specifications | Document schemas, rules and workflow definitions         |
| 06 — Test Plan                    | Unit, integration, security and acceptance tests         |
| 07 — Deployment Guide             | Docker, Ubuntu, backups, monitoring and production setup |

One important implementation decision: Don't start coding all the modules simultaneously. Begin with the tenant/security foundation and document lifecycle. Meanwhile, complete customer discovery to select the first industry pack.

The next engineering artifact I would build is the complete PostgreSQL database ERD and SQLAlchemy model specification, including tenant isolation, composite foreign keys, indexes, enums, JSONB structures and Alembic migration order.
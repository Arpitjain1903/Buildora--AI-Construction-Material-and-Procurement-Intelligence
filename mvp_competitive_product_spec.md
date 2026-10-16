# Competitive MVP Product Specification
## India-first construction material and cost intelligence

Date: 18 September 2026
Status: Initial product design

## 1. Product decision

### Working product definition

A supplier-neutral construction procurement intelligence layer for Indian contractors and design-build firms.

> Upload a BOQ, supplier quotes and project records. The system normalizes materials, calculates effective delivered cost, identifies what should be bought and when, flags variance and delay risk, and explains every recommendation from its source documents.

### Target customer

- Owner-led residential contractors
- Design-build firms
- Small and mid-sized builders
- One city or state at first
- Approximately 5–30 active projects

### Primary buyer

Contractor-owner, project director or procurement head.

### Primary user

Site engineer, site supervisor or procurement coordinator.

### Secondary reviewer

Quantity surveyor, architect, civil engineer or accounts administrator.

## 2. Competitive design principle

Do not build another all-in-one construction-management system.

| Competitor/category | What it already does | Do not copy in MVP |
|---|---|---|
| SiteSetu | WhatsApp, drawings, BOQ/material tracking, DPR, schedules, quality evidence and AI assistant | Full WhatsApp/project-management suite |
| Powerplay | Site tracking, stock visibility, purchase orders, GRNs, labour and project reports | Full site operations and HR/payroll |
| QSmaster | India-focused drawing-to-BOQ extraction, IS 1200/CPWD formats, review and Excel export | Automated drawing takeoff as the main wedge |
| IntoAEC | AI BOQ item creation, templates, material library, costing and accounting integrations | Generic AI BOQ editor |
| Moglix | Large-scale source-to-site procurement, supplier aggregation, approved-vendor and spend analytics | Supplier inventory network and enterprise procurement scale |
| Infra.Market | Broad construction material catalogue and supply platform | Owning inventory and competing on catalogue breadth |
| TestFit/Autodesk Forma | Site feasibility, generative planning and design analysis | Generic generative site design |
| Rheaply/Globechain | Reuse listings, inventory and ESG reporting | Public surplus marketplace in version one |

SiteSetu publicly describes ingestion of WhatsApp, drawings and schedules, BOQ/material tracking, procurement and an AI assistant. Powerplay publicly describes stock management, purchase orders and GRNs. QSmaster publicly describes AI drawing-to-BOQ generation for Indian standards. Moglix publicly describes source-to-site infrastructure procurement and landed-cost/spend analytics. [^1](https://sitesetu.app/) [^2](https://www.getpowerplay.in/) [^3](https://qsmaster.com/boq-generation) [^4](https://business.moglix.com/our-solutions/infrastructure)

### Your differentiation

Your MVP should answer a question these products do not clearly own as a neutral layer:

> For this project, this stage and this requirement, which purchase option has the best effective delivered cost, availability and risk—and why?

## 3. MVP promise

### Before

- BOQ in one Excel file
- Quotes in WhatsApp/PDF/images
- Supplier names inconsistent
- Units and pack sizes unclear
- Purchases tracked separately
- Site team discovers shortages late
- Owner cannot see whether the best decision was made

### After

- One normalized material register
- Quotes compared on like-for-like terms
- Effective delivered cost, not just unit price
- Buy-now/buy-later/verify queue
- BOQ vs quote vs purchase vs receipt variance
- Delivery and stockout risk alerts
- Weekly owner report with evidence links

## 4. MVP user journeys

### Journey A: Create project

1. User creates organization and project.
2. Enters city, project type, area, construction stage and target completion date.
3. Selects a rate source: user-provided quotes, rate book or historical project data.
4. System creates a project workspace and records data freshness.

### Journey B: Upload BOQ

1. User uploads XLSX/CSV.
2. System detects headers, rows, units, rates and revisions.
3. AI proposes canonical material mappings.
4. User reviews only ambiguous mappings.
5. System saves the original file, extracted fields, mapping confidence and reviewer decision.
6. Approved rows become the current BOQ baseline.

MVP supports PDF/image quote extraction, but the user must approve extracted values before they affect a calculation.

### Journey C: Compare quotes

1. User uploads or pastes supplier quotes.
2. System extracts supplier, item, specification, quantity, unit price, GST, freight, MOQ, payment terms and delivery date.
3. System maps quote lines to BOQ lines.
4. Ambiguous grade, unit or pack-size mappings enter a review queue.
5. Rules engine calculates effective delivered cost.
6. User sees cheapest unit price, cheapest delivered cost, fastest delivery, lowest-risk option and missing evidence.

### Journey D: Generate procurement plan

1. User selects project stage and planned work dates.
2. System uses approved BOQ quantities, existing stock, open orders, supplier delivery times and minimum order quantities.
3. It generates buy now, buy later, verify, do not buy yet, potential stockout and potential excess.

The initial scheduling logic is rules-based. The LLM can explain the result but cannot change quantities or dates without a user-approved action.

### Journey E: Record receipt and variance

1. Site user records ordered, received, rejected and delayed quantities.
2. User can enter data manually or upload a challan/invoice.
3. System compares BOQ, quote, purchase and receipt.
4. Owner sees price variance, quantity variance, rejected material, late delivery, emergency purchase and excess stock.

### Journey F: Weekly owner report

Report includes total planned material spend, purchases due in the next 7–14 days, top cost variances, top quantity variances, delayed deliveries, unresolved questions and decisions requiring approval.

The report should be exportable as PDF and XLSX and shareable as a reviewable message. Do not send RFQs or purchase orders automatically in MVP.

## 5. Feature priorities

### P0 — must build

- Organization, project and role access
- XLSX/CSV BOQ upload
- XLSX/CSV quote upload
- Manual quote entry
- PDF/image quote extraction with review queue
- Original-file preservation
- Canonical material family, grade, size, unit and aliases
- Unit conversion and mapping confidence
- Unit price, GST, freight, discount, MOQ and delivery date
- Effective delivered cost
- BOQ vs ordered vs received quantity
- Existing stock and open-order deductions
- Buy-now/buy-later recommendation
- Delivery risk and excess/shortage flags
- Source file/page/row reference
- Calculation version, assumptions and reviewer action
- Quote comparison, procurement queue, variance dashboard and weekly report
- XLSX/PDF export

### P1 — first pilot follow-up

- Mobile receipt entry
- Offline field mode
- WhatsApp-compatible reports
- Supplier reliability history
- Delivery fill-rate and delay metrics
- Reusable organization material dictionary
- User rate-book versioning
- Project-stage templates
- Email RFQ draft requiring review
- Multi-project view

### P2 — only after paid retention

- Drawing/PDF takeoff
- IFC import
- Site map and geospatial context
- Weather and hazard alerts
- Local building-rule checklist
- Project-linked surplus/reuse matching
- Supplier APIs
- Accounting/ERP integrations
- Payments or marketplace settlement
- Carbon/material passports

## 6. Screens to design

1. Portfolio dashboard: active projects, material spend, open decisions, delays and review items.
2. Project overview: stage, BOQ value, spend, orders, exceptions and data freshness.
3. Import/review queue: original item, proposed material, specification, unit, quantity, confidence and approve/edit/reject.
4. Quote comparison: BOQ item, supplier, specification match, price, tax, freight, delivered cost, delivery, MOQ, reliability and action.
5. Procurement queue: material, required date, stock, open order, net requirement, suggested quantity, best option and approval status.
6. Variance dashboard: BOQ vs planned vs ordered vs received, price variance, delivery delay, emergency purchases and excess.
7. Evidence drawer: source, extracted field, formula, rate version, corrections and timestamp.

## 7. Core data model

```text
Organization
  └── Project
        ├── ProjectMember
        ├── Document
        ├── BOQ ── BOQLine
        ├── SupplierQuote ── QuoteLine
        ├── PurchaseOrder ── PurchaseLine
        ├── Receipt ── ReceiptLine
        ├── MaterialIssue
        ├── ProcurementRecommendation
        ├── VarianceEvent
        └── AuditEvent

CanonicalMaterial
  ├── MaterialAlias
  ├── MaterialVariant
  ├── UnitConversion
  └── MaterialEvidence

Supplier
  ├── SupplierLocation
  ├── SupplierQuote
  ├── DeliveryEvent
  ├── QualityEvent
  └── SupplierReliabilitySnapshot
```

Important fields include original description, canonical material, specification, unit, quantity, rate, source document, source location, revision, mapping confidence, quote date, validity date, tax, freight, discount, MOQ, promised delivery, effective delivered cost, recommendation type, assumptions and approval status.

## 8. AI and rules architecture

### AI responsibilities

- Extract fields from documents
- Normalize names and aliases
- Classify materials
- Detect missing fields
- Explain calculations
- Summarize exceptions
- Translate reports

### Rules engine responsibilities

- Unit conversion
- Quantity arithmetic
- Tax and freight
- Delivered cost
- Stock deduction
- Net requirement
- Date and lead-time logic
- Variance thresholds
- Scenarios

The LLM cannot directly mutate approved BOQ quantities, material grade, supplier selection, purchase status, payment status or professional-review status. Every model-generated field has a confidence, source and review status.

## 9. Competitor-response matrix

| Capability | SiteSetu | Powerplay | QSmaster | Moglix | Your MVP |
|---|---:|---:|---:|---:|---:|
| WhatsApp/site evidence | Strong | Partial | No | Enterprise | Later/P1 |
| Project management | Strong | Strong | Limited | Enterprise | Minimal |
| Drawing-to-BOQ | Promoted | Not core | Strong | Not core | Exclude from P0 |
| BOQ normalization | Partial | Not core | BOQ output | Enterprise/custom | Core |
| Supplier quote ingestion | Not clearly central | Not clearly central | Not central | Procurement network | Core |
| Neutral multi-quote comparison | Not clearly central | Not clearly central | Not central | Supply-side | Core |
| Delivered-cost calculation | Not clearly central | Not clearly central | Costing-oriented | Enterprise | Core for small firms |
| Buy timing | Schedule-linked | Tracking/reporting | Procurement use case | Enterprise supply chain | Core rules engine |
| Variance alerts | Project/site focus | Tracking/reporting | Not core | Spend analytics | Core |
| Supplier reliability from receipts | Not clearly central | Possible | Not core | Enterprise data | Differentiator |
| Site feasibility | Not core | Not core | Not core | Not core | P2 |
| Reuse linked to BOQ need | Not core | Not core | Not core | Not core | P2 differentiator |
| Evidence trail | Strong project evidence | Reports | BOQ audit trail | Enterprise governance | Core |

## 10. MVP acceptance criteria

### Quality

- 95% of uploaded lines receive mapped, needs review or rejected status.
- No ambiguous unit or grade is silently accepted.
- Original source remains accessible.
- Every delivered-cost result is reproducible from stored inputs.
- Unit, tax and freight calculations have automated tests.

### Workflow

- New project created in under 10 minutes.
- Weekly quote update processed in under 30 minutes after onboarding.
- Site receipt recorded in under 2 minutes.
- Owner finds top exceptions in under 3 minutes.

### Trust

- No safety-critical recommendation is labelled approved by the system.
- Every recommendation shows source, date, assumptions and confidence.
- User approval is required before sending an RFQ or changing an approved baseline.
- Tenant/project access tests pass.

### Business validation

- At least 2 paid pilot customers.
- At least 4 of 6 pilots use it weekly.
- At least 3 customers document a changed purchase decision.
- At least 1.5% reduction in addressable material spend or 4 hours saved weekly.
- No increase in stockouts, rejected material, rework or delays.

## 11. Build sequence

### Sprint 0 — 3–5 days

Choose one city and project type, recruit two design partners, collect sample BOQs/quotes/receipts and create the initial 20–40 item material dictionary.

### Sprint 1 — 1 week

Project/authentication shell, file upload, BOQ/quote parsing, raw document preservation and review queue.

### Sprint 2 — 1 week

Canonical material model, aliases, unit conversion, mapping UI and approval history.

### Sprint 3 — 1 week

Quote comparison, delivered-cost engine, missing-field warnings and evidence drawer.

### Sprint 4 — 1 week

Stock/open-order model, net requirement, buy-now/buy-later rules and procurement queue.

### Sprint 5 — 1 week

Receipt entry, variance engine, delivery risk and owner dashboard.

### Sprint 6 — 1 week

Weekly report, XLSX/PDF export, roles, audit log and pilot onboarding.

### Sprint 7 — 1–2 weeks

Pilot fixes, material dictionary expansion, supplier reliability metrics, performance and security hardening.

## 12. Final positioning

Do not position this as an AI architect, autonomous builder, cheapest-product marketplace, engineer replacement or general construction ERP.

Position it as:

> **A trusted decision layer for construction purchases: understand the BOQ, compare the real delivered cost, buy at the right time and keep every decision explainable.**

This is narrow enough to build, differentiated enough to matter and connected to the larger construction-planning vision.

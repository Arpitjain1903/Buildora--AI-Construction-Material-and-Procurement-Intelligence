# Buildora AI — Intelligence for Smarter Construction

> **AI-Powered Material & Procurement Intelligence Platform for Construction, Engineering Take-Off, and Circular Sourcing.**

---

## 🏗️ Overview

**Buildora AI** is a full-stack engineering and procurement decision platform engineered specifically for residential contractors, design-build firms, and developers. It bridges site context, engineering standards (BIS/IS codes), material take-offs, multi-vendor delivered cost comparisons, circular material reuse, and multi-hazard renovation planning into a single unified system.

---

## ⚡ Quick Start

### 1. Requirements
- Python 3.10+ (Python 3.12 recommended)
- `pip install -r requirements.txt` (or install `fastapi uvicorn sqlalchemy pydantic requests`)

### 2. Launch the Platform
```powershell
python -m uvicorn python_app.main:app --reload --port 8000
```

Open your browser at:
```
http://localhost:8000/
```

### 3. Demo Credentials
- **Contractor Owner**: `owner@demo.local` / `owner123` *(Full access, approvals, budget oversight)*
- **Site User**: `site@demo.local` / `site123` *(Field receipts, stock entry, inspection logging)*

---

## 🧩 Architectural Modules

1. **Module 1 — Material Quantity Take-Off & Municipal Feasibility**:
   - Automated concrete volume ($m^3$), cement bags, aggregate (fine & coarse), structural rebar scheduling, and brick/AAC masonry.
   - Natural language project intake parser (`wizFreeText`).
   - Municipal bye-law compliance checker (FAR/FSI, ground coverage %, setbacks).
2. **Module 2 — Circular Marketplace & Reused Materials**:
   - Reused vs New material comparison with freight distance logistics.
   - Computer vision & rule-based material condition grader (Grade A/B/C).
   - Carbon ($CO_2$) and cost savings analytics.
3. **Module 3 — Climate, Weather & Regulatory Durability**:
   - IS 456 durability rules (exposure classes, minimum cover, w/c ratio).
   - IS 1893:2016 seismic zone factor lookup & IS 875 wind pressure computation.
   - Live weather integration via Open-Meteo with concrete curing schedule and rain alerts.
   - Interactive GIS Leaflet hazard map.
4. **Module 4 — Multi-Hazard Renovation & Structural Repair**:
   - Structural risk assessment scoring based on building age and visible distress.
   - Concrete crack and spalling damage photo analyzer.
   - Specialized repair sequencing protocols (epoxy injection, micro-concrete jacketing, polymer repair).
5. **Module 5 — Layout & Natural Ventilation Optimization**:
   - IS 3362 natural ventilation & window area calculations.
   - Cross-ventilation flow path suggestions.
6. **Financial ML Analytics**:
   - Price trend forecasting factoring seasonal monsoon cycles and logistics fuel indices.
   - Modified Z-Score over-invoicing and vendor anomaly detection.
   - Multi-parameter supplier reliability scoring.

---

## 🧪 Testing

Run the automated test suite:
```powershell
python -m pytest
```
*Current test suite: 63 passed across 6 test modules.*

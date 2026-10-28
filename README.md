# Vyapari AI - Python FastAPI Backend

FastAPI backend service handling all API requests, Supabase PostgreSQL database transactions, and Google Gemini AI processing for **Vyapari AI**.

---

## 🚀 Features

- **Supabase Authentication & Business Profile:**
  - `POST /api/auth/register`: Creates shopkeeper credentials in Supabase Auth & registers business profile in `businesses` table.
  - `POST /api/auth/login`: Authenticates shopkeeper, fetches live business details, and returns JWT token.
  - `GET /api/auth/me`: Returns current logged-in business profile.
  - `PUT /api/business/me`: Updates shop name, owner name, category, or preferred language.

- **Inventory Management (PostgreSQL with RLS):**
  - `GET /api/inventory/products`: Fetch live catalog with search, filter, and sorting.
  - `POST /api/inventory/products`: Add new inventory product.
  - `PUT /api/inventory/products/{id}`: Update product details and prices.
  - `DELETE /api/inventory/products/{id}`: Delete product.
  - `POST /api/inventory/add-stock`: Atomically add inward stock and log movement.
  - `POST /api/inventory/deduct-sale`: Atomically deduct sold stock, update balance, and trigger alerts.
  - `GET /api/inventory/movements`: Fetch real-time audit ledger.

- **Sales Processing:**
  - `POST /api/sales/record`: Multi-item sale builder, validates stock and deducts atomically.
  - `GET /api/sales`: Historical sales list.

- **Dashboard & Analytics:**
  - `GET /api/dashboard/summary`: Aggregated dashboard payload (today's revenue, transactions, stock value, low stock warnings, recent activity, business info).
  - `GET /api/reports`: Timeframe analytics (Today, This Week, This Month) with best-sellers, slow-movers, and 7-day trend.

- **AI & Voice Engine (Google Gemini 2.0 Flash-Lite):**
  - `POST /api/ai/interpret-voice`: Sends speech transcription (Telugu or English) + available store products to Gemini and returns structured action JSON with natural Telugu explanation.

- **Notifications:**
  - `GET /api/notifications`: Live alerts.
  - `POST /api/notifications/{id}/read`: Mark as read.

---

## 📦 Running the Server

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Ensure `.env` contains your Supabase and Gemini keys:
```properties
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
GEMINI_API_KEY=your-gemini-api-key
PORT=8000
```

### 3. Start the Server
```bash
python run.py
```
Or directly with uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger OpenAPI documentation is available at:
👉 **`http://localhost:8000/docs`**


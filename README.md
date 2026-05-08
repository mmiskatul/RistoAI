# RistoAI Backend

## 1. High-Level Architecture Explanation
RistoAI uses a layered FastAPI backend built around clean architecture boundaries:
- API layer in `app/api` exposes versioned HTTP endpoints only.
- Service layer in `app/services` owns business rules, RBAC checks, order pricing, analytics orchestration, and AI insight generation.
- Repository layer in `app/repositories` encapsulates MongoDB access using async Motor.
- Schema layer in `app/schemas` defines request and response DTOs with Pydantic v2.
- Model layer in `app/models` defines MongoDB-oriented document contracts.
- Core and config modules centralize settings, security, logging, constants, and exception handling.

The application is designed for MongoDB Atlas, async request handling, JWT authentication, and modular domain growth. All domain features are wired through dependency injection so repositories and services stay replaceable.

## 2. Folder Structure
```text
app/
  main.py
  api/
    v1/
      endpoints/
      router.py
  config/
    settings.py
  core/
    constants.py
    enums.py
    exceptions.py
    logging.py
    security.py
  db/
    indexes.py
    mongodb.py
  dependencies/
    auth.py
    services.py
  middleware/
    request_context.py
  models/
    ai_insight.py
    analytics.py
    base.py
    branch.py
    customer.py
    menu.py
    notification.py
    order.py
    restaurant.py
    user.py
  repositories/
    base.py
    ai_insight.py
    analytics_snapshot.py
    branch.py
    customer.py
    menu.py
    notification.py
    order.py
    restaurant.py
    user.py
  schemas/
    ai_insight.py
    analytics.py
    auth.py
    branch.py
    common.py
    customer.py
    menu.py
    notification.py
    order.py
    restaurant.py
    staff.py
  services/
    base.py
    ai_insight.py
    analytics.py
    auth.py
    branch.py
    customer.py
    menu.py
    notification.py
    order.py
    restaurant.py
    staff.py
    strategies/
      base.py
      demand_forecast.py
      menu_optimization.py
      recommendations.py
      waste_reduction.py
  tests/
    conftest.py
    test_auth.py
    test_menu.py
    test_orders.py
    test_protected_routes.py
    test_restaurants.py
```

## 3. Database Schema Design
Core collections:
- `users`: identity, password hash, role, active flag, restaurant assignments, branch assignments.
- `restaurants`: owner reference, contact details, address, config settings.
- `branches`: restaurant reference, branch metadata, assigned managers.
- `menu_categories`: restaurant reference, display grouping and sort order.
- `menu_items`: restaurant reference, optional branch reference, category reference, price, availability, prep time, tags.
- `customers`: restaurant reference, optional branch reference, contact details, lifecycle totals.
- `orders`: restaurant reference, branch reference, optional customer reference, embedded order items, totals, payment state, order state.
- `analytics_snapshots`: persisted generated analytics payloads for later inspection or chart caching.
- `ai_insights`: persisted recommendation outputs keyed by insight type.
- `notifications`: user-targeted notifications with read state.

Indexes included:
- Unique `users.email`
- Foreign-key style indexes on `restaurant_id`, `branch_id`, `customer_id`
- `orders.order_status`
- `created_at` indexes across major collections
- `menu_items.availability`

## 4. Design Patterns Used and Why
- Repository Pattern: centralized in `app/repositories/base.py` and specialized repos so Mongo queries are isolated from domain logic.
- Service Layer Pattern: centralized in `app/services/*` so route handlers remain thin and business rules stay reusable.
- Dependency Injection: FastAPI `Depends` in `app/dependencies/*` wires repositories and services per request.
- Strategy Pattern: `app/services/strategies/*` makes AI insight generation pluggable for future ML-backed implementations.
- Singleton Pattern: `app/db/mongodb.py` shares a single Motor client across the app lifecycle.
- Factory-style token creation: `TokenManager` in `app/core/security.py` encapsulates JWT creation for access and refresh tokens.

## 5. Full Backend Code by File
The repository contains the full codebase under `app/` with each file separated by responsibility. Key entry points:
- `app/main.py`: app factory, middleware, exception handlers, lifespan hooks.
- `app/dependencies/services.py`: service composition root.
- `app/services/order.py`: backend-side order pricing and status transition validation.
- `app/services/ai_insight.py`: pluggable AI insight orchestration.
- `app/api/v1/router.py`: versioned route registration.

## 6. .env.example
See [`.env.example`](./.env.example).

## 7. requirements.txt
See [`requirements.txt`](./requirements.txt).

## 8. How To Run Locally
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in the MongoDB Atlas connection details.
4. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```
5. Open docs:
   - Swagger UI: `http://localhost:8000/docs`
   - OpenAPI JSON: `http://localhost:8000/openapi.json`

## 9. MongoDB Atlas Setup
1. Create a cluster in MongoDB Atlas.
2. Create a database user with read/write access.
3. Add your development IP to the Atlas network access list.
4. Paste the SRV URI into `MONGODB_URI`.
5. Set `DATABASE_NAME` to the target logical database, for example `ristoai`.
6. Start the API; indexes are created automatically during startup.

## 10. AWS S3 Upload Setup
The backend image upload endpoint now uses AWS S3 only. Set all four of these environment variables on the backend:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET`
- `AWS_REGION`

Behavior:
- `POST /api/v1/upload/image` writes images to S3.
- If AWS S3 is not fully configured, image upload endpoints fail with a configuration error until the backend is fixed.
- `GET /api/v1/upload/aws/config-status` shows whether the S3 config is complete.
- `POST /api/v1/upload/aws/image/precheck` validates the file before upload.
- `POST /api/v1/upload/aws/verify` checks SDK availability, bucket access, and a safe write/delete cycle.

Recommended deployment check after the server is live:
1. Open `GET /health` and confirm it returns `{"status":"ok",...}`.
2. Authenticate with a real user.
3. Call `POST /api/v1/upload/aws/verify`.
4. Confirm `configured`, `bucket_accessible`, and `write_test_passed` are all `true`.
5. Upload a real image through `POST /api/v1/upload/image`.

## 11. Sample API Request/Response Examples
### Register
Request:
```json
{
  "full_name": "Risto Owner",
  "email": "owner@example.com",
  "password": "OwnerPass123",
  "phone": "+15550001111"
}
```
Response:
```json
{
  "user": {
    "id": "65f0c4...",
    "email": "owner@example.com",
    "full_name": "Risto Owner",
    "phone": "+15550001111",
    "role": "restaurant_owner",
    "is_active": true,
    "restaurant_ids": [],
    "branch_ids": [],
    "created_at": "2026-03-12T00:00:00+00:00",
    "updated_at": "2026-03-12T00:00:00+00:00"
  },
  "tokens": {
    "access_token": "jwt-access-token",
    "refresh_token": "jwt-refresh-token",
    "token_type": "bearer"
  }
}
```

### Create Restaurant
Request:
```json
{
  "name": "Risto Prime",
  "description": "Flagship outlet",
  "cuisine_type": "Italian",
  "contact_email": "hello@ristoprime.com",
  "contact_phone": "+15550002222",
  "address": "123 Main Street",
  "settings": {"tax_rate": 0.1}
}
```
Response:
```json
{
  "id": "65f0c5...",
  "owner_id": "65f0c4...",
  "name": "Risto Prime",
  "description": "Flagship outlet",
  "cuisine_type": "Italian",
  "contact_email": "hello@ristoprime.com",
  "contact_phone": "+15550002222",
  "address": "123 Main Street",
  "settings": {"tax_rate": 0.1},
  "created_at": "2026-03-12T00:05:00+00:00",
  "updated_at": "2026-03-12T00:05:00+00:00"
}
```

### Create Order
Request:
```json
{
  "restaurant_id": "65f0c5...",
  "branch_id": "65f0c6...",
  "items": [
    {"menu_item_id": "65f0c7...", "quantity": 2}
  ],
  "discount": 1.0,
  "payment_status": "pending"
}
```
Response:
```json
{
  "id": "65f0c8...",
  "restaurant_id": "65f0c5...",
  "branch_id": "65f0c6...",
  "customer_id": null,
  "items": [
    {
      "menu_item_id": "65f0c7...",
      "name": "Chicken Bowl",
      "quantity": 2,
      "unit_price": 12.0,
      "line_total": 24.0,
      "notes": null
    }
  ],
  "subtotal": 24.0,
  "tax": 2.4,
  "discount": 1.0,
  "total": 25.4,
  "payment_status": "pending",
  "order_status": "pending",
  "created_at": "2026-03-12T00:10:00+00:00",
  "updated_at": "2026-03-12T00:10:00+00:00"
}
```


## AI Chat Improvements & Fixes
- **Chat History:** Removed the hardcoded 40-message display limit, ensuring the full conversation history is loaded.
- **Translation Pagination:** Limited translation hydration to only the latest 40 messages to prevent Vercel Serverless Function timeouts on full-history requests.
- **Voice Transcription:**
  - Removed auto-translation of voice transcripts to preserve exact user phrasing.
  - Passed the user's selected app language explicitly to the OpenAI Whisper API to prevent cross-language misinterpretations.
- **Error Handling:** Added explicit error messages for missing API keys or OpenAI API failures instead of returning a generic fallback financial summary.
- **Infrastructure:** Validated that Vercel auto-detect works correctly for the FastAPI backend and removed explicit ercel.json to prevent deployment conflicts.


# auth-profile-service

Python implementation of the combined **Auth + Profile** service according to C4/ER diagrams and project NFRs, built with **Clean Architecture** (4 layers), **Event-Driven design** (Kafka + Transactional Outbox), **CQRS** in Profile, and **RBAC** with **JWT**.

## Structure (Clean Architecture)

```
app/
├── domain/                 # Business core - no external dependencies
│   ├── auth/                #   User Aggregate, RolePolicy, RoleRequest, Events, Exceptions
│   └── profile/              #   Profile Aggregate (read-model), Value Objects, Events
│
├── application/             # Use-Case coordination + Ports
│   ├── ports/                #   Abstract Interfaces (DIP) - UserRepositoryPort, JwtProviderPort, ...
│   ├── dto/                  #   Pydantic input/output REST DTOs
│   └── use_cases/
│       ├── auth/              #   Register, Login, Refresh, Logout, ApproveRegistration,
│       │                       #   GrantRole, RequestRole, DecideRoleRequest, BanUser
│       └── profile/            #   GetProfile, UpdatePresence, HideGame,
│                                #   TopPostsProjector, InventoryProjector, LibraryProjector,
│                                #   UserSyncProjector  (CQRS read-model projectors)
│
├── infrastructure/           # Technical adapters (implement ports)
│   ├── db/                    #   SQLAlchemy async models + repositories + Outbox table
│   ├── security/               #   JWT (PyJWT) + BCrypt password hasher
│   ├── messaging/               #   Kafka producer, OutboxDispatcher, Consumers (aiokafka)
│   ├── cache/                    #   Redis presence store + token blacklist
│   └── observability/             #   Structured JSON logs, OpenTelemetry, Prometheus
│
├── presentation/
│   └── rest/                 #   FastAPI Controllers + WebSocket presence endpoint
│
├── core/                     # Cross-cutting: RBAC deps, correlation-id middleware, DI wiring
├── config.py                 # pydantic-settings (.env)
└── main.py                   # composition root / FastAPI app + lifespan
```

Each dependency arrow only points from **outside to inside** (`Presentation → Application → Domain, and Infrastructure → Application` through ports). Domain has no dependencies on SQLAlchemy/Kafka/Redis (DIP).

## Implemented Features

### Auth
- Registration (`POST /auth/register`) → BASE USER created
- Login with JWT access+refresh (`POST /auth/login`)
- Refresh token (`POST /auth/refresh`) and Logout with revocation in Redis (`POST /auth/logout`)
- Account state machine: `PENDING → ACTIVE/REJECTED`, `ACTIVE ↔ BANNED`
- 4 roles with exactly one role invariant (`role_policy.py`)
- Role request by user + approval/rejection by Support/Admin (`POST /roles/request`, `POST /roles/{id}/decide`)
- ADMIN can directly change any user's role (`POST /admin/users/{id}/grant-role`)
- Ban/Unban by Support/Admin
- Initial Super-Admin created with `seed_super_admin()` at startup (idempotent)
- `AbuseEventConsumer`: consumes `GiftCardAbuseDetected` → only **flags** for Support review (no automatic ban)


### Profile (CQRS Read-Model)
- `GET /profile/{id}`: name, avatar, non-hidden games, in-game items, top 5 posts, real-time online status
- `POST /profile/library/hide` and `/unhide`
- WebSocket `/ws/presence?token=...`: heartbeat → Redis `SET EX` (TTL) → automatic online/offline
- CQRS projectors consuming events from other services: `LibraryProjector` (OwnershipGranted),
`InventoryProjector` (ItemGranted/TradeMatched), `TopPostsProjector` (PostReacted), `UserSyncProjector`
(UserRegistered from Auth itself)

### NFRs Implemented in This Service

| NFR | Implementation |
|---|---|
| **Security** | JWT (short-lived access + long-lived refresh), RBAC (`require_roles`), BCrypt, Rate-limit on login/register (`slowapi`) |
| **Reliability** | **Transactional Outbox** (writing events in the same DB transaction) + `OutboxDispatcher` with retry; consumers are idempotent-friendly (manual commit after successful processing) |
| **Scalability** |Stateless service (presence/session in Redis, not in process memory) → supports multiple replicas |
| **Availability** | Each consumer error is isolated separately (limited retry + logging instead of crashing the entire service) |
| **Maintainability** | Clean Architecture 4 layers, structured JSON logging with `correlation_id` |
| **Observability** | `/metrics` (Prometheus RED metrics), OpenTelemetry (optional, with `OTEL_EXPORTER_OTLP_ENDPOINT`)، correlation-id middleware |
| **Compatibility** | Ports & Adapters architecture instead of direct SDK dependencies in Domain/Application |

Note: As per the requirements, Auth and Profile are placed in one shared service/deployment, but internally they remain completely separated (separate auth/ and profile/ folders in each layer) and communicate only through Events (user-events) - exactly like two independent microservices.

## Running with Docker

```bash
cp .env.example .env
docker compose up --build
```

The service starts at `http://localhost:8000`. OpenAPI documentation: `http://localhost:8000/docs`.

After the first run, a Super-Admin is created with the email/password from `.env` (`SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD`)

## Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
(Requires Postgres/Redis/Kafka available according to `DATABASE_URL` / `REDIS_URL` / `KAFKA_BOOTSTRAP_SERVERS`)

## Tests

Unit tests on the Domain layer (no DB/Kafka/Redis required - demonstrating Clean Architecture testability):

```bash
pytest tests/ -v
```
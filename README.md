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
- Registration (`POST /v1/auth/register`) → a `BASIC_USER` in state `ACTIVE`. A basic user does
not wait for Support: they sign in as soon as the account exists, and only *role upgrades* go
through an administrator. `PENDING` remains a state so accounts already in it can still be
decided, but registration no longer produces one. An account that cannot sign in gets a **403
naming the reason** rather than "invalid email or password": that branch is only reachable with
the correct password, so it leaks nothing and saves somebody waiting on Support from believing
they mistyped it.
- Login with JWT access+refresh (`POST /auth/login`)
- Refresh token (`POST /auth/refresh`) and Logout with revocation in Redis (`POST /auth/logout`)
- Account state machine: `PENDING → ACTIVE/REJECTED`, `ACTIVE ↔ BANNED`
- 4 roles with exactly one role invariant (`role_policy.py`)
- Role request by user + approval/rejection by Support/Admin (`POST /roles/request`, `POST /roles/{id}/decide`)
- ADMIN can directly change any user's role (`POST /admin/users/{id}/grant-role`)
- Ban/Unban by Support/Admin
- Initial Super-Admin created with `seed_super_admin()` at startup (idempotent)
- `AbuseEventConsumer`: consumes `arcadia.wallet.v1.GiftCardAbuseDetected` → only **flags** for
Support review (no automatic ban), which is what requirement 1.5 asks for — the ban is at Support's
discretion, so making it automatic would be the platform deciding something a human was asked to


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

## Use cases

### Identity

| # | Use case | Actor | Notes |
|---|---|---|---|
| 1 | Register | Anyone | Lands `ACTIVE` as a `BASIC_USER` |
| 2 | Sign in | Any account | Returns an access + refresh pair |
| 3 | Refresh a session | Any account | |
| 4 | Sign out | Any account | The refresh token is revoked in Redis |
| 5 | Request a role | Basic user | Enters the pending-requests queue |
| 6 | Decide a role request | Support / Admin | Approve or reject |
| 7 | Grant a role directly | Admin | Bypasses the request flow |
| 8 | Ban / unban an account | Support / Admin | |
| 9 | Decide a pending registration | Support / Admin | For accounts still in `PENDING` |
| 10 | List the user directory | Support / Admin | Name, email, role, state |
| 11 | List account ids by role | Services | Feeds platform-wide announcements |
| 12 | Look up a recipient | Any account | Resolves an email or exact display name to an id, for gifting |
| 13 | Suggest recipients | Any account | Type-ahead for the same |

### Profile

| # | Use case | Actor | Notes |
|---|---|---|---|
| 14 | View a profile | Anyone signed in | Name, avatar, games, items, top 5 posts, live online status |
| 15 | Hide a game from a profile | Owner | Visitors stop seeing it; the owner still does, marked hidden |
| 16 | Unhide a game | Owner | |
| 17 | Set an avatar | Owner | |
| 18 | Broadcast presence | Any account | WebSocket heartbeat → Redis TTL → automatic offline |

The hide/unhide pair has one subtlety worth stating: a hidden game is filtered out for
*visitors* but still returned to the **owner**, marked `hidden`. Returning the filtered list
to everybody made hiding permanent — the game vanished from the only screen that could bring
it back.

### Recipient lookup

Deliberately not a search. Exact email, or exact display name when only one account has it;
two matches is reported as ambiguous rather than resolved to the first, because picking one
sends a stranger a game. It answers "is this specific person here" for somebody about to send
them something, without becoming a way to enumerate the platform.

## How it talks to the rest of the platform

```mermaid
graph LR
    gw["api-gateway"] -->|"REST /auth/*<br/>+ WS /auth/ws/presence"| a["auth-profile-service"]
    order["order-service"] -->|"REST: does this<br/>recipient exist?"| a
    notif["notification-service"] -->|"REST: who is staff?"| a
    fest["festival-service"] -->|"REST: platform audience"| a

    a -->|"user-events:<br/>UserRegistered, RoleGranted,<br/>UserBanned"| topic(("user-events"))
    topic --> wallet["wallet-service"]
    topic --> mk["marketplace-service"]
    topic --> rev["review-service"]
    topic --> comm["community-service"]
    topic --> notif

    cat["catalog-service"] -->|"game-events:<br/>OwnershipGranted"| a
    mk -->|"trade-events:<br/>ItemGranted, TradeMatched"| a
    comm -->|"community-events:<br/>PostReacted"| a
    wallet -->|"wallet-events:<br/>GiftCardAbuseDetected"| a

    classDef s fill:#2d7dd2,stroke:#1a5a9e,color:#fff
    classDef t fill:#f5a623,stroke:#c4841c,color:#000
    class gw,a,order,notif,fest,wallet,mk,rev,comm,cat s
    class topic t
```

| Direction | Peer | Why |
|---|---|---|
| Called by | order-service | Verifies a gift recipient exists before anything is charged |
| Called by | notification-service | The SUPPORT and ADMIN ids for staff-directed notifications |
| Called by | festival-service | The audience for a platform-wide announcement |
| Publishes | `user-events` | Five services need to know who exists and what they may do |
| Consumes | `game-events` | `LibraryProjector` — games on a profile |
| Consumes | `trade-events` | `InventoryProjector` — items on a profile |
| Consumes | `community-events` | `TopPostsProjector` — the top 5 shelf |
| Consumes | `wallet-events` | Flags gift-card abuse for Support review — it never bans automatically, because requirement 1.5 asks a human to decide |

The four projectors are the CQRS read side: a profile is assembled from events other
services published, so rendering one costs a single local read rather than four
cross-service calls.

## Infrastructure

| Concern | Choice |
|---|---|
| Language | Python 3.12, FastAPI |
| Storage | PostgreSQL — `arcadia_auth`, SQLAlchemy 2 async + Alembic |
| Messaging | Kafka via aiokafka, transactional outbox |
| Cache | Redis — refresh-token revocation, presence TTL, rate limits |
| Passwords | bcrypt via passlib, hashed **off the event loop** |
| Port | 8085, plus the presence WebSocket |
| Deployment | 1 replica, HPA to 4 at 70% CPU |

Two resourcing notes specific to this service, both learned the hard way:

**It runs with a full CPU core**, not the 150m the other services use. bcrypt is
deliberately expensive; under a fifth of a core a single sign-in took longer than the
liveness probe's one-second timeout, three failures killed the pod, and a handful of
sign-ins was enough to take authentication down. Its probes also get five seconds.

**Hashing runs in a thread.** It is synchronous, CPU-bound work, and running it directly in
an async handler stops the process answering anything else — including `/livez` — for the
duration.

## Running

This service is deployed by the infra repository along with the rest of the platform. It had its
own `docker-compose.yml` standing up a second Postgres, Redis and Kafka; that is removed, because
two compose files describing the same service is exactly the ambiguity `infra/README.md` says the
platform avoids — and the two disagreed about the database name, the port and the JWT secret.

```bash
cd ../infra && make up && make wait
```

REST on `http://localhost:8085`, OpenAPI at `/docs`, everything under `/v1`.

A Super-Admin is seeded once on first boot from `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD`.
There is nobody to approve the first administrator, so that account is created ACTIVE — every
other account is ACTIVE too. A BASIC_USER can sign in as soon as they register; role upgrades
still wait for Support.

## Local development

```bash
make install
make test        # no database, broker or cache needed
make run         # against the infra stack, on 8085
```

## Integration with the platform

The things that had to match, because five other services already existed:

| | |
|---|---|
| **Token claims** | `typ` (not `type`), plus `iss` and `aud`. Every service verifies all three; without the issuer and audience all five answered 401, and `type` meant `typ` arrived empty — which our verifiers read as "an access token", so this service's seven-day refresh tokens worked as credentials everywhere. Both halves are fixed: the claims here, and the verifiers made strict. |
| **Event envelope** | `event_id`, `event_type`, `schema_version`, `occurred_at`, `producer`, `aggregate_type`, `aggregate_id`, and the domain fields nested under `payload`. Events were published flat, so the Go consumers rejected them as malformed and the Python ones found no payload. |
| **Event names** | `arcadia.auth.v1.UserRegistered`, not `UserRegistered`. The wallet has routed on that exact string since before this service existed. |
| **Topics** | One per *producing service* — `user-events`, `wallet-events`, `game-events` — not one per event. `ownership-events` and `gift-card-abuse-events` did not exist, so four of the five consumers were subscribed to nothing. Because a topic carries many event types, every handler routes on `event_type`. |
| **Paths** | `/v1/...`, like everything else on the platform. |
| **Health** | `/livez` and `/readyz` separately. Postgres is critical; Redis is not — losing it makes presence stale and a logged-out token valid until it expires, neither of which is worth refusing every login over. |

`infra/test/e2e/test_00_identity.py` is what proves it: a registration provisions a wallet in
another service with no HTTP call, and a purchase made with a token this service issued shows up in
the profile library via the catalog's ownership event.

## Tests

Unit tests on the Domain layer (no DB/Kafka/Redis required - demonstrating Clean Architecture testability):

```bash
pytest tests/ -v
```
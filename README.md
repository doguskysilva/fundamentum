# Fundamentum

Fundamentum is a shared Python package that provides infrastructure primitives for a microservices ecosystem.

It exists to centralize cross-cutting concerns such as observability and internal service communication, while explicitly avoiding domain coupling.

The goal is consistency without overengineering.
---
## Purpose

Fundamentum is designed to be used by multiple Python microservices (FastAPI-based) to avoid code duplication while preserving service autonomy.

It provides:

- Structured logging
- Request correlation
- Minimal distributed tracing (via headers)
- A generic internal HTTP client
- Explicit service integration contracts
- It does not contain business logic or domain models.


## What Fundamentum Provides
### Observability

- request_id propagation using contextvars
- FastAPI middleware for request tracing
- JSON logging to stdout
- Automatic injection of:
 - service name
 - environment
 - version
 - request_id

### Internal HTTP Communication

- ServiceEndpoint contract definition
- Generic ServiceClient
- Automatic propagation of X-Request-ID
- Environment-based service resolution via .env
---
## What Fundamentum Does NOT Provide

- No domain models
- No wire models specific to any service
- No service registry with concrete endpoints
- No business logic
- No orchestration logic
- No service discovery or mesh abstractions

Each microservice remains responsible for:

- Its own wire models
- Its own endpoint registry
- Its own configuration
- Its own domain logic

## Installation

Used as a Git dependency:
```toml
fundamentum @ git+https://github.com/doguskysilva/fundamentum.git@v0.1.0
```
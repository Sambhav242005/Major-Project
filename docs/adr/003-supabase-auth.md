# ADR-0003: Supabase Auth for Authentication

## Status
Accepted

## Context
The project needs user authentication (email/password + Google OAuth) and authorization (project-level roles). The original proposal did not specify an auth approach.

## Decision
Use Supabase Auth for authentication, with JWT validation on the FastAPI backend.

## Consequences

### Positive
- Pre-built email/password and Google OAuth flows
- Session management handled by Supabase
- Row-level security policies in Postgres tie auth to data access
- No custom auth code to maintain

### Negative
- Dependency on Supabase service for auth
- JWT validation requires fetching JWKS keys from Supabase
- Service-role key must be kept secret server-side

### Risks
- Acceptable for semester project; Supabase has free tier sufficient for demo

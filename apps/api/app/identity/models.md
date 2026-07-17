# Identity Data Model Specification

## User

Core identity record.

Fields:

- id
- email
- username
- password_hash
- status
- created_at
- updated_at
- last_login

## Organization

Enterprise tenant boundary.

Fields:

- id
- name
- slug
- subscription_level
- created_at

## Membership

Links users to organizations and roles.

## Audit Event

Tracks security and administrative activity.

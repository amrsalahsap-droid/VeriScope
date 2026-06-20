# Workspace Governance Migration & Recovery Guide

## Migration Summary
The governance system has transitioned from organization-scoping to workspace-scoping to match VeriScope's core data model. This migration consolidates data models (such as `Workspace` and `Repository`) and updates related audit events and default policies.

## Alembic Migration Expectations
Deployments must execute migrations using Alembic:
`alembic upgrade head`
> [!CAUTION]
> **Normal deployment must use Alembic**
> All standard database schema updates, indexes, and constraints must be managed via Alembic. Manual SQL commands are strictly reserved for emergency recovery under supervision.

## Multiple Head Recovery Guidance
If a git merge introduces multiple Alembic branch heads:
1. Identify the heads using:
   `alembic heads`
2. Create a merge revision using:
   `alembic merge -m "Merge governance heads" <head_1> <head_2>`
3. Apply the upgrade.

## Enum Conflict Guidance
SQLite and Postgres handle enum updates differently:
* **Postgres**: Requires explicit `ALTER TYPE` or table recreation.
* **SQLite**: Does not enforce raw enum constraints in the same way, but schema definition must match. Ensure migration scripts use SQLAlchemy `Enum` definition matching `GovernanceRole` or `ScopeType`.

## Workspace ID Backfill Guidance
For legacy tables lacking `workspace_id`:
1. Retrieve the parent repository's `workspace_id`.
2. Backfill the child records (exceptions, role assignments) with the corresponding `workspace_id`.
3. Apply `NOT NULL` constraints once backfill completes.

## Audit Column Migration
Legacy audit tables (`organization_governance_audit_events`) are migrated to `workspace_governance_audit_events`.
The script handles:
1. Copying existing audit records.
2. Renaming the table and drop legacy FK constraints.
3. Adding the new foreign key to the `Workspace` table.

## Preset Name Migration
When moving policies to preset configurations, migration scripts map custom settings to predefined presets (`STANDARD`, `STRICT`, `REGULATED`) where field values align, setting remainder to `CUSTOM`.

## Organization Compatibility Route Behavior
To support legacy integrations and API calls:
* Compatibility routes are registered matching `/organizations/{workspace_id}/...`.
* **Important**: These compatibility routes do not query any `Organization` model; they map the `workspace_id` parameter directly to query the `Workspace` model.

## Safe Rollback Notes
If a migration fails during deployment:
1. Determine the last successful version:
   `alembic current`
2. Roll back to that version:
   `alembic downgrade <revision_id>`
3. Inspect database backups before re-running.

## Manual SQL Emergency Notes
If Alembic fails completely due to locking or constraint issues in production:
1. Backup the database.
2. Terminate active application connections.
3. Manually apply missing schema updates (e.g. column additions or indexes) using raw SQL client.
4. Update the `alembic_version` table manually to match the corresponding revision hash:
   `UPDATE alembic_version SET version_num = '<revision_hash>';`

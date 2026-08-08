# Migration Runbook

## Overview
This runbook covers Alembic database migration operations for production deployment, including upgrades, downgrades, backup procedures, and recovery.

## Prerequisites

- Database access (PostgreSQL)
- Alembic installed and configured
- Database backup procedure established
- Migration scripts reviewed and tested

## Migration Commands

### Check Current Migration Status
```bash
.venv\Scripts\python -m alembic current
```

Expected output: Current revision should match head

### Check Latest Migration
```bash
.venv\Scripts\python -m alembic heads
```

Expected output: Single head revision

### Upgrade to Latest Migration
```bash
.venv\Scripts\python -m alembic upgrade head
```

This applies all pending migrations to bring the database to the latest schema.

### Downgrade to Specific Revision
```bash
.venv\Scripts\python -m alembic downgrade <revision_id>
```

Example:
```bash
.venv\Scripts\python -m alembic downgrade cda47bebedda
```

### Downgrade by One Step
```bash
.venv\Scripts\python -m alembic downgrade -1
```

### View Migration History
```bash
.venv\Scripts\python -m alembic history
```

## Pre-Migration Checklist

### Backup Procedure
Before any migration, create a database backup:

```bash
# Using pg_dump
pg_dump -h <host> -U <user> -d <database> -F c -f backup_$(date +%Y%m%d_%H%M%S).dump

# Example
pg_dump -h prod-db.example.com -U veriscope -d veriscope_prod -F c -f backup_20250621_100000.dump
```

### Verification Steps
- [ ] Database backup created successfully
- [ ] Backup file size verified (should be non-zero)
- [ ] Current migration status recorded
- [ ] Migration scripts reviewed
- [ ] Migration tested in staging environment
- [ ] Rollback plan documented

## Migration Execution

### Standard Upgrade Procedure
1. Create database backup
2. Verify current migration status
3. Apply migration: `alembic upgrade head`
4. Verify migration success
5. Run application smoke tests
6. Monitor for errors

### Standard Downgrade Procedure
1. Create database backup
2. Verify current migration status
3. Identify target revision
4. Apply downgrade: `alembic downgrade <revision>`
5. Verify downgrade success
6. Run application smoke tests
7. Monitor for errors

## Migration Verification

### Post-Migration Checks
- [ ] Alembic current shows expected revision
- [ ] Database schema matches migration
- [ ] Application starts successfully
- [ ] Smoke tests pass
- [ ] No database errors in logs
- [ ] Performance metrics normal

### Schema Validation
```bash
# Connect to database and verify schema
psql -h <host> -U <user> -d <database>

# List tables
\dt

# Describe specific table
\d <table_name>

# Check indexes
\di
```

## Rollback Procedures

### Migration Rollback
If a migration fails or causes issues:

1. **Immediate Rollback:**
   ```bash
   .venv\Scripts\python -m alembic downgrade -1
   ```

2. **Restore from Backup:**
   ```bash
   pg_restore -h <host> -U <user> -d <database> -c backup_20250621_100000.dump
   ```

3. **Verify Restoration:**
   - Check application functionality
   - Verify data integrity
   - Run smoke tests

### Rollback Decision Criteria
Rollback should be triggered if:
- Migration fails mid-execution
- Application errors after migration
- Data corruption detected
- Performance degradation > 50%
- Critical functionality broken
- Security issues introduced

## Troubleshooting

### Migration Conflicts
**Symptom:** Alembic reports revision conflict

**Resolution:**
1. Check alembic_version table: `SELECT * FROM alembic_version;`
2. Manually update if needed: `UPDATE alembic_version SET version_num='<target_revision>';`
3. Verify with: `alembic current`

### Migration Timeout
**Symptom:** Migration hangs or times out

**Resolution:**
1. Check database locks: `SELECT * FROM pg_locks;`
2. Kill blocking transactions if safe
3. Retry migration
4. Consider running during maintenance window

### Schema Mismatch
**Symptom:** Migration fails due to schema differences

**Resolution:**
1. Compare expected vs actual schema
2. Manually fix schema if safe
3. Create custom migration if needed
4. Test in staging first

## Emergency Procedures

### Database Restore
```bash
# Stop application
# Restore from backup
pg_restore -h <host> -U <user> -d <database> -c backup_20250621_100000.dump

# Verify restoration
psql -h <host> -U <user> -d <database> -c "SELECT COUNT(*) FROM users;"

# Restart application
```

### Partial Migration Recovery
If migration partially applied:
1. Identify failed migration step
2. Manually complete or rollback step
3. Update alembic_version if needed
4. Verify data integrity
5. Document incident

## Maintenance Windows

### Recommended Migration Times
- Low traffic periods (e.g., 2-4 AM local time)
- Weekend maintenance windows
- Coordinate with stakeholders
- Have rollback plan ready

### Migration Duration Estimates
- Simple schema changes: 1-5 minutes
- Data migrations: 5-30 minutes
- Complex schema changes: 30-60 minutes
- Large table operations: 1-2 hours

## Monitoring

### Migration Logs
Monitor logs for:
- Migration start/stop times
- SQL execution errors
- Constraint violations
- Performance warnings
- Lock wait times

### Post-Migration Monitoring
- Database connection pool utilization
- Query performance metrics
- Error rates
- Application response times
- Data consistency checks

## Contact Information

- Database Administrator: [DBA contact]
- On-Call Engineer: [On-call contact]
- Migration Lead: [Lead contact]

## Related Documentation
- [Rollback Plan](./rollback-plan.md)
- [Incident Response](./incident-response-runbook.md)
- [Production Readiness](./phase-10-production-readiness.md)

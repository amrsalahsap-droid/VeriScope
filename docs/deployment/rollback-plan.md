# Rollback Plan

## Overview
This rollback plan covers procedures for reverting application code, database schema, worker queues, and GitHub App configurations in case of deployment failures or critical issues.

## Rollback Triggers

### Automatic Rollback Triggers
Rollback should be triggered automatically if:
- Application error rate > 10% for 5 minutes
- Database connection failures > 5% for 5 minutes
- API response time > 5 seconds for 5 minutes
- Critical security vulnerability detected
- Data corruption detected

### Manual Rollback Triggers
Rollback should be triggered manually if:
- Critical functionality broken
- Data integrity issues
- Performance degradation > 50%
- User-reported critical issues
- Compliance violations
- Security incidents

## Rollback Procedures

### Code Rollback

#### Git-Based Rollback
```bash
# Identify previous stable commit
git log --oneline -10

# Rollback to previous commit
git checkout <previous_commit_hash>

# Deploy previous version
# (Use your deployment system: Kubernetes, ECS, etc.)
```

#### Container Image Rollback
```bash
# List previous images
kubectl get deployments -n veriscope

# Rollback to previous revision
kubectl rollout undo deployment/veriscope-api -n veriscope

# Verify rollback status
kubectl rollout status deployment/veriscope-api -n veriscope
```

#### Blue-Green Rollback
If using blue-green deployment:
1. Switch traffic back to blue environment
2. Verify blue environment is stable
3. Deprovision green environment
4. Monitor for issues

### Database Rollback

#### Alembic Downgrade
```bash
# Check current migration
.venv\Scripts\python -m alembic current

# Downgrade to previous revision
.venv\Scripts\python -m alembic downgrade <previous_revision>

# Verify downgrade
.venv\Scripts\python -m alembic current
```

#### Database Restore
```bash
# Stop application
# Restore from backup
pg_restore -h <host> -U <user> -d <database> -c backup_20250621_100000.dump

# Verify restoration
psql -h <host> -U <user> -d <database> -c "SELECT COUNT(*) FROM users;"

# Restart application
```

#### Partial Migration Rollback
If migration partially applied:
1. Identify failed migration step
2. Manually complete or rollback step
3. Update alembic_version if needed
4. Verify data integrity
5. Document incident

### Worker Queue Rollback

#### Worker Rollback
```bash
# Stop current workers
sudo systemctl stop veriscope-worker

# Deploy previous worker code
git checkout <previous_commit_hash>

# Restart workers
sudo systemctl start veriscope-worker

# Verify worker status
sudo systemctl status veriscope-worker
```

#### Queue Cleanup
```bash
# Check queue status
rq queue veriscope_sync --url $REDIS_URL

# Empty queue (use with caution)
rq empty veriscope_sync --url $REDIS_URL

# Purge failed jobs
rq failed --url $REDIS_URL --purge
```

#### Redis Rollback
```bash
# Stop workers
sudo systemctl stop veriscope-worker

# Restore Redis from backup
redis-cli --rdb /backup/redis/dump_20250621.rdb

# Restart Redis
sudo systemctl restart redis-server

# Restart workers
sudo systemctl start veriscope-worker
```

### GitHub App Rollback

#### Webhook URL Rollback
If webhook URL needs to be changed:
1. Update webhook URL in GitHub App settings
2. Update `GITHUB_WEBHOOK_SECRET` if needed
3. Restart application
4. Test webhook delivery

#### App Permissions Rollback
If permissions need to be reduced:
1. Go to GitHub App settings
2. Reduce permissions to previous state
3. Verify functionality still works
4. Monitor for permission errors

#### Key Rollback
If private key needs to be reverted:
1. Restore previous private key from backup
2. Update `GITHUB_APP_PRIVATE_KEY` environment variable
3. Restart application
4. Verify API authentication works

## Rollback Verification

### Application Verification
- [ ] Application starts successfully
- [ ] Health check returns healthy
- [ ] Database connection established
- [ ] Redis connection established
- [ ] GitHub App authentication works
- [ ] API endpoints respond correctly
- [ ] Worker processes jobs
- [ ] Webhook delivery works

### Data Verification
- [ ] Database schema matches expected state
- [ ] Data integrity checks pass
- [ ] No data corruption detected
- [ ] Audit logs intact
- [ ] Evidence preserved

### Functional Verification
- [ ] Critical user workflows work
- [ ] GitHub integration works
- [ ] Notifications deliver
- [ ] RBAC enforcement works
- [ ] Evidence packs generate

## Rollback Time Estimates

| Component | Rollback Time | Verification Time | Total Time |
|-----------|---------------|-------------------|------------|
| Code | 2-5 minutes | 5-10 minutes | 7-15 minutes |
| Database (downgrade) | 1-3 minutes | 5-10 minutes | 6-13 minutes |
| Database (restore) | 5-15 minutes | 10-20 minutes | 15-35 minutes |
| Worker Queue | 2-5 minutes | 5-10 minutes | 7-15 minutes |
| Redis | 2-5 minutes | 5-10 minutes | 7-15 minutes |
| GitHub App | 1-2 minutes | 5-10 minutes | 6-12 minutes |

**Total Estimated Rollback Time:** 15-35 minutes (depending on components)

## Rollback Communication

### Internal Communication
- Notify engineering team via Slack/Teams
- Notify on-call engineer
- Notify product team
- Document rollback in incident log

### External Communication
- Notify users if service is degraded
- Post status page update
- Send incident notification if SLA impacted

## Rollback Decision Process

### Rollback Authorization
Rollback requires authorization from:
- On-call engineer (automatic triggers)
- Engineering lead (manual triggers)
- Product manager (if user-facing)

### Rollback Steps
1. Assess situation and confirm rollback need
2. Notify stakeholders
3. Execute rollback procedures
4. Verify rollback success
5. Monitor for issues
6. Document incident
7. Schedule post-mortem

## Post-Rollback Actions

### Immediate Actions
- [ ] Monitor application health
- [ ] Monitor error rates
- [ ] Monitor performance metrics
- [ ] Verify user workflows
- [ ] Check data integrity

### Follow-up Actions
- [ ] Document rollback incident
- [ ] Schedule post-mortem meeting
- [ ] Identify root cause
- [ ] Implement fixes
- [ ] Update deployment procedures
- [ ] Update rollback plan if needed

## Rollback Testing

### Pre-Deployment Rollback Testing
Before each deployment, test rollback procedures:
1. Test code rollback in staging
2. Test database downgrade in staging
3. Test worker rollback in staging
4. Verify rollback success
5. Document any issues

### Rollback Drill Schedule
- Monthly rollback drills
- Quarterly full rollback simulation
- Annual disaster recovery test

## Rollback Failures

### If Rollback Fails
If rollback procedure fails:
1. Escalate to engineering lead
2. Notify stakeholders
3. Attempt alternative rollback method
4. Consider service degradation mode
5. Engage additional resources
6. Document failure for post-mortem

### Service Degradation Mode
If rollback is not possible:
1. Enable read-only mode if available
2. Disable non-critical features
3. Show maintenance page
4. Estimate recovery time
5. Communicate with users

## Rollback Documentation

### Incident Log
Document each rollback incident:
- Timestamp
- Trigger (automatic/manual)
- Components rolled back
- Rollback procedure used
- Rollback duration
- Issues encountered
- Verification results
- Follow-up actions

### Rollback Metrics
Track rollback metrics:
- Rollback frequency
- Rollback success rate
- Average rollback time
- Components most frequently rolled back
- Root causes of rollbacks

## Contact Information

- On-Call Engineer: [On-call contact]
- Engineering Lead: [Engineering lead contact]
- Product Manager: [Product manager contact]
- DevOps Engineer: [DevOps contact]

## Related Documentation
- [Migration Runbook](./migration-runbook.md)
- [Worker Queue Runbook](./worker-queue-runbook.md)
- [GitHub App Runbook](./github-app-production-runbook.md)
- [Incident Response](./incident-response-runbook.md)
- [Production Readiness](./phase-10-production-readiness.md)

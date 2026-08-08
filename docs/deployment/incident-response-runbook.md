# Incident Response Runbook

## Overview
This runbook covers incident response procedures for production outages, security incidents, data corruption, and other critical issues requiring immediate action.

## Incident Severity Levels

### SEV-0 (Critical)
- Service completely down
- Data loss or corruption
- Security breach
- SLA breach imminent
- Response time: 15 minutes

### SEV-1 (High)
- Major functionality broken
- Significant performance degradation
- Partial data integrity issue
- Security vulnerability exposed
- Response time: 30 minutes

### SEV-2 (Medium)
- Minor functionality broken
- Moderate performance degradation
- Non-critical data issue
- Response time: 1 hour

### SEV-3 (Low)
- Cosmetic issues
- Minor performance impact
- Documentation errors
- Response time: 4 hours

## Incident Response Process

### 1. Detection
- Automated monitoring alerts
- User reports
- Security scanning
- Data integrity checks

### 2. Triage
- Assess severity level
- Determine impact scope
- Identify affected components
- Estimate recovery time

### 3. Response
- Mobilize response team
- Implement mitigation
- Execute recovery procedures
- Communicate with stakeholders

### 4. Resolution
- Verify fix
- Monitor for recurrence
- Document incident
- Conduct post-mortem

## Common Incidents

### Application Outage

#### Symptoms
- Application not responding
- 500 errors on all endpoints
- Health check failing

#### Diagnosis
```bash
# Check application status
kubectl get pods -n veriscope

# Check application logs
kubectl logs -f deployment/veriscope-api -n veriscope

# Check health endpoint
curl https://veriscope.example.com/
```

#### Resolution
1. Restart application pods
2. If restart fails, rollback to previous version
3. Check database connectivity
4. Check Redis connectivity
5. Verify environment variables
6. Monitor for errors

#### Escalation
- If unresolved in 15 minutes: Escalate to engineering lead
- If unresolved in 30 minutes: Consider service degradation mode

### Database Outage

#### Symptoms
- Database connection errors
- Slow queries
- Connection pool exhaustion

#### Diagnosis
```bash
# Check database connectivity
psql -h <host> -U <user> -d <database> -c "SELECT 1;"

# Check database logs
# (PostgreSQL logs location varies by installation)

# Check connection count
psql -h <host> -U <user> -d <database> -c "SELECT count(*) FROM pg_stat_activity;"
```

#### Resolution
1. Check database server status
2. Restart database if needed
3. Check connection pool settings
4. Identify and kill long-running queries
5. Scale database resources if needed
6. Consider failover to replica

#### Escalation
- If unresolved in 15 minutes: Escalate to DBA
- If data corruption suspected: Immediately escalate to engineering lead

### Redis Outage

#### Symptoms
- Worker queue not processing
- Cache misses
- Connection errors

#### Diagnosis
```bash
# Check Redis status
redis-cli -h <host> -p <port> ping

# Check Redis logs
sudo journalctl -u redis-server

# Check Redis memory
redis-cli -h <host> -p <port> INFO memory
```

#### Resolution
1. Restart Redis server
2. Check Redis memory usage
3. Evict old keys if memory full
4. Restart workers after Redis recovery
5. Monitor queue processing

#### Escalation
- If unresolved in 10 minutes: Escalate to infrastructure team
- If data loss suspected: Immediately escalate to engineering lead

### GitHub Integration Failure

#### Symptoms
- Webhook delivery failures
- API authentication errors
- Rate limit exceeded

#### Diagnosis
```bash
# Check webhook delivery logs in GitHub
# (GitHub repository settings → Webhooks)

# Check application logs for GitHub API errors
kubectl logs -f deployment/veriscope-api -n veriscope | grep github

# Check rate limit usage
# (via GitHub API or application metrics)
```

#### Resolution
1. Verify GitHub App credentials
2. Check webhook secret
3. Check GitHub App permissions
4. Implement rate limit backoff
5. Monitor API usage
6. Contact GitHub support if needed

#### Escalation
- If unresolved in 30 minutes: Escalate to engineering lead
- If security issue suspected: Immediately escalate to security team

### Security Incident

#### Symptoms
- Unauthorized access detected
- Data breach suspected
- Malicious activity observed
- Vulnerability exploited

#### Immediate Actions
1. Isolate affected systems
2. Preserve evidence (logs, metrics)
3. Disable compromised accounts
4. Rotate all secrets
5. Notify security team
6. Notify stakeholders if data breach

#### Resolution
1. Conduct security investigation
2. Patch vulnerabilities
3. Restore from clean backup if needed
4. Implement additional security measures
5. Monitor for recurrence
6. Document incident for compliance

#### Escalation
- Immediately escalate to security team
- Notify legal team if data breach
- Notify executive team if critical

### Data Corruption

#### Symptoms
- Data integrity checks failing
- Inconsistent query results
- Application errors due to bad data

#### Diagnosis
```bash
# Run data integrity checks
# (Application-specific integrity checks)

# Check for orphaned records
psql -h <host> -U <user> -d <database> -c "SELECT count(*) FROM <table> WHERE <foreign_key> IS NULL;"

# Check for duplicate records
psql -h <host> -U <user> -d <database> -c "SELECT <id>, count(*) FROM <table> GROUP BY <id> HAVING count(*) > 1;"
```

#### Resolution
1. Identify scope of corruption
2. Stop application writes
3. Restore from backup if needed
4. Repair data if possible
5. Verify data integrity
6. Restart application

#### Escalation
- Immediately escalate to engineering lead
- Notify data steward if applicable

## Communication

### Internal Communication
- Notify on-call engineer
- Notify engineering team via Slack/Teams
- Notify engineering lead for SEV-0/SEV-1
- Notify product team for user-facing issues
- Document incident in incident log

### External Communication
- Update status page for SEV-0/SEV-1
- Send incident notification if SLA impacted
- Post incident summary after resolution
- Provide ETA for resolution when known

## Post-Incident Actions

### Immediate Actions
- [ ] Monitor for recurrence
- [ ] Verify fix is complete
- [ ] Update monitoring/alerting
- [ ] Document incident

### Follow-up Actions
- [ ] Schedule post-mortem meeting
- [ ] Identify root cause
- [ ] Implement fixes
- [ ] Update runbooks if needed
- [ ] Update monitoring if needed
- [ ] Share learnings with team

## Incident Metrics

Track incident metrics:
- Incident frequency by severity
- Mean time to detect (MTTD)
- Mean time to respond (MTTR)
- Mean time to resolve (MTTR)
- Components with most incidents
- Root cause categories

## Incident Drills

### Drill Schedule
- Quarterly incident response drills
- Annual full disaster recovery test
- Monthly security incident drills

### Drill Scenarios
- Application outage
- Database outage
- Redis outage
- GitHub integration failure
- Security breach
- Data corruption

## Contact Information

### On-Call
- On-Call Engineer: [On-call contact]
- Engineering Lead: [Engineering lead contact]
- Product Manager: [Product manager contact]

### Specialists
- Database Administrator: [DBA contact]
- Security Team: [Security contact]
- Infrastructure Team: [Infrastructure contact]
- GitHub Support: [GitHub support contact]

### Management
- Engineering Manager: [Engineering manager contact]
- CTO: [CTO contact]

## Related Documentation
- [Rollback Plan](./rollback-plan.md)
- [Migration Runbook](./migration-runbook.md)
- [Worker Queue Runbook](./worker-queue-runbook.md)
- [GitHub App Runbook](./github-app-production-runbook.md)
- [Production Readiness](./phase-10-production-readiness.md)

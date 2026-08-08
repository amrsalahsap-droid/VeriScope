# Worker Queue Runbook

## Overview
This runbook covers Redis/RQ background worker configuration, deployment, monitoring, and operational procedures for production.

## Architecture

### Components
- **Redis**: Message broker and job queue storage
- **RQ (Redis Queue)**: Job queue library for Python
- **RQ Worker**: Background job processor
- **Queue Name**: `veriscope_sync`

### Job Types
- PR comment delivery
- GitHub sync operations
- Governance notifications
- Evidence pack generation
- Compliance calculations

## Redis Configuration

### Production Redis Setup
```bash
# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server

# Enable Redis on boot
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping
# Expected response: PONG
```

### Redis Configuration File
Location: `/etc/redis/redis.conf`

Key settings for production:
```
# Bind to specific interface
bind 127.0.0.1

# Require password
requirepass <strong_password>

# Max memory policy
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
```

### Redis Connection String
Environment variable: `REDIS_URL`

Format: `redis://:<password>@<host>:<port>/<db>`

Example: `redis://:securepass@redis.prod.example.com:6379/0`

## RQ Worker Configuration

### Worker Installation
```bash
# Install RQ
pip install rq

# Install Redis Python client
pip install redis
```

### Worker Startup Command
```bash
.venv\Scripts\python -m rq worker veriscope_sync --url $REDIS_URL
```

### Production Worker Daemon
Create systemd service file: `/etc/systemd/system/veriscope-worker.service`

```ini
[Unit]
Description=Veriscope RQ Worker
After=network.target redis.service

[Service]
Type=simple
User=veriscope
Group=veriscope
WorkingDirectory=/opt/veriscope
Environment="PATH=/opt/veriscope/.venv/bin"
Environment="REDIS_URL=redis://:<password>@redis.prod.example.com:6379/0"
ExecStart=/opt/veriscope/.venv/bin/python -m rq worker veriscope_sync --url $REDIS_URL
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable veriscope-worker
sudo systemctl start veriscope-worker
sudo systemctl status veriscope-worker
```

### Worker Configuration Options

#### Basic Options
- `--url`: Redis connection URL
- `--name`: Custom worker name
- `--verbose`: Enable verbose logging

#### Performance Options
- `--burst`: Process jobs then exit (for scaling)
- `--worker-class`: Custom worker class
- `--max-jobs`: Maximum jobs per worker cycle

#### Monitoring Options
- `--log-file`: Log file path
- `--log-format`: Log format string

Example production command:
```bash
.venv\Scripts\python -m rq worker veriscope_sync \
  --url $REDIS_URL \
  --name worker-prod-1 \
  --verbose \
  --log-file /var/log/veriscope/worker.log
```

## Retry Policies

### Default Retry Configuration
Job retry behavior is configured in code:

```python
# Default retry settings
DEFAULT_RETRY_DELAY = 60  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_INTERVALS = [60, 120, 300]  # progressive backoff
```

### Custom Retry Policies
Set per-job retry options:

```python
from rq import Retry

# Retry with custom intervals
job = queue.enqueue(
    func,
    args=(arg1, arg2),
    retry=Retry(max=3, interval=[60, 120, 300])
)
```

### Retry Configuration by Job Type
- **PR Comment Delivery**: 3 retries, 60s intervals
- **GitHub Sync**: 5 retries, progressive backoff
- **Notifications**: 3 retries, 60s intervals
- **Evidence Packs**: 2 retries, 120s intervals

## Monitoring

### Worker Status
```bash
# Check active workers
rq info --url $REDIS_URL

# Check queue status
rq queue veriscope_sync --url $REDIS_URL

# Check failed jobs
rq failed --url $REDIS_URL
```

### Monitoring Metrics
- Queue length (pending jobs)
- Worker count (active workers)
- Failed job count
- Job execution time
- Worker CPU/memory usage

### Logging
Worker logs location: `/var/log/veriscope/worker.log`

Log levels:
- INFO: Normal operations
- WARNING: Retries, slow jobs
- ERROR: Failed jobs, exceptions
- CRITICAL: Worker crashes

### Alerting
Alert on:
- Worker process down
- Queue length > 1000
- Failed job rate > 5%
- Worker CPU > 80%
- Worker memory > 2GB

## Scaling

### Horizontal Scaling
Add more workers:

```bash
# Start additional workers
.venv\Scripts\python -m rq worker veriscope_sync --url $REDIS_URL --name worker-prod-2
.venv\Scripts\python -m rq worker veriscope_sync --url $REDIS_URL --name worker-prod-3
```

### Vertical Scaling
Increase worker resources:
- More CPU cores
- More memory
- Faster Redis connection

### Burst Mode
For temporary load spikes:
```bash
.venv\Scripts\python -m rq worker veriscope_sync --url $REDIS_URL --burst
```

Worker will exit after queue is empty.

## Troubleshooting

### Worker Not Processing Jobs
**Symptoms:** Jobs queued but not executing

**Diagnosis:**
```bash
# Check worker status
rq info --url $REDIS_URL

# Check worker logs
tail -f /var/log/veriscope/worker.log

# Check Redis connection
redis-cli -h <host> -p <port> ping
```

**Resolution:**
- Restart worker: `sudo systemctl restart veriscope-worker`
- Check Redis connectivity
- Verify worker has proper permissions
- Check for worker errors in logs

### High Queue Backlog
**Symptoms:** Queue length growing continuously

**Diagnosis:**
```bash
# Check queue length
rq queue veriscope_sync --url $REDIS_URL

# Check worker count
rq info --url $REDIS_URL
```

**Resolution:**
- Add more workers (horizontal scaling)
- Increase worker resources (vertical scaling)
- Optimize slow jobs
- Consider job prioritization

### Failed Jobs Accumulating
**Symptoms:** Failed job count increasing

**Diagnosis:**
```bash
# Check failed jobs
rq failed --url $REDIS_URL

# Inspect specific failed job
rq failed --url $REDIS_URL --job-id <job_id>
```

**Resolution:**
- Review job failure reasons
- Fix underlying issues
- Retry failed jobs: `rq requeue --url $REDIS_URL --job-id <job_id>`
- Purge old failed jobs: `rq failed --url $REDIS_URL --purge`

### Redis Connection Issues
**Symptoms:** Worker cannot connect to Redis

**Diagnosis:**
```bash
# Test Redis connection
redis-cli -h <host> -p <port> ping

# Check Redis logs
sudo journalctl -u redis-server
```

**Resolution:**
- Verify Redis is running
- Check Redis password
- Verify network connectivity
- Check firewall rules
- Verify REDIS_URL environment variable

## Maintenance

### Worker Restart
```bash
# Graceful restart
sudo systemctl restart veriscope-worker

# Force restart
sudo systemctl stop veriscope-worker
sudo systemctl start veriscope-worker
```

### Queue Maintenance
```bash
# Empty queue (use with caution)
rq empty veriscope_sync --url $REDIS_URL

# Purge old failed jobs
rq failed --url $REDIS_URL --purge

# Compact Redis
redis-cli --rdb - <dump_file>
```

### Redis Maintenance
```bash
# Save Redis data
redis-cli SAVE

# Backup Redis
redis-cli --rdb /backup/redis/dump_$(date +%Y%m%d).rdb

# Monitor Redis memory
redis-cli INFO memory
```

## Disaster Recovery

### Worker Recovery
If worker crashes:
1. Check logs for error
2. Fix underlying issue
3. Restart worker
4. Verify queue processing resumes

### Redis Recovery
If Redis fails:
1. Restart Redis: `sudo systemctl restart redis-server`
2. Verify data persistence
3. Restart workers
4. Monitor queue processing

### Queue Data Recovery
If Redis data is lost:
1. Restore from Redis backup
2. Requeue critical jobs manually
3. Monitor for data inconsistencies
4. Implement safeguards to prevent recurrence

## Security

### Redis Security
- Enable Redis password authentication
- Bind Redis to specific interface
- Use TLS for Redis connections (if remote)
- Restrict Redis network access
- Regular Redis security updates

### Worker Security
- Run worker as non-root user
- Restrict worker file system access
- Use environment variables for secrets
- Regular dependency updates
- Monitor for security vulnerabilities

## Contact Information

- Infrastructure Team: [Infrastructure contact]
- On-Call Engineer: [On-call contact]
- Redis Administrator: [Redis admin contact]

## Related Documentation
- [Production Readiness](./phase-10-production-readiness.md)
- [Rollback Plan](./rollback-plan.md)
- [Incident Response](./incident-response-runbook.md)

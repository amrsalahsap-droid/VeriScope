# Environment Configuration Checklist

## Overview
This checklist validates all required environment variables, CORS settings, and configuration limits for production deployment.

## Required Environment Variables

### Database Configuration
- [ ] `DATABASE_URL` - PostgreSQL connection string
  - Format: `postgresql://user:password@host:port/database`
  - Must use production database, not localhost/test
  - SSL mode should be `require` for production

### Redis Configuration
- [ ] `REDIS_URL` - Redis connection string
  - Format: `redis://host:port/db`
  - Must use production Redis instance
  - Password required for production

### Application Configuration
- [ ] `APP_ENV` - Set to `production`
  - Must NOT be `development` or `test`
  - Production mode disables inline fallbacks

### Security Configuration
- [ ] `STATE_SECRET_KEY` - JWT signing secret
  - Must be strong random string (32+ characters)
  - Must NOT be default or example value
  - Must be kept secret

- [ ] `GITHUB_WEBHOOK_SECRET` - GitHub webhook signature verification
  - Must match GitHub App webhook secret
  - Must NOT be default or example value

### GitHub App Configuration
- [ ] `GITHUB_APP_ID` - GitHub App ID
  - Must be production GitHub App ID
  - Must NOT be test/dev App ID

- [ ] `GITHUB_APP_PRIVATE_KEY` - GitHub App private key
  - Must be production private key
  - Must be PEM format
  - Must NOT be example key

### S3 Configuration (if using S3)
- [ ] `S3_BUCKET_NAME` - S3 bucket name
  - Must be production bucket
  - Must NOT be test bucket

- [ ] `S3_ACCESS_KEY` - S3 access key
  - Must be production credentials
  - Must have required permissions

- [ ] `S3_SECRET_KEY` - S3 secret key
  - Must be production credentials
  - Must be kept secret

- [ ] `S3_ENDPOINT_URL` - S3 endpoint (if using custom S3)
  - Must be production endpoint
  - Must NOT be localhost

### CORS Configuration
- [ ] `CORS_ORIGINS` - Allowed CORS origins
  - Must be production frontend domain(s)
  - Must NOT include `*` in production
  - Must NOT include localhost in production

### Rate Limiting Configuration
- [ ] `RATE_LIMIT_ENABLED` - Set to `true`
  - Must be enabled in production

- [ ] `RATE_LIMIT_PER_MINUTE` - Appropriate limit for production
  - Must be set based on expected traffic
  - Must NOT be unlimited

## Configuration Validation Rules

### Production Mode Checks
- [ ] `APP_ENV=production` is set
- [ ] No localhost URLs in database/Redis/S3 configuration
- [ ] No test/dev credentials
- [ ] No example/default secrets
- [ ] No wildcard CORS origins (`*`)

### Security Checks
- [ ] All secrets are strong (32+ characters)
- [ ] No secrets in code or version control
- [ ] SSL/TLS enabled for database connections
- [ ] Webhook secret matches GitHub App configuration

### Infrastructure Checks
- [ ] Database is production instance (not local)
- [ ] Redis is production instance (not local)
- [ ] S3 bucket is production (if using S3)
- [ ] GitHub App is production (not test/dev)

## Pre-Deployment Validation

### Automated Validation
Run the secret safety scan:
```bash
.venv\Scripts\python scripts/verify_secret_safety.py
```

Expected result: Zero `REAL_SECRET` findings

### Manual Validation
- [ ] Review all environment variables in production environment
- [ ] Verify no hardcoded credentials in configuration files
- [ ] Verify CORS origins match production frontend
- [ ] Verify rate limits are appropriate for expected traffic
- [ ] Verify all secrets are stored securely (e.g., AWS Secrets Manager, HashiCorp Vault)

## Post-Deployment Verification

- [ ] Application starts successfully
- [ ] Database connection established
- [ ] Redis connection established
- [ ] GitHub App authentication works
- [ ] Webhook signature validation works
- [ ] CORS headers correct on API responses
- [ ] Rate limiting active

## Rollback Criteria

Deployment should be rolled back if:
- Any required environment variable is missing
- Any secret is default/example value
- Any configuration points to localhost/test
- CORS origins include wildcard or localhost
- Rate limiting is disabled
- Application fails to start
- Database/Redis connection fails
- GitHub App authentication fails

## Configuration File Locations

- Environment variables: Production environment (AWS ECS, Kubernetes, etc.)
- Configuration validation: `scripts/verify_secret_safety.py`
- CORS configuration: `app/main.py` (CORS middleware)
- Rate limiting: `app/main.py` (rate limiter middleware)

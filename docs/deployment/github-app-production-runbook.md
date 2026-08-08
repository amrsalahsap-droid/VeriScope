# GitHub App Production Runbook

## Overview
This runbook covers GitHub App configuration, deployment, webhook management, and operational procedures for production.

## GitHub App Configuration

### Required Permissions
The GitHub App requires the following repository permissions:

#### Repository Permissions
- **Contents**: Read (for fetching files, commits)
- **Pull Requests**: Read/Write (for posting comments, statuses)
- **Checks**: Read/Write (for posting check runs)
- **Issues**: Read (for reading PR metadata)
- **Commit Status**: Read/Write (for posting commit statuses)
- **Metadata**: Read (for repository metadata)

#### Organization Permissions
- **Members**: Read (for organization member access)
- **Administration**: Read (for organization settings)

### Webhook Events
Required webhook events:
- **pull_request** (opened, synchronized, closed)
- **push** (for branch updates)
- **check_run** (for check run events)
- **installation** (for installation events)
- **installation_repositories** (for repository addition/removal)

### Environment Variables
- `GITHUB_APP_ID`: GitHub App ID
- `GITHUB_APP_PRIVATE_KEY`: GitHub App private key (PEM format)
- `GITHUB_WEBHOOK_SECRET`: Webhook signature verification secret

## GitHub App Setup

### Create GitHub App
1. Go to GitHub Settings → Developer settings → GitHub Apps
2. Click "New GitHub App"
3. Configure app settings:
   - **GitHub App name**: Veriscope Production
   - **Homepage URL**: https://veriscope.example.com
   - **Webhook URL**: https://veriscope.example.com/github/webhook
   - **Webhook secret**: Generate strong secret
4. Configure permissions (see above)
5. Configure webhook events (see above)
6. Install app on target organizations

### Generate Private Key
1. Go to GitHub App settings
2. Click "Generate a private key"
3. Download PEM file
4. Store securely (e.g., AWS Secrets Manager, HashiCorp Vault)
5. Set `GITHUB_APP_PRIVATE_KEY` environment variable

### Installation ID
After installing the app:
1. Note the Installation ID from the installation URL
2. Store in database for each organization
3. Used for API authentication

## Webhook Configuration

### Webhook URL
Production webhook URL: `https://veriscope.example.com/github/webhook`

### Webhook Secret
- Generate strong random string (32+ characters)
- Set as `GITHUB_WEBHOOK_SECRET` environment variable
- Configure in GitHub App webhook settings
- Used for signature verification

### Signature Verification
Webhook signatures are verified using HMAC-SHA256:

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)
```

Invalid signatures are rejected with 401 status.

## API Authentication

### Installation Token
GitHub App uses installation tokens for API authentication:

```python
from app.services.github_api_client import GitHubApiClient

client = GitHubApiClient()
token = client.get_installation_token(installation_id)
```

Token expiration: 1 hour (auto-refreshed)

### Rate Limiting
GitHub API rate limits:
- Installation tokens: 5,000 requests/hour
- Unauthenticated: 60 requests/hour

Monitor rate limit usage and implement backoff.

## Operational Procedures

### Monitor Webhook Delivery
Check webhook delivery logs in GitHub:
1. Go to repository settings → Webhooks
2. Click on webhook
3. View recent deliveries
4. Check for failures

### Monitor API Usage
Check GitHub API rate limits:
```python
from app.services.github_api_client import GitHubApiClient

client = GitHubApiClient()
rate_limit = client.get_rate_limit()
print(f"Remaining: {rate_limit['remaining']}")
print(f"Reset: {rate_limit['reset']}")
```

### Key Rotation
Rotate GitHub App private key periodically:

1. Generate new private key in GitHub App settings
2. Update `GITHUB_APP_PRIVATE_KEY` environment variable
3. Restart application
4. Verify API authentication works
5. Delete old key after verification

### Webhook Secret Rotation
Rotate webhook secret periodically:

1. Generate new webhook secret
2. Update `GITHUB_WEBHOOK_SECRET` environment variable
3. Update GitHub App webhook settings
4. Restart application
5. Verify webhook signature verification works
6. Test with sample webhook payload

## Troubleshooting

### Webhook Not Received
**Symptoms:** Webhooks not triggering application

**Diagnosis:**
- Check GitHub webhook delivery logs
- Verify webhook URL is accessible
- Check application logs for webhook errors
- Verify webhook secret matches

**Resolution:**
- Verify webhook URL is correct and accessible
- Check firewall/network rules
- Verify webhook secret matches
- Check application is running
- Review application logs for errors

### Signature Verification Failing
**Symptoms:** Webhook signature verification fails

**Diagnosis:**
- Check `GITHUB_WEBHOOK_SECRET` environment variable
- Verify secret matches GitHub App settings
- Check signature calculation logic

**Resolution:**
- Verify webhook secret is set correctly
- Update webhook secret if needed
- Restart application
- Test with sample webhook payload

### API Authentication Failing
**Symptoms:** GitHub API calls return 401/403

**Diagnosis:**
- Check `GITHUB_APP_PRIVATE_KEY` environment variable
- Verify private key is valid PEM format
- Check installation ID is correct
- Verify app permissions are sufficient

**Resolution:**
- Verify private key is set correctly
- Check private key format (PEM)
- Verify installation ID in database
- Check app permissions in GitHub
- Regenerate private key if needed

### Rate Limit Exceeded
**Symptoms:** GitHub API returns 403 rate limit exceeded

**Diagnosis:**
- Check rate limit usage
- Review API call patterns
- Identify high-frequency endpoints

**Resolution:**
- Implement request queuing
- Add caching for expensive calls
- Optimize API call patterns
- Consider GitHub App rate limit increase

## Security

### Private Key Security
- Store private key securely (secrets manager)
- Never commit private key to version control
- Rotate private key periodically
- Limit access to private key
- Monitor for unauthorized access

### Webhook Secret Security
- Store webhook secret securely
- Never commit webhook secret to version control
- Rotate webhook secret periodically
- Use strong random secret (32+ characters)
- Monitor for unauthorized webhook calls

### Permission Principle of Least Privilege
- Grant only required permissions
- Review permissions regularly
- Remove unused permissions
- Monitor permission usage
- Audit permission changes

## Monitoring

### Webhook Metrics
- Webhook delivery success rate
- Webhook delivery latency
- Signature verification failures
- Webhook processing time

### API Metrics
- API call success rate
- API call latency
- Rate limit usage
- Token refresh frequency

### Alerting
Alert on:
- Webhook delivery failure rate > 5%
- Signature verification failures
- API authentication failures
- Rate limit usage > 80%
- API error rate > 5%

## Maintenance

### Regular Tasks
- Monitor webhook delivery logs
- Review API rate limit usage
- Check for GitHub API deprecations
- Review app permissions
- Rotate private key (quarterly)
- Rotate webhook secret (quarterly)

### GitHub API Updates
Monitor GitHub API changelog for:
- New features
- Deprecations
- Breaking changes
- Rate limit changes
- Permission changes

## Disaster Recovery

### Webhook Recovery
If webhook delivery fails:
1. Check webhook URL accessibility
2. Verify webhook secret
3. Restart application
4. Test with sample webhook
5. Monitor delivery logs

### API Recovery
If API authentication fails:
1. Verify private key is set
2. Check installation ID
3. Verify app permissions
4. Regenerate private key if needed
5. Restart application

### App Recovery
If GitHub App is deleted:
1. Recreate GitHub App with same configuration
2. Generate new private key
3. Update environment variables
4. Reinstall app on organizations
5. Update installation IDs in database

## Contact Information

- GitHub Administrator: [GitHub admin contact]
- On-Call Engineer: [On-call contact]
- Security Team: [Security contact]

## Related Documentation
- [Production Readiness](./phase-10-production-readiness.md)
- [Rollback Plan](./rollback-plan.md)
- [Incident Response](./incident-response-runbook.md)

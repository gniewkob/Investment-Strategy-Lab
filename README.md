# Investment Strategy Lab

Research-only, reproducible market-data analysis and educational paper-trading experiments.

## Status
Early prototype. There are **no live brokerage integrations, trades or order-execution features**. Historical model performance does not demonstrate forecasting skill.

## Architecture
- Python: deterministic data validation and research experiments
- PostgreSQL (external): versioned source observations, model results and audit history
- GitHub Actions: tests and, once separately configured, scheduled research-only jobs
- ChatGPT plugin: interpret verified results and explain uncertainty

## Security
This repository is public. **Never commit** database connection strings, API tokens, wallet information, portfolio exports, passwords, account identifiers or production data. Store runtime credentials only as GitHub Actions repository secrets and use least-privilege database roles. Code reviews and external PR workflows must not receive secrets.

## Planned next steps
1. Publish the tested code on a review branch and run CI.
2. Validate time-of-publication controls against synthetic fixture data.
3. Review least-privilege credentials and schema migration.
4. Verify the first scheduled run before claiming autonomy.

Licensed and third-party market datasets should not be published in this repository.

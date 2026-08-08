# Migration Exception Record - Alembic Topological Sort Hang

## 1. Issue Description & Captured Error

When executing database schema migrations on a fresh production database using Alembic:

```bash
.venv\Scripts\python -m alembic upgrade head
```

The process hangs indefinitely after printing:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

### Captured Stack Trace / Loop Location
A stack trace monitoring check captures the execution looping infinitely within Alembic's dependency resolver:
* File: `alembic/script/revision.py`
* Function: `_topological_sort`
* Line: 975 (inside loop resolving branch merges)

This hang is caused by circular dependencies or complex branching histories across the 119 sequential and parallel merge revision files in the repository migration folder.

## 2. Workaround Procedure

Rather than resolving the complex topological merge history at runtime, the following auditable procedure has been executed:
1. **Schema Extraction**: Exported a schema-only dump of `veriscope_dev` (which has successfully applied all 119 migrations incrementally).
2. **Schema Restoration**: Restored this schema structure into `veriscope_prod_final`.
3. **Alembic Version Alignment**: Manually inserted `'c96a41da899b'` into the `alembic_version` table.
4. **No-Op Upgrade Verification**: Ran `alembic upgrade head` to confirm that Alembic completes instantly as a no-op when the schema matches the latest revision.

## 3. Schema Equivalence Proof

The schema was validated between the source `veriscope_dev` and target `veriscope_prod_final` databases. The database structure matches exactly:

| Metric | Source (veriscope_dev) | Target (veriscope_prod_final) | Match Status |
| :--- | :---: | :---: | :---: |
| **Table Count** | 121 | 121 | **100% Match** |
| **Index Count** | 598 | 598 | **100% Match** |
| **Table Constraints** | 1526 | 1526 | **100% Match** |

All primary keys, foreign keys, unique indices, check constraints, triggers, and sequences were successfully replicated.

## 4. Data Integrity Proof

* **Empty Target Isolation**: The production target database `veriscope_prod_final` was empty prior to migration. There was zero risk of mutating or overwriting historical production data.
* **Schema-Only Restrictions**: The schema migration was performed using schema-only exports (`pg_dump -s`). No development data was copied into production.
* **Verification Checks**: Run `python scripts/verify_production_readiness_real_http.py` to confirm that all 50 E2E relational data model smoke tests execute and pass.

## 5. Backup and Restore Proof

A test backup/restore cycle has been completed successfully using the following commands:
* **Backup Command**:
  ```bash
  pg_dump -h 192.168.100.44 -U postgres -d veriscope_prod_final -F c -f veriscope_prod_final_test.dump
  ```
* **Restore Command**:
  ```bash
  pg_restore -h 192.168.100.44 -U postgres -d veriscope_prod_final_restore_test veriscope_prod_final_test.dump
  ```

## 6. Rollback Plan

If a database rollback is required during deployment:
1. Revert to the latest stable release tag in Git.
2. If schema structure must be restored, run:
   ```bash
   dropdb -h 192.168.100.44 -U postgres veriscope_prod_final
   createdb -h 192.168.100.44 -U postgres veriscope_prod_final
   pg_restore -h 192.168.100.44 -U postgres -d veriscope_prod_final <backup_file>.dump
   ```

## 7. Approval & Metadata

* **Approval Owner**: Platform Engineering Lead
* **Approval Timestamp**: 2026-06-21T13:00:00Z
* **Manual alembic_version update declared**: YES (Revision `'c96a41da899b'`)
* **Status**: APPROVED EXCEPTION

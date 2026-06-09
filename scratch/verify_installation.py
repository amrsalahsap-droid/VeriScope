#!/usr/bin/env python
"""Verify database schema and existing installations."""
import sys
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')

from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Check workspace_id column exists
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'github_installations' AND column_name = 'workspace_id'"
    ))
    cols = result.fetchall()
    if cols:
        print('✓ workspace_id column exists')
    else:
        print('✗ workspace_id column MISSING - run fix_db_schema.py')
    
    # Check installations
    result = conn.execute(text(
        'SELECT id, workspace_id, github_installation_id, github_account_login, status '
        'FROM github_installations'
    ))
    rows = result.fetchall()
    print(f'\nInstallations in DB: {len(rows)}')
    for row in rows:
        print(f'  ID={row[0]}, workspace={row[1]}, installation_id={row[2]}, login={row[3]}, status={row[4]}')
    
    if rows:
        print(f'\n✓ Installation found: {rows[0][2]}')
    else:
        print('\n✗ No installations found - need to link installation_id=135363628')

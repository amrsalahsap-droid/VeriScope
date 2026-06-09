"""
Check what's in the semantic index for a repository.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.repository import Repository
from app.models.repository_semantic_entry import RepositorySemanticEntry

db_gen = get_db()
db = next(db_gen)

try:
    # Get a real repository
    repo = db.query(Repository).filter(
        Repository.full_name != "test/behavior-discovery-verification"
    ).first()
    
    if not repo:
        print("No real repository found")
        sys.exit(1)
    
    print(f"Repository: {repo.full_name}")
    print(f"ID: {repo.id}")
    
    # Check semantic entries
    entries = db.query(RepositorySemanticEntry).filter(
        RepositorySemanticEntry.repository_id == repo.id
    ).all()
    
    print(f"\nTotal Semantic Entries: {len(entries)}")
    
    # Group by entry type
    by_type = {}
    for entry in entries:
        entry_type = entry.entry_type
        if entry_type not in by_type:
            by_type[entry_type] = []
        by_type[entry_type].append(entry)
    
    print(f"\nBy Type:")
    for entry_type, type_entries in by_type.items():
        print(f"  {entry_type}: {len(type_entries)}")
        if type_entries:
            print(f"    Examples:")
            for e in type_entries[:5]:
                print(f"      - {e.path} (confidence: {e.confidence})")
    
finally:
    db.close()

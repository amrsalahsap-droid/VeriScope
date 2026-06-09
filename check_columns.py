from sqlalchemy import text
from app.db.session import SessionLocal

db = SessionLocal()

tables = ['test_cases']

model_cols = ['id','repository_id','suite_name','test_name','stable_identity','raw_test_name','normalized_test_name','normalized_identity_strategy','framework_name','framework_version','identity_normalization_version','canonical_identity_hash','previous_identity_hash','identity_lineage_root_hash','identity_version','identity_resolution_strategy','created_at']

for table in tables:
    result = db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_name = '{table}' ORDER BY ordinal_position"
    ))
    cols = [r[0] for r in result]
    print(f"\n{table}:\n  {cols}")
    if cols:
        missing = [c for c in model_cols if c not in cols]
        print(f"  MISSING from DB: {missing}")
    else:
        print("  TABLE DOES NOT EXIST")

db.close()

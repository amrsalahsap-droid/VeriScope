"""add AC test mapping semantic audit fields

Revision ID: ac_map_semantic_audit
Revises: merge_mapping_fk_fix
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ac_map_semantic_audit"
down_revision = "merge_mapping_fk_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mapping_candidates", sa.Column("requirement_package_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("mapping_candidates", sa.Column("primary_status", sa.String(length=50), nullable=True))
    op.add_column("mapping_candidates", sa.Column("coverage_type", sa.String(length=20), nullable=False, server_default="none"))
    op.add_column("mapping_candidates", sa.Column("execution_status", sa.String(length=20), nullable=False, server_default="unknown"))
    op.add_column("mapping_candidates", sa.Column("declared_ac_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("mapping_candidates", sa.Column("declared_ac_display_ref", sa.String(length=100), nullable=True))
    op.add_column("mapping_candidates", sa.Column("semantic_ac_display_ref", sa.String(length=100), nullable=True))
    op.add_column("mapping_candidates", sa.Column("semantic_ac_text_snapshot", sa.Text(), nullable=True))
    op.add_column("mapping_candidates", sa.Column("ai_decision_json", sa.JSON(), nullable=True))
    op.add_column("mapping_candidates", sa.Column("safety_gate_json", sa.JSON(), nullable=True))
    op.add_column("mapping_candidates", sa.Column("created_by", sa.String(length=20), nullable=False, server_default="system"))
    op.add_column("mapping_candidates", sa.Column("user_decision", sa.String(length=30), nullable=False, server_default="none"))
    op.add_column("mapping_candidates", sa.Column("user_decision_at", sa.DateTime(), nullable=True))
    op.add_column("mapping_candidates", sa.Column("user_decision_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("mapping_candidates", sa.Column("audit_comment", sa.Text(), nullable=True))
    op.add_column("mapping_candidates", sa.Column("partial_support_reason", sa.Text(), nullable=True))
    op.create_index("ix_mapping_candidates_primary_status", "mapping_candidates", ["primary_status"])
    op.create_index("ix_mapping_candidates_requirement_package_id", "mapping_candidates", ["requirement_package_id"])
    op.create_foreign_key("fk_mapping_candidates_requirement_package", "mapping_candidates", "requirement_packages", ["requirement_package_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_mapping_candidates_declared_ac", "mapping_candidates", "acceptance_criteria", ["declared_ac_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_mapping_candidates_user_decision_by", "mapping_candidates", "users", ["user_decision_by"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_mapping_candidates_user_decision_by", "mapping_candidates", type_="foreignkey")
    op.drop_constraint("fk_mapping_candidates_declared_ac", "mapping_candidates", type_="foreignkey")
    op.drop_constraint("fk_mapping_candidates_requirement_package", "mapping_candidates", type_="foreignkey")
    op.drop_index("ix_mapping_candidates_requirement_package_id", table_name="mapping_candidates")
    op.drop_index("ix_mapping_candidates_primary_status", table_name="mapping_candidates")
    for column in ("partial_support_reason", "audit_comment", "user_decision_by", "user_decision_at", "user_decision", "created_by", "safety_gate_json", "ai_decision_json", "semantic_ac_text_snapshot", "semantic_ac_display_ref", "declared_ac_display_ref", "declared_ac_id", "execution_status", "coverage_type", "primary_status", "requirement_package_id"):
        op.drop_column("mapping_candidates", column)

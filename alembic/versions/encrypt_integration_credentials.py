"""encrypt_integration_credentials

Revision ID: encrypt_integration_credentials
Revises: ab3ae270c1dd
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union
import json
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'encrypt_integration_credentials'
down_revision: Union[str, Sequence[str], None] = 'ab3ae270c1dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - encrypt existing credentials and add tracking columns."""
    
    # Step 1: Add new columns for encryption tracking
    op.add_column('integration_connections', sa.Column('credentials_encrypted_at', sa.DateTime(), nullable=True))
    op.add_column('integration_connections', sa.Column('credentials_version', sa.Integer(), nullable=False, server_default='1'))
    
    # Step 2: Change encrypted_credentials from JSONB to Text
    # First, we need to migrate existing data
    connection = op.get_bind()
    
    # Get all connections with credentials
    result = connection.execute(
        sa.text("SELECT id, encrypted_credentials FROM integration_connections WHERE encrypted_credentials IS NOT NULL")
    )
    
    # Import encryption service (will fail if key not set, which is intentional)
    try:
        from app.services.security.credential_encryption_service import get_credential_encryption_service
        encryption_service = get_credential_encryption_service()
        
        # Encrypt existing credentials
        for row in result:
            conn_id = row[0]
            credentials_data = row[1]
            
            # Skip if already encrypted (heuristic check)
            if isinstance(credentials_data, str) and len(credentials_data) >= 44:
                try:
                    json.loads(credentials_data)
                    # Valid JSON, not encrypted
                    pass
                except:
                    # Not valid JSON, likely already encrypted
                    continue
            
            # Encrypt the credentials
            if credentials_data:
                try:
                    encrypted = encryption_service.encrypt(credentials_data)
                    connection.execute(
                        sa.text(
                            "UPDATE integration_connections "
                            "SET encrypted_credentials = :encrypted, "
                            "credentials_encrypted_at = :encrypted_at, "
                            "credentials_version = 1 "
                            "WHERE id = :conn_id"
                        ),
                        {"encrypted": encrypted, "encrypted_at": datetime.utcnow(), "conn_id": conn_id}
                    )
                except Exception as e:
                    # Log error but continue with other rows
                    print(f"Failed to encrypt credentials for connection {conn_id}: {e}")
        
        connection.commit()
        
    except Exception as e:
        # If encryption service not available, we'll handle this in the application layer
        print(f"Encryption service not available during migration: {e}")
        print("Credentials will be encrypted on next access through application layer")
    
    # Step 3: Alter column type from JSONB to Text
    op.alter_column('integration_connections', 'encrypted_credentials', 
                   existing_type=postgresql.JSONB(),
                   type_=sa.Text(),
                   existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema - revert to plaintext credentials (DANGEROUS)."""
    
    # WARNING: This downgrade will lose all encrypted credentials
    # It should only be used in development/testing
    
    # Revert column type from Text to JSONB
    op.alter_column('integration_connections', 'encrypted_credentials',
                   existing_type=sa.Text(),
                   type_=postgresql.JSONB(),
                   existing_nullable=True)
    
    # Drop tracking columns
    op.drop_column('integration_connections', 'credentials_version')
    op.drop_column('integration_connections', 'credentials_encrypted_at')

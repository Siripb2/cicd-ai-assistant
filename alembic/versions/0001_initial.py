"""create pipeline_analyses table

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("request_id", sa.String(36), unique=True, index=True, nullable=False),
        sa.Column("org_id", sa.String(64), index=True, nullable=False, server_default="default"),
        sa.Column("pipeline_name", sa.String(255), index=True, nullable=False),
        sa.Column("repository", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("log_content", sa.Text(), nullable=False),
        sa.Column("ai_analysis_raw", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("affected_component", sa.String(255), nullable=True),
        sa.Column("fix_suggestion", sa.Text(), nullable=True),
        sa.Column("confidence_level", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ANALYZED", "FAILED", name="analysisstatus"),
            nullable=False,
            server_default="PENDING",
            index=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("pipeline_analyses")

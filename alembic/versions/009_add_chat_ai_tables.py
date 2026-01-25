"""Add chat AI analysis tables

Revision ID: 009_chat_ai_tables
Revises: 008_extend_mappings
Create Date: 2026-01-24

Adds:
- chat_messages: Persistent message history for AI context
- chat_ai_settings: Per-chat AI configuration
- detected_issues: Problem/issue tracking
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '009_chat_ai_tables'
down_revision = '008_extend_mappings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Chat Messages - persistent context storage
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),  # Telegram message ID
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('message_type', sa.String(50), default='text'),  # text, voice, photo, document
        sa.Column('reply_to_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),

        # AI analysis fields (populated by AI)
        sa.Column('sentiment_score', sa.Float(), nullable=True),  # -1.0 to 1.0
        sa.Column('is_question', sa.Boolean(), default=False),
        sa.Column('is_answered', sa.Boolean(), default=False),
        sa.Column('detected_intent', sa.String(50), nullable=True),  # task, problem, question, info

        # Indexes for fast queries
        sa.Index('idx_chat_messages_chat_created', 'chat_id', 'created_at'),
        sa.Index('idx_chat_messages_user', 'user_id'),
    )

    # 2. Chat AI Settings - per-chat configuration
    op.create_table(
        'chat_ai_settings',
        sa.Column('chat_id', sa.BigInteger(), primary_key=True),
        sa.Column('chat_title', sa.String(255), nullable=True),

        # Feature toggles
        sa.Column('problem_detection_enabled', sa.Boolean(), default=True),
        sa.Column('task_detection_enabled', sa.Boolean(), default=True),
        sa.Column('daily_summary_enabled', sa.Boolean(), default=False),
        sa.Column('auto_answer_questions', sa.Boolean(), default=False),

        # Configuration
        sa.Column('context_size', sa.Integer(), default=100),  # Max messages to keep in context
        sa.Column('daily_summary_time', sa.Time(), nullable=True),  # e.g., 18:00
        sa.Column('min_confidence_threshold', sa.Float(), default=0.7),  # For task detection
        sa.Column('problem_keywords', sa.Text(), nullable=True),  # JSON array of custom keywords

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # 3. Detected Issues - problem/task tracking
    op.create_table(
        'detected_issues',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=True),

        # Issue details
        sa.Column('issue_type', sa.String(50), nullable=False),  # problem, unanswered, urgent, task
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=True),

        # Status tracking
        sa.Column('status', sa.String(50), default='new'),  # new, notified, acknowledged, resolved, ignored
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.BigInteger(), nullable=True),

        # Plane integration
        sa.Column('plane_issue_id', sa.String(100), nullable=True),
        sa.Column('plane_project_id', sa.String(100), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.Index('idx_detected_issues_chat_status', 'chat_id', 'status'),
        sa.Index('idx_detected_issues_type', 'issue_type'),
    )


def downgrade() -> None:
    op.drop_table('detected_issues')
    op.drop_table('chat_ai_settings')
    op.drop_table('chat_messages')

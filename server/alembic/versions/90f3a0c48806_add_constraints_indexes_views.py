"""add constraints indexes views

Revision ID: 90f3a0c48806
Revises: a4cf3f83562f
Create Date: 2026-03-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90f3a0c48806'
down_revision: Union[str, None] = 'a4cf3f83562f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # 1. Add CHECK constraints to manual_corrections
    # ==========================================================================
    op.create_check_constraint(
        "chk_target_type",
        "manual_corrections",
        "target_type IN ('ocr', 'knowledge', 'plan', 'qa')",
    )
    op.create_check_constraint(
        "chk_correction_status",
        "manual_corrections",
        "status IN ('pending', 'resolved', 'rejected')",
    )

    # ==========================================================================
    # 2. Create indexes - High priority (performance critical)
    # ==========================================================================

    # error_book indexes
    op.create_index(
        "idx_error_book_student",
        "error_book",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "idx_error_book_subject",
        "error_book",
        ["subject_id"],
        unique=False,
    )
    op.create_index(
        "idx_error_book_recall",
        "error_book",
        ["is_recalled", "last_recall_at"],
        unique=False,
    )
    op.create_index(
        "idx_error_book_student_status",
        "error_book",
        ["student_id", "is_recalled"],
        unique=False,
    )

    # qa_messages index
    op.create_index(
        "idx_qa_messages_session",
        "qa_messages",
        ["session_id", "created_at"],
        unique=False,
    )

    # model_call_logs indexes
    op.create_index(
        "idx_model_logs_created",
        "model_call_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_model_logs_agent",
        "model_call_logs",
        ["agent_name", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_model_logs_student",
        "model_call_logs",
        ["student_id", "created_at"],
        unique=False,
    )

    # student_knowledge_status indexes
    op.create_index(
        "idx_student_knowledge_student",
        "student_knowledge_status",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "idx_student_knowledge_status",
        "student_knowledge_status",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_student_knowledge_compound",
        "student_knowledge_status",
        ["student_id", "status", "knowledge_point_id"],
        unique=False,
    )

    # weekly_reports index
    op.create_index(
        "idx_weekly_reports_student_week",
        "weekly_reports",
        ["student_id", sa.text("report_week DESC")],
        unique=False,
    )

    # exam_records index (with DESC, replacing old index if exists)
    op.execute("DROP INDEX IF EXISTS idx_exam_student_date")
    op.create_index(
        "idx_exam_records_student_date",
        "exam_records",
        ["student_id", sa.text("exam_date DESC")],
        unique=False,
    )

    # ==========================================================================
    # 3. Create indexes - Medium priority
    # ==========================================================================

    # qa_sessions index
    op.create_index(
        "idx_qa_sessions_student",
        "qa_sessions",
        ["student_id", "created_at"],
        unique=False,
    )

    # study_uploads index
    op.create_index(
        "idx_study_uploads_ocr_status",
        "study_uploads",
        ["ocr_status"],
        unique=False,
    )

    # manual_corrections index
    op.create_index(
        "idx_corrections_type",
        "manual_corrections",
        ["target_type", "created_at"],
        unique=False,
    )

    # knowledge_update_logs index
    op.create_index(
        "idx_knowledge_logs_student",
        "knowledge_update_logs",
        ["student_id", "created_at"],
        unique=False,
    )

    # subject_risk_states index
    op.create_index(
        "idx_risk_states_student",
        "subject_risk_states",
        ["student_id"],
        unique=False,
    )

    # daily_plans index (with DESC)
    op.create_index(
        "idx_daily_plans_student_date",
        "daily_plans",
        ["student_id", sa.text("plan_date DESC")],
        unique=False,
    )

    # ==========================================================================
    # 4. Create view v_high_risk_knowledge_points
    # ==========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW v_high_risk_knowledge_points AS
        SELECT
            sks.student_id,
            sks.knowledge_point_id,
            kt.name AS knowledge_point_name,
            s.name AS subject_name,
            s.id AS subject_id,
            sks.status,
            kt.importance_score,
            sks.last_updated_at
        FROM student_knowledge_status sks
        JOIN knowledge_tree kt ON sks.knowledge_point_id = kt.id
        JOIN subjects s ON kt.subject_id = s.id
        WHERE sks.status = '反复失误'
        ORDER BY kt.importance_score DESC, sks.last_updated_at DESC
    """)


def downgrade() -> None:
    # ==========================================================================
    # 1. Drop view
    # ==========================================================================
    op.execute("DROP VIEW IF EXISTS v_high_risk_knowledge_points")

    # ==========================================================================
    # 2. Drop indexes - Medium priority
    # ==========================================================================
    op.drop_index("idx_daily_plans_student_date", table_name="daily_plans")
    op.drop_index("idx_risk_states_student", table_name="subject_risk_states")
    op.drop_index("idx_knowledge_logs_student", table_name="knowledge_update_logs")
    op.drop_index("idx_corrections_type", table_name="manual_corrections")
    op.drop_index("idx_study_uploads_ocr_status", table_name="study_uploads")
    op.drop_index("idx_qa_sessions_student", table_name="qa_sessions")

    # ==========================================================================
    # 3. Drop indexes - High priority
    # ==========================================================================
    # Restore old exam_records index
    op.drop_index("idx_exam_records_student_date", table_name="exam_records")
    op.create_index(
        "idx_exam_student_date",
        "exam_records",
        ["student_id", "exam_date"],
        unique=False,
    )

    op.drop_index("idx_weekly_reports_student_week", table_name="weekly_reports")
    op.drop_index("idx_student_knowledge_compound", table_name="student_knowledge_status")
    op.drop_index("idx_student_knowledge_status", table_name="student_knowledge_status")
    op.drop_index("idx_student_knowledge_student", table_name="student_knowledge_status")
    op.drop_index("idx_model_logs_student", table_name="model_call_logs")
    op.drop_index("idx_model_logs_agent", table_name="model_call_logs")
    op.drop_index("idx_model_logs_created", table_name="model_call_logs")
    op.drop_index("idx_qa_messages_session", table_name="qa_messages")
    op.drop_index("idx_error_book_student_status", table_name="error_book")
    op.drop_index("idx_error_book_recall", table_name="error_book")
    op.drop_index("idx_error_book_subject", table_name="error_book")
    op.drop_index("idx_error_book_student", table_name="error_book")

    # ==========================================================================
    # 4. Drop CHECK constraints
    # ==========================================================================
    op.drop_constraint("chk_correction_status", "manual_corrections", type_="check")
    op.drop_constraint("chk_target_type", "manual_corrections", type_="check")

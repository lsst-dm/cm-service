"""Separate out most tables and indices

Revision ID: 92053b1ad093
Revises: d2a05fd9869c
Create Date: 2024-12-16 20:45:33.619155+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92053b1ad093"
down_revision: str | None = "d2a05fd9869c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_production_name"), "production", ["name"], unique=True)
    op.create_index(op.f("ix_spec_block_name"), "spec_block", ["name"], unique=False)
    op.create_index(op.f("ix_specification_name"), "specification", ["name"], unique=False)
    op.create_index(op.f("ix_campaign_name"), "campaign", ["name"], unique=False)
    op.create_index(op.f("ix_campaign_parent_id"), "campaign", ["parent_id"], unique=False)
    op.create_index(op.f("ix_campaign_spec_block_id"), "campaign", ["spec_block_id"], unique=False)
    op.create_index(op.f("ix_campaign_spec_id"), "campaign", ["spec_id"], unique=False)
    op.create_index(op.f("ix_step_name"), "step", ["name"], unique=False)
    op.create_index(op.f("ix_step_parent_id"), "step", ["parent_id"], unique=False)
    op.create_index(op.f("ix_step_spec_block_id"), "step", ["spec_block_id"], unique=False)
    op.create_index(op.f("ix_group_name"), "group", ["name"], unique=False)
    op.create_index(op.f("ix_group_parent_id"), "group", ["parent_id"], unique=False)
    op.create_index(op.f("ix_group_spec_block_id"), "group", ["spec_block_id"], unique=False)
    op.create_index(op.f("ix_step_dependency_depend_id"), "step_dependency", ["depend_id"], unique=False)
    op.create_index(op.f("ix_step_dependency_prereq_id"), "step_dependency", ["prereq_id"], unique=False)
    op.create_index(op.f("ix_job_name"), "job", ["name"], unique=False)
    op.create_index(op.f("ix_job_parent_id"), "job", ["parent_id"], unique=False)
    op.create_index(op.f("ix_job_spec_block_id"), "job", ["spec_block_id"], unique=False)
    op.create_index(op.f("ix_script_c_id"), "script", ["c_id"], unique=False)
    op.create_index(op.f("ix_script_g_id"), "script", ["g_id"], unique=False)
    op.create_index(op.f("ix_script_j_id"), "script", ["j_id"], unique=False)
    op.create_index(op.f("ix_script_name"), "script", ["name"], unique=False)
    op.create_index(op.f("ix_script_s_id"), "script", ["s_id"], unique=False)
    op.create_index(op.f("ix_script_spec_block_id"), "script", ["spec_block_id"], unique=False)
    op.create_index(op.f("ix_task_set_job_id"), "task_set", ["job_id"], unique=False)
    op.create_index(op.f("ix_wms_task_report_job_id"), "wms_task_report", ["job_id"], unique=False)
    op.create_index(op.f("ix_product_set_job_id"), "product_set", ["job_id"], unique=False)
    op.create_index(op.f("ix_product_set_task_id"), "product_set", ["task_id"], unique=False)
    op.create_index(op.f("ix_queue_c_id"), "queue", ["c_id"], unique=False)
    op.create_index(op.f("ix_queue_g_id"), "queue", ["g_id"], unique=False)
    op.create_index(op.f("ix_queue_j_id"), "queue", ["j_id"], unique=False)
    op.create_index(op.f("ix_queue_s_id"), "queue", ["s_id"], unique=False)
    op.create_index(op.f("ix_queue_script_id"), "queue", ["script_id"], unique=False)
    op.create_index(op.f("ix_script_dependency_depend_id"), "script_dependency", ["depend_id"], unique=False)
    op.create_index(op.f("ix_script_dependency_prereq_id"), "script_dependency", ["prereq_id"], unique=False)
    op.create_index(op.f("ix_script_error_script_id"), "script_error", ["script_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_script_error_script_id"), table_name="script_error", if_exists=True)
    op.drop_index(op.f("ix_script_dependency_prereq_id"), table_name="script_dependency", if_exists=True)
    op.drop_index(op.f("ix_script_dependency_depend_id"), table_name="script_dependency", if_exists=True)
    op.drop_index(op.f("ix_queue_script_id"), table_name="queue", if_exists=True)
    op.drop_index(op.f("ix_queue_s_id"), table_name="queue", if_exists=True)
    op.drop_index(op.f("ix_queue_j_id"), table_name="queue", if_exists=True)
    op.drop_index(op.f("ix_queue_g_id"), table_name="queue", if_exists=True)
    op.drop_index(op.f("ix_queue_c_id"), table_name="queue", if_exists=True)
    op.drop_index(op.f("ix_product_set_task_id"), table_name="product_set", if_exists=True)
    op.drop_index(op.f("ix_product_set_job_id"), table_name="product_set", if_exists=True)
    op.drop_index(op.f("ix_wms_task_report_job_id"), table_name="wms_task_report", if_exists=True)
    op.drop_index(op.f("ix_task_set_job_id"), table_name="task_set", if_exists=True)
    op.drop_index(op.f("ix_script_spec_block_id"), table_name="script", if_exists=True)
    op.drop_index(op.f("ix_script_s_id"), table_name="script", if_exists=True)
    op.drop_index(op.f("ix_script_name"), table_name="script", if_exists=True)
    op.drop_index(op.f("ix_script_j_id"), table_name="script", if_exists=True)
    op.drop_index(op.f("ix_script_g_id"), table_name="script", if_exists=True)
    op.drop_index(op.f("ix_script_c_id"), table_name="script", if_exists=True)
    op.drop_index(op.f("ix_job_spec_block_id"), table_name="job", if_exists=True)
    op.drop_index(op.f("ix_job_parent_id"), table_name="job", if_exists=True)
    op.drop_index(op.f("ix_job_name"), table_name="job", if_exists=True)
    op.drop_index(op.f("ix_step_dependency_prereq_id"), table_name="step_dependency", if_exists=True)
    op.drop_index(op.f("ix_step_dependency_depend_id"), table_name="step_dependency", if_exists=True)
    op.drop_index(op.f("ix_group_spec_block_id"), table_name="group", if_exists=True)
    op.drop_index(op.f("ix_group_parent_id"), table_name="group", if_exists=True)
    op.drop_index(op.f("ix_group_name"), table_name="group", if_exists=True)
    op.drop_index(op.f("ix_step_spec_block_id"), table_name="step", if_exists=True)
    op.drop_index(op.f("ix_step_parent_id"), table_name="step", if_exists=True)
    op.drop_index(op.f("ix_step_name"), table_name="step", if_exists=True)
    op.drop_index(op.f("ix_campaign_spec_id"), table_name="campaign", if_exists=True)
    op.drop_index(op.f("ix_campaign_spec_block_id"), table_name="campaign", if_exists=True)
    op.drop_index(op.f("ix_campaign_parent_id"), table_name="campaign", if_exists=True)
    op.drop_index(op.f("ix_campaign_name"), table_name="campaign", if_exists=True)
    op.drop_index(op.f("ix_specification_name"), table_name="specification", if_exists=True)
    op.drop_index(op.f("ix_spec_block_name"), table_name="spec_block", if_exists=True)
    op.drop_index(op.f("ix_production_name"), table_name="production", if_exists=True)

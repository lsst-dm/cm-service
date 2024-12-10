"""Autogenerated from Model v0.4.0

Revision ID: f5e50e000a35
Revises: fc48b549d66f
Create Date: 2024-12-10 20:47:05.843863+00:00

This migration was auto-generated by `alembic revision --autogenerate` based on
the state of the application model as of tag release v0.4.0, and hand-tuned for
correctness.

Hand tuning consisted of:

- All generated Enums modified with `create_type=False`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import MetaData

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5e50e000a35"
down_revision: str | None = "fc48b549d66f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "pipetask_error_type",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "error_source",
            sa.Enum(
                "cmservice",
                "local_script",
                "manifest",
                name="errorsourceenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column(
            "error_flavor",
            sa.Enum(
                "infrastructure",
                "configuration",
                "pipelines",
                name="errorflavorenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column(
            "error_action",
            sa.Enum(
                "fail",
                "requeue_and_pause",
                "rescue",
                "auto_retry",
                "review",
                "accept",
                name="erroractionenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("diagnostic_message", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_name", "diagnostic_message"),
    )
    op.create_table(
        "production",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_production_name"), "production", ["name"], unique=True)
    op.create_table(
        "script_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_script_template_name"), "script_template", ["name"], unique=False)
    op.create_table(
        "spec_block",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("handler", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("spec_aliases", sa.JSON(), nullable=True),
        sa.Column("scripts", sa.JSON(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spec_block_name"), "spec_block", ["name"], unique=False)
    op.create_table(
        "specification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("spec_aliases", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_specification_name"), "specification", ["name"], unique=False)
    op.create_table(
        "campaign",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec_id", sa.Integer(), nullable=False),
        sa.Column("spec_block_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "failed",
                "rejected",
                "paused",
                "rescuable",
                "waiting",
                "ready",
                "prepared",
                "running",
                "reviewable",
                "accepted",
                "rescued",
                name="statusenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("handler", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("spec_aliases", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["production.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_block_id"], ["spec_block.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_id"], ["specification.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
        sa.UniqueConstraint("parent_id", "name"),
    )
    op.create_index(op.f("ix_campaign_name"), "campaign", ["name"], unique=False)
    op.create_index(op.f("ix_campaign_parent_id"), "campaign", ["parent_id"], unique=False)
    op.create_index(op.f("ix_campaign_spec_block_id"), "campaign", ["spec_block_id"], unique=False)
    op.create_index(op.f("ix_campaign_spec_id"), "campaign", ["spec_id"], unique=False)
    op.create_table(
        "step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec_block_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "failed",
                "rejected",
                "paused",
                "rescuable",
                "waiting",
                "ready",
                "prepared",
                "running",
                "reviewable",
                "accepted",
                "rescued",
                name="statusenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("handler", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("spec_aliases", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_block_id"], ["spec_block.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
        sa.UniqueConstraint("parent_id", "name"),
    )
    op.create_index(op.f("ix_step_name"), "step", ["name"], unique=False)
    op.create_index(op.f("ix_step_parent_id"), "step", ["parent_id"], unique=False)
    op.create_index(op.f("ix_step_spec_block_id"), "step", ["spec_block_id"], unique=False)
    op.create_table(
        "group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec_block_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "failed",
                "rejected",
                "paused",
                "rescuable",
                "waiting",
                "ready",
                "prepared",
                "running",
                "reviewable",
                "accepted",
                "rescued",
                name="statusenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("handler", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("spec_aliases", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["step.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_block_id"], ["spec_block.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
        sa.UniqueConstraint("parent_id", "name"),
    )
    op.create_index(op.f("ix_group_name"), "group", ["name"], unique=False)
    op.create_index(op.f("ix_group_parent_id"), "group", ["parent_id"], unique=False)
    op.create_index(op.f("ix_group_spec_block_id"), "group", ["spec_block_id"], unique=False)
    op.create_table(
        "step_dependency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prereq_id", sa.Integer(), nullable=False),
        sa.Column("depend_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["depend_id"], ["step.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prereq_id"], ["step.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_step_dependency_depend_id"), "step_dependency", ["depend_id"], unique=False)
    op.create_index(op.f("ix_step_dependency_prereq_id"), "step_dependency", ["prereq_id"], unique=False)
    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec_block_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "failed",
                "rejected",
                "paused",
                "rescuable",
                "waiting",
                "ready",
                "prepared",
                "running",
                "reviewable",
                "accepted",
                "rescued",
                name="statusenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("handler", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("spec_aliases", sa.JSON(), nullable=True),
        sa.Column("wms_job_id", sa.String(), nullable=True),
        sa.Column("stamp_url", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["group.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_block_id"], ["spec_block.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
    )
    op.create_index(op.f("ix_job_name"), "job", ["name"], unique=False)
    op.create_index(op.f("ix_job_parent_id"), "job", ["parent_id"], unique=False)
    op.create_index(op.f("ix_job_spec_block_id"), "job", ["spec_block_id"], unique=False)
    op.create_table(
        "script",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spec_block_id", sa.Integer(), nullable=False),
        sa.Column(
            "parent_level",
            sa.Enum(
                "production",
                "campaign",
                "step",
                "group",
                "job",
                "script",
                "n_levels",
                name="levelenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("c_id", sa.Integer(), nullable=True),
        sa.Column("s_id", sa.Integer(), nullable=True),
        sa.Column("g_id", sa.Integer(), nullable=True),
        sa.Column("j_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "failed",
                "rejected",
                "paused",
                "rescuable",
                "waiting",
                "ready",
                "prepared",
                "running",
                "reviewable",
                "accepted",
                "rescued",
                name="statusenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.Enum(
                "default",
                "no_script",
                "bash",
                "slurm",
                "htcondor",
                name="scriptmethodenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("handler", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("child_config", sa.JSON(), nullable=True),
        sa.Column("collections", sa.JSON(), nullable=True),
        sa.Column("script_url", sa.String(), nullable=True),
        sa.Column("stamp_url", sa.String(), nullable=True),
        sa.Column("log_url", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["c_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["g_id"], ["group.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["j_id"], ["job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["s_id"], ["step.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_block_id"], ["spec_block.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
    )
    op.create_index(op.f("ix_script_c_id"), "script", ["c_id"], unique=False)
    op.create_index(op.f("ix_script_g_id"), "script", ["g_id"], unique=False)
    op.create_index(op.f("ix_script_j_id"), "script", ["j_id"], unique=False)
    op.create_index(op.f("ix_script_name"), "script", ["name"], unique=False)
    op.create_index(op.f("ix_script_s_id"), "script", ["s_id"], unique=False)
    op.create_index(op.f("ix_script_spec_block_id"), "script", ["spec_block_id"], unique=False)
    op.create_table(
        "task_set",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column("n_expected", sa.Integer(), nullable=False),
        sa.Column("n_done", sa.Integer(), nullable=False),
        sa.Column("n_failed", sa.Integer(), nullable=False),
        sa.Column("n_failed_upstream", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
    )
    op.create_index(op.f("ix_task_set_job_id"), "task_set", ["job_id"], unique=False)
    op.create_table(
        "wms_task_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column("n_unknown", sa.Integer(), nullable=False),
        sa.Column("n_misfit", sa.Integer(), nullable=False),
        sa.Column("n_unready", sa.Integer(), nullable=False),
        sa.Column("n_ready", sa.Integer(), nullable=False),
        sa.Column("n_pending", sa.Integer(), nullable=False),
        sa.Column("n_running", sa.Integer(), nullable=False),
        sa.Column("n_deleted", sa.Integer(), nullable=False),
        sa.Column("n_held", sa.Integer(), nullable=False),
        sa.Column("n_succeeded", sa.Integer(), nullable=False),
        sa.Column("n_failed", sa.Integer(), nullable=False),
        sa.Column("n_pruned", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
    )
    op.create_index(op.f("ix_wms_task_report_job_id"), "wms_task_report", ["job_id"], unique=False)
    op.create_table(
        "pipetask_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("error_type_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("quanta", sa.String(), nullable=False),
        sa.Column("diagnostic_message", sa.String(), nullable=False),
        sa.Column("data_id", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["error_type_id"], ["pipetask_error_type.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_set.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quanta"),
    )
    op.create_index(
        op.f("ix_pipetask_error_error_type_id"), "pipetask_error", ["error_type_id"], unique=False
    )
    op.create_index(op.f("ix_pipetask_error_task_id"), "pipetask_error", ["task_id"], unique=False)
    op.create_table(
        "product_set",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column("n_expected", sa.Integer(), nullable=False),
        sa.Column("n_done", sa.Integer(), nullable=False),
        sa.Column("n_failed", sa.Integer(), nullable=False),
        sa.Column("n_failed_upstream", sa.Integer(), nullable=False),
        sa.Column("n_missing", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_set.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fullname"),
    )
    op.create_index(op.f("ix_product_set_job_id"), "product_set", ["job_id"], unique=False)
    op.create_index(op.f("ix_product_set_task_id"), "product_set", ["task_id"], unique=False)
    op.create_table(
        "queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("time_created", sa.DateTime(), nullable=False),
        sa.Column("time_updated", sa.DateTime(), nullable=False),
        sa.Column("time_finished", sa.DateTime(), nullable=True),
        sa.Column("time_next_check", sa.DateTime(), nullable=True),
        sa.Column("interval", sa.Float(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column(
            "node_level",
            sa.Enum(
                "production",
                "campaign",
                "step",
                "group",
                "job",
                "script",
                "n_levels",
                name="levelenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("c_id", sa.Integer(), nullable=True),
        sa.Column("s_id", sa.Integer(), nullable=True),
        sa.Column("g_id", sa.Integer(), nullable=True),
        sa.Column("j_id", sa.Integer(), nullable=True),
        sa.Column("script_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["c_id"], ["campaign.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["g_id"], ["group.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["j_id"], ["job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["s_id"], ["step.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["script_id"], ["script.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_queue_c_id"), "queue", ["c_id"], unique=False)
    op.create_index(op.f("ix_queue_g_id"), "queue", ["g_id"], unique=False)
    op.create_index(op.f("ix_queue_j_id"), "queue", ["j_id"], unique=False)
    op.create_index(op.f("ix_queue_s_id"), "queue", ["s_id"], unique=False)
    op.create_index(op.f("ix_queue_script_id"), "queue", ["script_id"], unique=False)
    op.create_table(
        "script_dependency",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prereq_id", sa.Integer(), nullable=False),
        sa.Column("depend_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["depend_id"], ["script.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prereq_id"], ["script.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_script_dependency_depend_id"), "script_dependency", ["depend_id"], unique=False)
    op.create_index(op.f("ix_script_dependency_prereq_id"), "script_dependency", ["prereq_id"], unique=False)
    op.create_table(
        "script_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("script_id", sa.Integer(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "cmservice",
                "local_script",
                "manifest",
                name="errorsourceenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column("diagnostic_message", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["script_id"], ["script.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_script_error_script_id"), "script_error", ["script_id"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_script_error_script_id"), table_name="script_error")
    op.drop_table("script_error")
    op.drop_index(op.f("ix_script_dependency_prereq_id"), table_name="script_dependency")
    op.drop_index(op.f("ix_script_dependency_depend_id"), table_name="script_dependency")
    op.drop_table("script_dependency")
    op.drop_index(op.f("ix_queue_script_id"), table_name="queue")
    op.drop_index(op.f("ix_queue_s_id"), table_name="queue")
    op.drop_index(op.f("ix_queue_j_id"), table_name="queue")
    op.drop_index(op.f("ix_queue_g_id"), table_name="queue")
    op.drop_index(op.f("ix_queue_c_id"), table_name="queue")
    op.drop_table("queue")
    op.drop_index(op.f("ix_product_set_task_id"), table_name="product_set")
    op.drop_index(op.f("ix_product_set_job_id"), table_name="product_set")
    op.drop_table("product_set")
    op.drop_index(op.f("ix_pipetask_error_task_id"), table_name="pipetask_error")
    op.drop_index(op.f("ix_pipetask_error_error_type_id"), table_name="pipetask_error")
    op.drop_table("pipetask_error")
    op.drop_index(op.f("ix_wms_task_report_job_id"), table_name="wms_task_report")
    op.drop_table("wms_task_report")
    op.drop_index(op.f("ix_task_set_job_id"), table_name="task_set")
    op.drop_table("task_set")
    op.drop_index(op.f("ix_script_spec_block_id"), table_name="script")
    op.drop_index(op.f("ix_script_s_id"), table_name="script")
    op.drop_index(op.f("ix_script_name"), table_name="script")
    op.drop_index(op.f("ix_script_j_id"), table_name="script")
    op.drop_index(op.f("ix_script_g_id"), table_name="script")
    op.drop_index(op.f("ix_script_c_id"), table_name="script")
    op.drop_table("script")
    op.drop_index(op.f("ix_job_spec_block_id"), table_name="job")
    op.drop_index(op.f("ix_job_parent_id"), table_name="job")
    op.drop_index(op.f("ix_job_name"), table_name="job")
    op.drop_table("job")
    op.drop_index(op.f("ix_step_dependency_prereq_id"), table_name="step_dependency")
    op.drop_index(op.f("ix_step_dependency_depend_id"), table_name="step_dependency")
    op.drop_table("step_dependency")
    op.drop_index(op.f("ix_group_spec_block_id"), table_name="group")
    op.drop_index(op.f("ix_group_parent_id"), table_name="group")
    op.drop_index(op.f("ix_group_name"), table_name="group")
    op.drop_table("group")
    op.drop_index(op.f("ix_step_spec_block_id"), table_name="step")
    op.drop_index(op.f("ix_step_parent_id"), table_name="step")
    op.drop_index(op.f("ix_step_name"), table_name="step")
    op.drop_table("step")
    op.drop_index(op.f("ix_campaign_spec_id"), table_name="campaign")
    op.drop_index(op.f("ix_campaign_spec_block_id"), table_name="campaign")
    op.drop_index(op.f("ix_campaign_parent_id"), table_name="campaign")
    op.drop_index(op.f("ix_campaign_name"), table_name="campaign")
    op.drop_table("campaign")
    op.drop_index(op.f("ix_specification_name"), table_name="specification")
    op.drop_table("specification")
    op.drop_index(op.f("ix_spec_block_name"), table_name="spec_block")
    op.drop_table("spec_block")
    op.drop_index(op.f("ix_script_template_name"), table_name="script_template")
    op.drop_table("script_template")
    op.drop_index(op.f("ix_production_name"), table_name="production")
    op.drop_table("production")
    op.drop_table("pipetask_error_type")
    # ### end Alembic commands ###

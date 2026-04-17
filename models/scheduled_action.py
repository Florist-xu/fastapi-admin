from tortoise import fields

from models.common import BaseModel


class SystemScheduledAction(BaseModel):
    actor_id = fields.CharField(max_length=36, null=True, description="Scheduler user id")
    actor_name = fields.CharField(max_length=255, null=True, description="Scheduler user name")
    operation_type = fields.CharField(max_length=80, null=False, description="Normalized operation type")
    resource = fields.CharField(max_length=40, null=False, description="Resource group")
    action = fields.CharField(max_length=40, null=False, description="Action name")
    summary = fields.CharField(max_length=500, null=True, description="Task summary")
    payload = fields.JSONField(null=True, description="Normalized execution payload")
    execute_at = fields.DatetimeField(null=False, description="Execute at")
    status = fields.CharField(max_length=20, null=False, default="pending", description="pending/running/succeeded/failed")
    started_at = fields.DatetimeField(null=True, description="Started time")
    executed_at = fields.DatetimeField(null=True, description="Executed time")
    result_message = fields.TextField(null=True, description="Execution result message")
    error_message = fields.TextField(null=True, description="Execution error message")

    class Meta:
        table = "system_scheduled_action"
        table_description = "Scheduled action task"
        ordering = ["execute_at", "created_at"]


class SystemScheduledClientEvent(BaseModel):
    user_id = fields.CharField(max_length=36, null=False, description="Target user id")
    action_name = fields.CharField(max_length=50, null=False, description="Client action name")
    summary = fields.CharField(max_length=255, null=True, description="Client action summary")
    payload = fields.JSONField(null=True, description="Client action payload")
    source_task_id = fields.CharField(max_length=36, null=True, description="Source scheduled task id")
    available_at = fields.DatetimeField(null=False, auto_now_add=True, description="Available time")
    consumed_at = fields.DatetimeField(null=True, description="Consumed time")

    class Meta:
        table = "system_scheduled_client_event"
        table_description = "Scheduled client event queue"
        ordering = ["available_at", "created_at"]

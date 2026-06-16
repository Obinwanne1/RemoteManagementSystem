from marshmallow import Schema, fields, validate, EXCLUDE

_SCHEDULE_TYPES = ("daily", "weekly", "monthly", "manual")


class AutomationProfileCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    customer_id = fields.String(load_default=None, allow_none=True)
    device_group_id = fields.String(load_default=None, allow_none=True)
    is_active = fields.Boolean(load_default=True)
    schedule_type = fields.String(load_default="weekly", validate=validate.OneOf(_SCHEDULE_TYPES))
    schedule_config = fields.Dict(load_default={})
    run_on_new_agents = fields.Boolean(load_default=False)
    notification_emails = fields.List(fields.Email(), load_default=[])
    os_patch_config = fields.Dict(load_default={})
    software_patch_config = fields.Dict(load_default={})
    disk_config = fields.Dict(load_default={})
    maintenance_config = fields.Dict(load_default={})
    scripts = fields.List(fields.Dict(), load_default=[])


class AutomationProfileUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate.Length(min=1, max=255))
    is_active = fields.Boolean()
    schedule_type = fields.String(validate=validate.OneOf(_SCHEDULE_TYPES))
    schedule_config = fields.Dict()
    run_on_new_agents = fields.Boolean()
    notification_emails = fields.List(fields.Email())
    os_patch_config = fields.Dict()
    software_patch_config = fields.Dict()
    disk_config = fields.Dict()
    maintenance_config = fields.Dict()
    scripts = fields.List(fields.Dict())

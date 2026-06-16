from marshmallow import Schema, fields, validate, EXCLUDE

_SEVERITIES = ("info", "warning", "critical")
_OPERATORS = ("gt", "lt", "gte", "lte", "eq")


class AlertRuleCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    metric = fields.String(required=True, validate=validate.Length(min=1, max=100))
    operator = fields.String(required=True, validate=validate.OneOf(_OPERATORS))
    threshold = fields.Float(load_default=None, allow_none=True)
    severity = fields.String(load_default="warning", validate=validate.OneOf(_SEVERITIES))
    cooldown_minutes = fields.Integer(load_default=15, validate=validate.Range(min=1, max=1440))
    notification_channels = fields.Dict(load_default={})
    auto_create_ticket = fields.Boolean(load_default=False)
    is_active = fields.Boolean(load_default=True)
    customer_id = fields.String(load_default=None, allow_none=True)
    device_group_id = fields.String(load_default=None, allow_none=True)


class AlertRuleUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate.Length(min=1, max=255))
    metric = fields.String(validate=validate.Length(min=1, max=100))
    operator = fields.String(validate=validate.OneOf(_OPERATORS))
    threshold = fields.Float(allow_none=True)
    severity = fields.String(validate=validate.OneOf(_SEVERITIES))
    cooldown_minutes = fields.Integer(validate=validate.Range(min=1, max=1440))
    notification_channels = fields.Dict()
    auto_create_ticket = fields.Boolean()
    is_active = fields.Boolean()

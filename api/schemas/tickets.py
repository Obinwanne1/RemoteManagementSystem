from marshmallow import Schema, fields, validate, EXCLUDE

_PRIORITIES = ("low", "medium", "high", "critical")
_STATUSES = ("open", "in_progress", "resolved", "closed")


class TicketCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    title = fields.String(required=True, validate=validate.Length(min=1, max=500))
    customer_id = fields.String(required=True, validate=validate.Length(min=1))
    description = fields.String(load_default=None, allow_none=True)
    device_id = fields.String(load_default=None, allow_none=True)
    assignee_id = fields.String(load_default=None, allow_none=True)
    priority = fields.String(load_default="medium", validate=validate.OneOf(_PRIORITIES))
    status = fields.String(load_default="open", validate=validate.OneOf(_STATUSES))
    source = fields.String(load_default="manual", validate=validate.Length(max=50))
    alert_id = fields.String(load_default=None, allow_none=True)
    tags = fields.List(fields.String(), load_default=[])


class TicketUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    title = fields.String(validate=validate.Length(min=1, max=500))
    description = fields.String(allow_none=True)
    assignee_id = fields.String(allow_none=True)
    priority = fields.String(validate=validate.OneOf(_PRIORITIES))
    status = fields.String(validate=validate.OneOf(_STATUSES))
    tags = fields.List(fields.String())


class CommentCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    body = fields.String(required=True, validate=validate.Length(min=1))
    is_internal = fields.Boolean(load_default=False)

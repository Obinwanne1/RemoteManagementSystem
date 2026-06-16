from marshmallow import Schema, fields, validate, EXCLUDE


class NetworkScanSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    scan_range = fields.String(required=True, validate=validate.Length(min=1, max=100))
    customer_id = fields.String(load_default=None, allow_none=True)


class _AgentlessHostSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    ip = fields.String(required=True, validate=validate.Length(min=1, max=45))
    mac = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    vendor = fields.String(load_default="Unknown", validate=validate.Length(max=255))
    platform = fields.String(load_default="unknown", validate=validate.Length(max=50))
    device_type = fields.String(load_default="unknown", validate=validate.Length(max=50))


class AgentlessDevicesSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    hosts = fields.List(
        fields.Nested(_AgentlessHostSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    customer_id = fields.String(load_default=None, allow_none=True)

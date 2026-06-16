from marshmallow import Schema, fields, validate, EXCLUDE

_TIERS = ("standard", "premium", "enterprise")


class CustomerCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    email = fields.Email(load_default=None, allow_none=True)
    phone = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=50))
    address = fields.String(load_default=None, allow_none=True)
    tier = fields.String(load_default="standard", validate=validate.OneOf(_TIERS))
    notes = fields.String(load_default=None, allow_none=True)


class CustomerUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate.Length(min=1, max=255))
    email = fields.Email(allow_none=True)
    phone = fields.String(allow_none=True, validate=validate.Length(max=50))
    address = fields.String(allow_none=True)
    tier = fields.String(validate=validate.OneOf(_TIERS))
    notes = fields.String(allow_none=True)


class DeviceGroupCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    customer_id = fields.String(required=True, validate=validate.Length(min=1))
    description = fields.String(load_default=None, allow_none=True)

from marshmallow import Schema, fields, validate, EXCLUDE

_ROLES = ("admin", "technician", "viewer")


class CreateUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True)
    full_name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    password = fields.String(required=True, validate=validate.Length(min=1))
    role = fields.String(load_default="technician", validate=validate.OneOf(_ROLES))
    must_change_password = fields.Boolean(load_default=False)


class UpdateUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    full_name = fields.String(validate=validate.Length(min=1, max=255))
    role = fields.String(validate=validate.OneOf(_ROLES))
    is_active = fields.Boolean()
    password = fields.String(validate=validate.Length(min=1))
    must_change_password = fields.Boolean()

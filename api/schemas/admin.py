from marshmallow import Schema, fields, validate, EXCLUDE

_ROLES = ("admin", "technician", "viewer", "client")


class CreateUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True)
    full_name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    password = fields.String(required=True, validate=validate.Length(min=1))
    role = fields.String(load_default="technician", validate=validate.OneOf(_ROLES))
    must_change_password = fields.Boolean(load_default=False)
    department_id = fields.String(load_default=None, allow_none=True)
    customer_id = fields.String(load_default=None, allow_none=True)


class UpdateUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    full_name = fields.String(validate=validate.Length(min=1, max=255))
    role = fields.String(validate=validate.OneOf(_ROLES))
    is_active = fields.Boolean()
    password = fields.String(validate=validate.Length(min=1))
    must_change_password = fields.Boolean()
    department_id = fields.String(allow_none=True)
    customer_id = fields.String(allow_none=True)


class DepartmentCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    description = fields.String(load_default=None, allow_none=True)
    color = fields.String(load_default="#407E3C", validate=validate.Length(equal=7))


class DepartmentUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate.Length(min=1, max=100))
    description = fields.String(allow_none=True)
    color = fields.String(validate=validate.Length(equal=7))

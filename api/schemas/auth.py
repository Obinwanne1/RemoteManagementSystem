from marshmallow import Schema, fields, validate, EXCLUDE


class LoginSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=1))


class ChangePasswordSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    current_password = fields.String(required=True, validate=validate.Length(min=1))
    new_password = fields.String(required=True, validate=validate.Length(min=1))


class ForceChangePasswordSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    new_password = fields.String(required=True, validate=validate.Length(min=1))


class MfaEnableSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    code = fields.String(required=True, validate=validate.Length(min=1))


class MfaLoginSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    mfa_token = fields.String(required=True, validate=validate.Length(min=1))
    code = fields.String(required=True, validate=validate.Length(min=1))


class MfaDisableSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    password = fields.String(required=True, validate=validate.Length(min=1))


class PasswordResetRequestSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True)


class PasswordResetConfirmSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    token = fields.String(required=True, validate=validate.Length(min=1))
    new_password = fields.String(required=True, validate=validate.Length(min=1))

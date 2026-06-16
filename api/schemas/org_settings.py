from marshmallow import Schema, fields, validate, EXCLUDE


class OrgSettingsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    company_name = fields.String(allow_none=True, validate=validate.Length(max=255))
    company_address = fields.String(allow_none=True)
    company_email = fields.Email(allow_none=True)
    company_phone = fields.String(allow_none=True, validate=validate.Length(max=50))
    payment_terms = fields.String(allow_none=True)
    bank_details = fields.String(allow_none=True)
    footer_notes = fields.String(allow_none=True)
    app_name = fields.String(allow_none=True, validate=validate.Length(max=100))
    tagline = fields.String(allow_none=True, validate=validate.Length(max=255))
    primary_color = fields.String(allow_none=True, validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"))
    currency = fields.String(allow_none=True, validate=validate.Length(max=10))
    timezone = fields.String(allow_none=True, validate=validate.Length(max=100))

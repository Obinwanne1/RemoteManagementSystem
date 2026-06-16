from marshmallow import Schema, fields, validate, EXCLUDE

_INVOICE_STATUSES = ("draft", "sent", "paid", "overdue")


class GenerateInvoiceSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    customer_id = fields.String(required=True, validate=validate.Length(min=1))
    per_device_rate = fields.Float(load_default=15.00, validate=validate.Range(min=0))
    tax_rate = fields.Float(load_default=0.0, validate=validate.Range(min=0, max=1))
    period_start = fields.String(load_default=None, allow_none=True)
    period_end = fields.String(load_default=None, allow_none=True)
    due_date = fields.String(load_default=None, allow_none=True)
    notes = fields.String(load_default=None, allow_none=True)


class InvoiceStatusSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    status = fields.String(required=True, validate=validate.OneOf(_INVOICE_STATUSES))

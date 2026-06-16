from marshmallow import Schema, fields, validate, EXCLUDE

_FILE_TYPES = ("bat", "ps1", "py")
_OS_TARGETS = ("windows", "linux", "macos", "any")

MAX_SCRIPT_BYTES = 512 * 1024


def _content_size(value):
    if len(value.encode("utf-8")) > MAX_SCRIPT_BYTES:
        raise validate.ValidationError("Script content exceeds 512KB limit")


class ScriptCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    file_type = fields.String(required=True, validate=validate.OneOf(_FILE_TYPES))
    content = fields.String(required=True, validate=[validate.Length(min=1), _content_size])
    description = fields.String(load_default=None, allow_none=True)
    os_target = fields.String(load_default="windows", validate=validate.OneOf(_OS_TARGETS))
    tags = fields.List(fields.String(), load_default=[])


class ScriptUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate.Length(min=1, max=255))
    description = fields.String(allow_none=True)
    content = fields.String(validate=[validate.Length(min=1), _content_size])
    tags = fields.List(fields.String())


class RunScriptSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    device_ids = fields.List(
        fields.String(validate=validate.Length(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )
    timeout_seconds = fields.Integer(load_default=300, validate=validate.Range(min=10, max=3600))

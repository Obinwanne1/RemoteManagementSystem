import json
from flask import Blueprint, jsonify, render_template_string

docs_bp = Blueprint("docs", __name__)

_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>RMM API Docs</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
  <style>
    body { margin: 0; }
    .topbar { background-color: #407E3C !important; }
    .topbar-wrapper img { display: none; }
    .topbar-wrapper::before {
      content: "RMM Platform API";
      color: #fff;
      font-size: 1.2rem;
      font-weight: 600;
      padding-left: 1rem;
    }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: "/api/openapi.json",
    dom_id: "#swagger-ui",
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: "BaseLayout",
    deepLinking: true,
    persistAuthorization: true,
    displayRequestDuration: true,
    filter: true,
  });
</script>
</body>
</html>"""


@docs_bp.route("/api/docs")
def swagger_ui():
    return render_template_string(_SWAGGER_UI_HTML)


@docs_bp.route("/api/openapi.json")
def openapi_spec():
    from swagger_spec import OPENAPI_SPEC
    return jsonify(OPENAPI_SPEC)

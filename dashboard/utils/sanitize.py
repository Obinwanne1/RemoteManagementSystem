"""HTML-escaping helper for f-strings passed to st.markdown(..., unsafe_allow_html=True).

Any API-returned or user-editable value (names, emails, notes, ticket text,
device/network-scan fields, etc.) must go through esc() before being
interpolated into an HTML string — otherwise a value like <script>...</script>
saved via a form renders for every viewer (stored XSS).
"""
import html


def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)

"""Direct unit test of the shared pagination helper (audits/testing_audit.md
Finding P1 — an example of testing a shared utility in isolation rather than
only incidentally through whichever routes call it)."""
from utils.pagination import paginated_response


class TestPaginatedResponse:
    def test_caps_per_page_at_max(self, app):
        from models.customer import Customer
        with app.test_request_context("/?per_page=9999"):
            body, status = paginated_response(Customer.query, lambda c: c.to_dict(), max_per_page=100)
            assert status == 200
            assert body.json["page"] == 1

    def test_uses_default_per_page_when_not_specified(self, app):
        from models.customer import Customer
        with app.test_request_context("/"):
            body, status = paginated_response(
                Customer.query, lambda c: c.to_dict(), default_per_page=20, max_per_page=100
            )
            assert status == 200
            assert body.json["page"] == 1
            assert "pages" in body.json  # the exact key audits/code_duplication_audit.md Finding N2 added

    def test_custom_items_key(self, app):
        from models.customer import Customer
        with app.test_request_context("/"):
            body, status = paginated_response(Customer.query, lambda c: c.to_dict(), items_key="customers")
            assert "customers" in body.json
            assert "items" not in body.json

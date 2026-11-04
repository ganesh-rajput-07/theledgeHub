from tests.factories import make_invoice_pdf
from tests.integration.test_extraction_api import extract, upload


def rules_url(tenant):
    return f"/api/v1/workspaces/{tenant.workspace_id}/extraction-rules"


def save(tenant, config):
    return tenant.put(rules_url(tenant), json=config)


def test_editor_lists_catalog_fields_operators_and_defaults(api):
    editor = api.get(rules_url(api)).json()
    keys = [rule["key"] for rule in editor["predefined"]]
    assert {"total_matches", "duplicate", "buyer_is_client", "large_amount"} <= set(keys)
    assert editor["config"]["builtin"]["total_matches"] == {
        "enabled": True,
        "severity": "error",
        "params": {"max_round_off": 1.0},
    }
    assert "greater_than" in editor["operators"]["amount"] and "greater_than" not in editor["operators"]["text"]
    assert {"key": "total", "label": "Total", "type": "amount"} in editor["fields"]


def test_custom_error_rule_rechecks_pending_invoices_and_blocks_approval(api):
    pdf, _ = make_invoice_pdf(1)
    doc_id = upload(api, pdf)
    assert extract(api, doc_id)["issues"] == []

    config = api.get(rules_url(api)).json()["config"]
    config["custom"] = [
        {
            "field": "total",
            "operator": "greater_than",
            "value": "1",
            "severity": "error",
            "message": "Partner must sign off every invoice",
        }
    ]
    saved = save(api, config)
    assert saved.status_code == 200, saved.text
    assert saved.json()["rechecked"] == 1

    issues = api.get(f"/api/v1/documents/{doc_id}/extraction").json()["issues"]
    assert [i["message"] for i in issues] == ["Partner must sign off every invoice"]
    approve = api.post(f"/api/v1/documents/{doc_id}/extraction/approve")
    assert approve.status_code == 409 and "Partner must sign off" in approve.json()["detail"]

    config["custom"][0]["severity"] = "warning"  # downgraded: flagged, but approvable
    save(api, config)
    assert api.post(f"/api/v1/documents/{doc_id}/extraction/approve").status_code == 200


def test_billed_to_this_client_rule(api):
    pdf, truth = make_invoice_pdf(2)
    doc_id = upload(api, pdf)
    extract(api, doc_id)
    config = api.get(rules_url(api)).json()["config"]
    config["builtin"]["buyer_is_client"] = {
        "enabled": True,
        "severity": "error",
        "params": {"client_gstin": truth["vendor_gstin"]},
    }
    assert save(api, config).status_code == 200
    codes = [i["code"] for i in api.get(f"/api/v1/documents/{doc_id}/extraction").json()["issues"]]
    assert "wrong_buyer" in codes  # this invoice is billed to someone else


def test_new_extractions_use_the_workspace_rules(api):
    config = api.get(rules_url(api)).json()["config"]
    config["builtin"]["large_amount"] = {"enabled": True, "severity": "warning", "params": {"amount": 1}}
    save(api, config)
    pdf, _ = make_invoice_pdf(3)
    issues = extract(api, upload(api, pdf))["issues"]
    assert ("large_amount", "warning") in {(i["code"], i["severity"]) for i in issues}


def test_invalid_rules_are_rejected_with_a_clear_message(api):
    config = api.get(rules_url(api)).json()["config"]
    config["custom"] = [{"field": "vendor_name", "operator": "greater_than", "value": "5", "message": "x"}]
    response = save(api, config)
    assert response.status_code == 422 and "can't be used" in response.json()["detail"]
    assert api.get(rules_url(api)).json()["config"]["custom"] == []  # nothing was saved


def test_only_managers_edit_and_other_tenants_get_404(api, make_tenant):
    member, outsider = make_tenant("member"), make_tenant("outsider")
    api.post(f"/api/v1/organizations/{api.org_id}/members", json={"email": member.email})
    config = api.get(rules_url(api)).json()["config"]

    assert member.get(rules_url(api)).status_code == 200  # members can see the rules
    assert member.put(rules_url(api), json=config).status_code == 403
    assert outsider.get(rules_url(api)).status_code == 404
    assert outsider.put(rules_url(api), json=config).status_code == 404


def test_rule_changes_are_audited(api):
    config = api.get(rules_url(api)).json()["config"]
    config["builtin"]["date_not_future"]["enabled"] = True
    save(api, config)
    entry = api.get(
        f"/api/v1/organizations/{api.org_id}/audit-logs", params={"action": "extraction_rules.update"}
    ).json()[0]
    assert entry["actor_email"] == api.email
    assert "date_not_future" in entry["details"]["enabled"]


def test_rules_are_per_workspace(api):
    other = api.post(f"/api/v1/organizations/{api.org_id}/workspaces", json={"name": "Client B"}).json()["id"]
    config = api.get(rules_url(api)).json()["config"]
    config["builtin"]["total_matches"]["enabled"] = False
    save(api, config)
    other_rules = api.get(f"/api/v1/workspaces/{other}/extraction-rules").json()["config"]
    assert other_rules["builtin"]["total_matches"]["enabled"] is True

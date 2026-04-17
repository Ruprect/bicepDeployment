# tests/test_header_generator.py
import json
import pytest
from pathlib import Path
from deployScript.header_generator import (
    generate_logic_app_header,
    generate_keyvault_header,
    _infer_bicep_type,
    _is_used_in_body,
)


def _write_params(tmp_path, params_dict):
    """Write a parameters.local.json with the given key→value dict."""
    data = {
        "$schema": "...",
        "contentVersion": "1.0.0.0",
        "parameters": {k: {"value": v} for k, v in params_dict.items()},
    }
    p = tmp_path / "parameters.local.json"
    p.write_text(json.dumps(data))
    return p


def test_infer_type_string():
    assert _infer_bicep_type("hello") == "string"


def test_infer_type_int():
    assert _infer_bicep_type(42) == "int"


def test_infer_type_bool():
    assert _infer_bicep_type(True) == "bool"


def test_infer_type_object():
    assert _infer_bicep_type({}) == "object"
    assert _infer_bicep_type({"a": 1}) == "object"


def test_infer_type_array():
    assert _infer_bicep_type([]) == "array"


def test_is_used_detects_word_boundary():
    body = "  state: logicAppState\n  location: resourceGroup().location"
    assert _is_used_in_body("logicAppState", body) is True
    assert _is_used_in_body("state", body) is True  # substring match too (Bicep uses word-level properties)
    assert _is_used_in_body("notPresent", body) is False


def test_logic_app_header_required_params_declared_without_suppress(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {"bcCustomers": "11.1"},
        "logicAppState": "Disabled",
        "storageAccount": {},
    }
    p = _write_params(tmp_path, params)
    body = "  state: logicAppState"
    header = generate_logic_app_header(body, p, "bcCustomers")
    assert "param environment string\n" in header
    assert "param projectSuffix string\n" in header
    assert "param workflowNames object\n" in header
    assert "param logicAppState string\n" in header


def test_logic_app_header_unused_params_get_suppress(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {},
        "logicAppState": "Disabled",
        "storageAccount": {},
        "secretValues": {"key": "val"},
    }
    p = _write_params(tmp_path, params)
    body = "  state: logicAppState"  # storageAccount and secretValues not referenced
    header = generate_logic_app_header(body, p, "someKey")
    assert "#disable-next-line no-unused-params\nparam storageAccount object" in header
    assert "@secure()\n#disable-next-line no-unused-params\nparam secretValues object" in header


def test_logic_app_header_var_block(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {},
        "logicAppState": "Disabled",
    }
    p = _write_params(tmp_path, params)
    header = generate_logic_app_header("", p, "bcDataHandler")
    assert "var prefix = 'la-${environment}-${projectSuffix}'" in header
    assert "var nameOfLogicApp = '${prefix}-${workflowNames.bcDataHandler}'" in header


def test_logic_app_header_unknown_key_emits_placeholder(tmp_path):
    params = {"environment": "dev", "projectSuffix": "la-", "workflowNames": {}, "logicAppState": "Disabled"}
    p = _write_params(tmp_path, params)
    header = generate_logic_app_header("", p, None)
    assert "workflowNames.UNKNOWN" in header


def test_keyvault_header_has_kv_var_block(tmp_path):
    params = {"environment": "dev", "projectSuffix": "la-", "logicAppState": "Disabled"}
    p = _write_params(tmp_path, params)
    header = generate_keyvault_header("", p)
    assert "var prefix = 'kv-${environment}'" in header
    assert "var nameOfKeyVault = '${prefix}-${uniqueString(resourceGroup().id)}'" in header


def test_object_param_with_empty_default_gets_default(tmp_path):
    params = {
        "environment": "dev",
        "projectSuffix": "la-",
        "workflowNames": {},
        "logicAppState": "Disabled",
        "storageAccount": {},
    }
    p = _write_params(tmp_path, params)
    header = generate_logic_app_header("", p, "key")
    assert "param storageAccount object = {}" in header

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from deployScript.exporter import ResourceExporter


class MockAzureClient:
    def get_resource_arm_json(self, resource_id):
        return None
    def _get_az_command(self):
        return 'az'


class MockConfigManager:
    pass


def make_exporter():
    return ResourceExporter(MockAzureClient(), MockConfigManager())


# --- _make_output_filename ---

def test_filename_storage_account():
    e = make_exporter()
    assert e._make_output_filename("Microsoft.Storage/storageAccounts", "myaccount") == "storageaccounts-myaccount"

def test_filename_keyvault():
    e = make_exporter()
    assert e._make_output_filename("Microsoft.KeyVault/vaults", "mykeyvault") == "vaults-mykeyvault"

def test_filename_preserves_resource_name_case():
    e = make_exporter()
    assert e._make_output_filename("Microsoft.Compute/virtualMachines", "MyVM") == "virtualmachines-MyVM"


# --- _sanitize_resource_for_arm ---

def test_sanitize_removes_internal_fields():
    e = make_exporter()
    raw = {
        "id": "/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sa",
        "name": "sa",
        "type": "Microsoft.Storage/storageAccounts",
        "apiVersion": "2021-09-01",
        "location": "eastus",
        "tags": {},
        "properties": {"primaryEndpoints": {}},
        "managedBy": None,
        "etag": "W/\"abc\"",
        "systemData": {"createdAt": "2021-01-01"},
        "identity": None,
        "changedTime": "2021-01-01",
        "createdTime": "2021-01-01",
    }
    result = e._sanitize_resource_for_arm(raw)
    assert "managedBy" not in result
    assert "etag" not in result
    assert "systemData" not in result
    assert "identity" not in result
    assert "changedTime" not in result
    assert "createdTime" not in result
    assert result["name"] == "sa"
    assert result["apiVersion"] == "2021-09-01"

def test_sanitize_keeps_required_fields():
    e = make_exporter()
    raw = {
        "name": "sa",
        "type": "Microsoft.Storage/storageAccounts",
        "apiVersion": "2021-09-01",
        "location": "eastus",
        "tags": {"env": "prod"},
        "properties": {"foo": "bar"},
        "sku": {"name": "Standard_LRS"},
        "kind": "StorageV2",
    }
    result = e._sanitize_resource_for_arm(raw)
    assert result["sku"] == {"name": "Standard_LRS"}
    assert result["kind"] == "StorageV2"
    assert result["tags"] == {"env": "prod"}

def test_sanitize_non_null_identity_is_kept():
    e = make_exporter()
    raw = {
        "name": "sa", "type": "T", "apiVersion": "2021", "location": "eastus",
        "identity": {"type": "SystemAssigned", "principalId": "abc"},
    }
    result = e._sanitize_resource_for_arm(raw)
    assert "identity" in result

def test_sanitize_null_identity_is_removed():
    e = make_exporter()
    raw = {
        "name": "sa", "type": "T", "apiVersion": "2021", "location": "eastus",
        "identity": None,
    }
    result = e._sanitize_resource_for_arm(raw)
    assert "identity" not in result


# --- _wrap_arm_template ---

def test_wrap_produces_valid_arm_envelope():
    e = make_exporter()
    resource = {"name": "sa", "type": "Microsoft.Storage/storageAccounts", "apiVersion": "2021-09-01", "location": "eastus"}
    result = e._wrap_arm_template(resource)
    assert result["$schema"] == "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    assert result["contentVersion"] == "1.0.0.0"
    assert result["resources"] == [resource]


import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from deployScript.workflow_mappings import WorkflowMappings


def _make_params_file(tmp_path, extra=None):
    params = {
        "environment": {"value": "dev"},
        "projectSuffix": {"value": "la-"},
        "workflowNames": {"value": {}},
        "logicAppState": {"value": "Disabled"},
    }
    if extra:
        params.update(extra)
    p = tmp_path / "parameters.local.json"
    p.write_text(json.dumps({"$schema": "...", "contentVersion": "1.0.0.0", "parameters": params}))
    return p


def test_export_uses_mapped_filename(tmp_path):
    """When a mapping exists, the output file should use mapping.filename."""
    from deployScript.exporter import ResourceExporter

    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    wm.add("GetCustomers", "bcCustomers", "11.1-GetCustomers")

    exporter = ResourceExporter(MagicMock(), MagicMock())

    resource = MagicMock()
    resource.resource_type = "Microsoft.Logic/workflows"
    resource.name = "GetCustomers"

    stem = exporter._resolve_export_stem(resource, wm)
    assert stem == "11.1-GetCustomers"


def test_export_uses_default_stem_when_no_mapping(tmp_path):
    from deployScript.exporter import ResourceExporter

    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    exporter = ResourceExporter(MagicMock(), MagicMock())

    resource = MagicMock()
    resource.resource_type = "Microsoft.Logic/workflows"
    resource.name = "GetCustomers"

    stem = exporter._resolve_export_stem(resource, wm)
    assert stem == "workflows-GetCustomers"

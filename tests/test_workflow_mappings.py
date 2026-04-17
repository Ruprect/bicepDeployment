# tests/test_workflow_mappings.py
import json
import pytest
from pathlib import Path
from deployScript.workflow_mappings import WorkflowMappings, MappingEntry


def test_load_returns_empty_when_file_missing(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    assert wm.find_by_azure_name("anything") is None


def test_load_reads_existing_file(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    p.write_text(json.dumps({
        "test-bc": {"workflowKey": "bcDataHandler", "filename": "01.0-BC"}
    }))
    wm = WorkflowMappings(p).load()
    entry = wm.find_by_azure_name("test-bc")
    assert entry == MappingEntry(azure_name="test-bc", workflow_key="bcDataHandler", filename="01.0-BC")


def test_find_by_azure_name_missing_returns_none(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    assert wm.find_by_azure_name("not-here") is None


def test_find_by_filename(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    p.write_text(json.dumps({
        "test-bc": {"workflowKey": "bcDataHandler", "filename": "01.0-BC"}
    }))
    wm = WorkflowMappings(p).load()
    entry = wm.find_by_filename("01.0-BC")
    assert entry.azure_name == "test-bc"
    assert entry.workflow_key == "bcDataHandler"


def test_find_by_filename_missing_returns_none(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    assert wm.find_by_filename("nope") is None


def test_add_and_save_round_trip(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    wm = WorkflowMappings(p).load()
    wm.add("GetCustomers", "bcCustomers", "11.1-GetCustomers")
    wm.save()

    wm2 = WorkflowMappings(p).load()
    entry = wm2.find_by_azure_name("GetCustomers")
    assert entry.workflow_key == "bcCustomers"
    assert entry.filename == "11.1-GetCustomers"


def test_add_overwrites_existing_entry(tmp_path):
    p = tmp_path / ".workflow-mappings.json"
    wm = WorkflowMappings(p).load()
    wm.add("test-bc", "oldKey", "old-file")
    wm.add("test-bc", "newKey", "new-file")
    entry = wm.find_by_azure_name("test-bc")
    assert entry.workflow_key == "newKey"
    assert entry.filename == "new-file"


def test_add_returns_mapping_entry(tmp_path):
    wm = WorkflowMappings(tmp_path / ".workflow-mappings.json").load()
    entry = wm.add("test-bc", "bcDataHandler", "01.0-BC")
    assert isinstance(entry, MappingEntry)
    assert entry.azure_name == "test-bc"

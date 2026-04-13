import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MAPPINGS_FILENAME = ".workflow-mappings.json"


@dataclass
class MappingEntry:
    azure_name: str
    workflow_key: str
    filename: str


class WorkflowMappings:
    def __init__(self, path: Path = None):
        self._path = path or Path(MAPPINGS_FILENAME)
        self._data: dict = {}

    def load(self) -> 'WorkflowMappings':
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        return self

    def save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2), encoding='utf-8')

    def find_by_azure_name(self, azure_name: str) -> Optional[MappingEntry]:
        entry = self._data.get(azure_name)
        if entry:
            return MappingEntry(
                azure_name=azure_name,
                workflow_key=entry['workflowKey'],
                filename=entry['filename'],
            )
        return None

    def find_by_filename(self, stem: str) -> Optional[MappingEntry]:
        for azure_name, entry in self._data.items():
            if entry['filename'] == stem:
                return MappingEntry(
                    azure_name=azure_name,
                    workflow_key=entry['workflowKey'],
                    filename=entry['filename'],
                )
        return None

    def add(self, azure_name: str, workflow_key: str, filename: str) -> MappingEntry:
        self._data[azure_name] = {'workflowKey': workflow_key, 'filename': filename}
        return MappingEntry(azure_name=azure_name, workflow_key=workflow_key, filename=filename)

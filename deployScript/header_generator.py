import json
import re
from pathlib import Path
from typing import Optional


def _infer_bicep_type(value) -> str:
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, list):
        return 'array'
    return 'object'


def _is_used_in_body(param_name: str, body: str) -> bool:
    return bool(re.search(rf'\b{re.escape(param_name)}\b', body))


def _load_params(parameters_file: Path) -> dict:
    """Read parameters from parameters.local.json, unwrapping the Azure format."""
    data = json.loads(parameters_file.read_text(encoding='utf-8'))
    return {k: v['value'] for k, v in data['parameters'].items()}


def _emit_param_lines(key: str, value, used: bool) -> list:
    """Return the lines (as strings) to emit for one parameter declaration."""
    btype = _infer_bicep_type(value)
    default = ' = {}' if (btype == 'object' and value == {}) else ''
    lines = []
    if key == 'secretValues':
        lines.append('@secure()')
    if not used:
        lines.append('#disable-next-line no-unused-params')
    lines.append(f'param {key} {btype}{default}')
    return lines


def generate_logic_app_header(
    body: str,
    parameters_file: Path,
    workflow_key: Optional[str],
) -> str:
    """
    Generate the standard Logic App bicep header from parameters.local.json.

    Required params (environment, projectSuffix, workflowNames, logicAppState) are
    always declared without suppress regardless of body usage.
    All other params follow usage detection.
    """
    params = _load_params(parameters_file)
    required = {'environment', 'projectSuffix', 'workflowNames', 'logicAppState'}
    lines = []

    # Required params first, in fixed order
    for key in ['environment', 'projectSuffix', 'workflowNames', 'logicAppState']:
        if key not in params:
            continue
        lines.extend(_emit_param_lines(key, params[key], used=True))

    lines.append('')

    # Remaining params, usage-detected
    for key, value in params.items():
        if key in required:
            continue
        used = _is_used_in_body(key, body)
        lines.extend(_emit_param_lines(key, value, used=used))

    # Var block
    lines.append('')
    lines.append("var prefix = 'la-${environment}-${projectSuffix}'")
    wkey = workflow_key if workflow_key else 'UNKNOWN'
    lines.append(f"var nameOfLogicApp = '${{prefix}}-${{workflowNames.{wkey}}}'")
    lines.append('')

    return '\n'.join(lines)


def generate_keyvault_header(body: str, parameters_file: Path) -> str:
    """
    Generate the standard Key Vault bicep header from parameters.local.json.

    Only 'environment' is declared without suppress. All others follow usage detection.
    """
    params = _load_params(parameters_file)
    required = {'environment'}
    lines = []

    if 'environment' in params:
        lines.extend(_emit_param_lines('environment', params['environment'], used=True))

    lines.append('')

    for key, value in params.items():
        if key in required:
            continue
        used = _is_used_in_body(key, body)
        lines.extend(_emit_param_lines(key, value, used=used))

    lines.append('')
    lines.append("// Limitation of Key Vault name to 24 characters")
    lines.append("var prefix = 'kv-${environment}'")
    lines.append("var nameOfKeyVault = '${prefix}-${uniqueString(resourceGroup().id)}'")
    lines.append('')

    return '\n'.join(lines)

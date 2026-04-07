# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository serves two purposes:

1. **Deployment Orchestration Framework**: A universal tool for deploying Azure Bicep templates via an interactive Python CLI. A Windows WPF GUI and VS Code extension also exist but are currently WIP.

2. **Azure IaC Templates**: Bicep templates for deploying Logic Apps that integrate Microsoft Dynamics 365 Business Central with Microsoft Dataverse, handling data synchronization for customer data, tanks, configuration templates, and other business entities.

## Architecture

### Deployment Tool — Python CLI Module Structure (`deployScript/`)

| Module | Responsibility |
|--------|---------------|
| `main.py` | Entry point, main loop, input handling |
| `menu.py` | Color-coded interactive UI, key input handling |
| `config.py` | Settings persistence, `.deployment-settings.json` management |
| `bicep_manager.py` | Template discovery, SHA256 change detection, status tracking |
| `deployment.py` | Deployment and validation orchestration |
| `azure_client.py` | Azure CLI detection, authentication, `az` command execution |
| `logger.py` | Dual console+file logging, spinner progress, ANSI colors |

> **WIP**: A Windows WPF GUI (`WPF/`) and VS Code extension (`vscode-extension/`) are in development but not yet complete.

### Bicep Template Components

1. **Connection Templates** (`00.0.connections.bicep`): Defines API connections to Business Central, Dataverse, and Azure Blob Storage
2. **Storage Infrastructure** (`00.1.StorageAccount.bicep`): Azure Storage Account with managed identity blob connections
3. **Helper Logic Apps** (`01.*.Helper.*.bicep`): Error handling, notifications, and utility workflows
4. **OrderPlanner Integration** (`02.*-OrderPlanner*.bicep`): OrderPlanner system integration for order management and shipment tracking
5. **External Integration** (`03.0-LogisticsTracker.bicep`): LogisticsTracker system integration using managed identity for blob storage
6. **Main Data Handler** (`11.0-BCDataHandler.bicep`): Core business logic for data synchronization
7. **Country-Specific Templates** (`11.*_byCountry.bicep`): Entity-specific workflows for multi-tenant scenarios

### Data Flow

- Business Central webhook triggers → Logic Apps → Dataverse updates
- OrderPlanner system integration via blob storage triggers → Business Central API updates
- Supports multi-tenant scenarios (Norway/Sweden with different company IDs)
- Handles various entity types: customers, tanks, NACE codes, salespersons, frame agreements, tank agreements, order management

## Common Development Commands

### Deployment

```bash
# Using submodule or cloned repo
python bicepDeployment/deploy.py

# If deployment scripts are copied locally
python deploy.py

# Legacy PowerShell launcher (calls deploy.py)
.\deploy.ps1
```

### Interactive Menu Options

- **Number (1-N)**: Deploy individual template
- **Range/List**: Deploy a subset — e.g. `1-3`, `1,3,5`, `1-3,5,10-15`
- **A**: Deploy all enabled templates
- **V**: Toggle validation mode (All / Changed / Skip)
- **O**: Reorder templates and enable/disable them
- **P**: Select parameter file
- **R**: Refresh file list to detect new templates
- **C**: Configure Azure CLI settings and authentication
- **Q**: Quit

### What the Deployment System Does Automatically

- **Discovers** all `.bicep` files in the current directory
- **Detects changes** using SHA256 file hashing (falls back to modification timestamp)
- **Prompts** before deploying an unchanged template (with "always skip/deploy" options)
- **Maintains** deployment order and enabled/disabled state in `.deployment-settings.json`
- **Validates** Azure CLI availability and authentication
- **Prevents** deployment of empty (0 KB) files
- **Generates** timestamped deployment names for Azure portal tracking
- **Generates** comprehensive deployment logs in `logs/`
- **Tracks** both deployment history and validation history per template

### Direct Azure CLI Commands

```bash
# Validate
az deployment group validate --resource-group <rg> --template-file <file> --parameters @parameters.local.json

# Deploy (Incremental)
az deployment group create --resource-group <rg> --template-file <file> --parameters @parameters.local.json

# Deploy (Complete — removes resources not in template)
az deployment group create --resource-group <rg> --template-file <file> --mode Complete --parameters @parameters.local.json
```

## Configuration

### Deployment Settings (`.deployment-settings.json`)

Auto-created on first run. Shared across all interfaces.

```json
{
  "SelectedParameterFile": "parameters.local.json",
  "LastUpdated": "2025-09-05 09:29:07",
  "FileOrder": [
    {
      "FileName": "00.0.connections.bicep",
      "Enabled": true,
      "LastDeploymentSuccess": true,
      "LastDeployment": "2025-09-05 09:29:07",
      "LastFileHash": "<sha256>",
      "LastDeploymentError": null,
      "LastValidationSuccess": true,
      "LastValidation": "2025-09-05 09:28:45",
      "LastValidationError": null
    }
  ],
  "Configuration": {
    "ResourceGroup": "my-resource-group",
    "Subscription": "subscription-id",
    "DesiredTenant": "tenant-id",
    "ConsoleWidth": 75,
    "ValidationMode": "All"
  }
}
```

### Validation Modes

| Mode | Behaviour |
|------|-----------|
| **All** | Validate all templates before every deployment |
| **Changed** | Only validate templates modified since last deployment |
| **Skip** | Deploy without any pre-flight validation |

### Bicep Parameters (`parameters.local.json`)

Key parameters:

- `dataverse.clientSecret`: Client secret for Dataverse authentication
- `dataverse.clientId`: Client ID for Dataverse connection
- `dataverse.uri`: Dataverse environment URI
- `businessCentral.environmentName`: BC environment name (default: `CRONUS_NO_DEV`)
- `businessCentral.countries`: Array containing Norway and Sweden configurations with company IDs and system reference GUIDs
- `storageAccount`: Blob storage paths and container names (includes `orderPlannerPath` for order processing)
- `workflowNames`: Centralized Logic App naming convention

### Template Naming Convention

- `la-{environment}-bc-{workflow-name}` for Logic Apps
- Environment defaults to `test`

### Connection Configuration

The system uses three main connection types:

- `dynamicssmbsaas`: Business Central connector
- `commondataservice`: Dataverse connector
- `azureblob`: Azure Blob Storage connector (configured with managed identity for LogisticsTracker)

## Key Development Patterns

### Error Handling

All Logic Apps implement a Try-Catch-Finally pattern:

- **Try**: Main business logic
- **Catch**: Error handling with helper workflow calls
- **Finally**: Response handling and termination

### Data Synchronization

Logic Apps check for existing records in Dataverse before upserting to avoid unnecessary updates. They compare source data with existing Dataverse data and only proceed if changes are detected.

### Multi-Tenant Support

The system handles different company IDs and system references for Norway and Sweden markets through parameterized configurations.

## File Organization

### Deployment Logs

All deployment logs are automatically stored in the `logs/` folder:

- `logs/deployment-YYYY-MM-DD_HH-mm-ss.log`: Timestamped deployment logs
- `logs/deployment-latest.log`: Most recent deployment log
- `logs/azure-cli-debug.log`: Azure CLI detection debug log

### Development Artifacts

Each type of temporary artifact has its own dedicated dot-folder — all excluded from git:

| Folder | Purpose |
|--------|---------|
| `.claude/` | Claude Code settings only (`settings.local.json`) |
| `.backup/` | Backup copies of modified files (`.backup`, `.bak` extensions) |
| `.drafts/` | Work-in-progress Bicep templates not yet ready for the main directory |
| `.scripts/` | Temporary or one-off scripts (PowerShell, bash) used during development |
| `.notes/` | Session summaries, fix documentation, and debug notes generated by Claude |

## Testing

Test Logic Apps using the Azure portal's Logic App Designer or by triggering webhooks from Business Central in the appropriate environment.

## Template Dependencies and Deployment Order

The deployment script automatically manages template dependencies:

1. **Connections first**: `00.0.connections.bicep` must be deployed before other templates
2. **Storage infrastructure**: `00.1.StorageAccount.bicep` creates storage and blob connections
3. **Helper workflows**: `01.*.Helper.*.bicep` provide shared utilities
4. **OrderPlanner integrations**: `02.*-OrderPlanner*.bicep` handle order management and shipment tracking
5. **External integrations**: `03.*LogisticsTracker*.bicep` handle external system connectivity
6. **Data handlers**: `11.*` templates handle Business Central to Dataverse synchronization

### Managed Identity Configuration

The LogisticsTracker Logic App uses system-assigned managed identity for Azure Blob Storage access. The storage account connection is configured without authentication parameters to enable managed identity.

## Prerequisites

- **Azure CLI** installed and configured (`az login` required)
- **Python 3.x** for the CLI deployment tool (`pip install colorama` optional, for Windows color support)
- **PowerShell 5.1+** for legacy deployment scripts
- Access to Business Central and Dataverse environments
- Valid service principals and connection credentials in `parameters.local.json`

## Important Notes

- All Logic Apps default to 'Disabled' state for safety — must be manually enabled after deployment
- Complete deployment mode removes Azure resources not defined in the template — use with caution
- Empty (0 KB) template files are automatically disabled and cannot be deployed
- Service account modifications are ignored to prevent circular updates
- SHA256 hashing is used to detect file changes — the tool will prompt before re-deploying an unchanged template
- Deployment logs provide detailed timing and success/failure information for troubleshooting
- Always test deployments in development environment before production
- `deploy.ps1-old` in the root is the legacy full-PowerShell implementation, kept for reference only

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains Azure infrastructure as code (IaC) templates using Bicep for deploying Logic Apps that integrate Microsoft Dynamics 365 Business Central with Microsoft Dataverse. The system handles data synchronization between these platforms for customer data, tanks, configuration templates, and other business entities.

## Architecture

### Core Components

1. **Connection Templates** (`00.0.connections.bicep`): Defines API connections to Business Central, Dataverse, and Azure Blob Storage
2. **Storage Infrastructure** (`00.1.StorageAccount.bicep`): Azure Storage Account with managed identity blob connections
3. **Helper Logic Apps** (`01.*.Helper.*.bicep`): Error handling, notifications, and utility workflows
4. **Bottomline Integration** (`02.*-Bottomline*.bicep`): Bottomline system integration for order management and shipment tracking
5. **External Integration** (`03.0-AccellaHandler.bicep`): Accella system integration using managed identity for blob storage
6. **Main Data Handler** (`11.0-BCDataHandler.bicep`): Core business logic for data synchronization
7. **Country-Specific Templates** (`11.*_byCountry.bicep`): Entity-specific workflows for multi-tenant scenarios

### Data Flow

- Business Central webhook triggers → Logic Apps → Dataverse updates
- Bottomline system integration via blob storage triggers → Business Central API updates
- Supports multi-tenant scenarios (Norway/Sweden with different company IDs)
- Handles various entity types: customers, tanks, NACE codes, salespersons, frame agreements, tank agreements, order management

## Common Development Commands

### Deployment

This project uses the universal Bicep deployment scripts from the [bicepDeployment](https://github.com/Ruprect/bicepDeployment) repository.

#### Setup (First Time)
```bash
# Method 1: Git submodule (recommended)
git submodule add https://github.com/Ruprect/bicepDeployment.git

# Method 2: Clone separately
git clone https://github.com/Ruprect/bicepDeployment.git
```

#### Deploy Templates
```bash
# Using submodule or cloned repo
python bicepDeployment/deploy.py

# If deployment scripts are copied locally
python deploy.py

# Legacy PowerShell (guides to Python setup)
.\deploy.ps1
```

The deployment script provides an enhanced interactive menu:

- **Number selection (1-N)**: Deploy individual templates 
- **A**: Deploy all enabled templates with validation mode integration
- **V**: Toggle validation modes (All/Changed/Skip)
- **O**: Reorder templates and enable/disable them for deployment
- **P**: Select parameter file (`parameters.local.json` or others)
- **R**: Refresh file list to detect new templates
- **C**: Configure Azure CLI settings and authentication
- **Q**: Quit

The deployment system automatically:

- **Discovers** all `.bicep` files in the current directory
- **Maintains** deployment order and enabled/disabled state in `.deployment-settings.json`
- **Validates** Azure CLI availability and authentication
- **Prevents** deployment of empty (0 KB) files
- **Supports** validation modes and timestamped deployment names
- **Generates** comprehensive deployment logs in `logs/` folder with professional output
- **Tracks** deployment history and change detection

### Direct Azure CLI Commands

Validate Bicep templates:

```bash
az deployment group validate --resource-group <resource-group> --template-file <template-file> --parameters @parameters.local.json
```

Deploy specific template:

```bash
az deployment group create --resource-group <resource-group> --template-file <template-file> --parameters @parameters.local.json
```

Deploy with Complete mode (removes resources not in template):

```bash
az deployment group create --resource-group <resource-group> --template-file <template-file> --mode Complete --parameters @parameters.local.json
```

## Configuration

### Parameters

Key parameters are defined in `parameters.local.json`:

- `dataverse.clientSecret`: Client secret for Dataverse authentication
- `dataverse.clientId`: Client ID for Dataverse connection (default: 49df27b2-3d6e-4e4b-9e55-d55ef9a433e9)
- `dataverse.uri`: Dataverse environment URI
- `businessCentral.environmentName`: BC environment name (default: FLOGAS_NO_DEV)
- `businessCentral.countries`: Array containing Norway and Sweden configurations with company IDs and system reference GUIDs
- `storageAccount`: Configuration for blob storage paths and container names (includes bottomlinePath for order processing)
- `workflowNames`: Centralized Logic App naming convention for consistent resource naming
- Environment-specific values are parameterized in individual Bicep files

### Template Naming Convention

- `la-{environment}-bc-{workflow-name}` for Logic Apps
- Environment defaults to 'test'
- Workflow names correspond to business functions

### Connection Configuration

The system uses three main connection types:

- `dynamicssmbsaas`: Business Central connector
- `commondataservice`: Dataverse connector
- `azureblob`: Azure Blob Storage connector (configured with managed identity for AccellaHandler)

## Key Development Patterns

### Error Handling

All Logic Apps implement a Try-Catch-Finally pattern:

- Try: Main business logic
- Catch: Error handling with helper workflow calls
- Finally: Response handling and termination

### Data Synchronization

Logic Apps check for existing records in Dataverse before upserting to avoid unnecessary updates. They compare source data with existing Dataverse data and only proceed if changes are detected.

### Multi-Tenant Support

The system handles different company IDs and system references for Norway and Sweden markets through parameterized configurations.

## File Organization

### Deployment Logs

All deployment logs are automatically stored in the `logs/` folder:

- `logs/deployment-YYYY-MM-DD_HH-mm-ss.log`: Timestamped deployment logs
- `logs/deployment-latest.log`: Most recent deployment log

### Development Artifacts

Temporary scripts and development files are stored in `.claude/` folder and excluded from git.

## Testing

Test Logic Apps using the Azure portal's Logic App Designer or by triggering webhooks from Business Central in the appropriate environment.

## Template Dependencies and Deployment Order

The deployment script automatically manages template dependencies:

1. **Connections first**: `00.0.connections.bicep` must be deployed before other templates
2. **Storage infrastructure**: `00.1.StorageAccount.bicep` creates storage and blob connections
3. **Helper workflows**: `01.*.Helper.*.bicep` provide shared utilities
4. **Bottomline integrations**: `02.*-Bottomline*.bicep` handle order management and shipment tracking
5. **External integrations**: `03.*AccellaHandler*.bicep` handle external system connectivity
6. **Data handlers**: `11.*` templates handle Business Central to Dataverse synchronization

### Managed Identity Configuration

The AccellaHandler Logic App uses system-assigned managed identity for Azure Blob Storage access. The storage account connection is configured without authentication parameters to enable managed identity.

## Prerequisites

- Azure CLI installed and configured (`az login` required)
- PowerShell 5.1 or later for deployment scripts
- Access to Business Central and Dataverse environments
- Valid service principals and connection credentials configured in `parameters.local.json`

## Important Notes

- All Logic Apps default to 'Disabled' state for safety - must be manually enabled after deployment
- The deployment script handles different Azure CLI commands for different template types
- Complete deployment mode is only available for the first template in deployment order
- Empty (0 KB) template files are automatically disabled and cannot be deployed
- Service account modifications are ignored to prevent circular updates
- Deployment logs provide detailed timing and success/failure information for troubleshooting
- Always test deployments in development environment before production

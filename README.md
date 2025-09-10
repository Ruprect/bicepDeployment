# Bicep Deployment Scripts

A comprehensive deployment tool for Azure Bicep templates with interactive menu system, validation, and advanced deployment features.

## Overview

This repository contains deployment scripts that can be used with any Bicep template project. The scripts provide an interactive deployment experience with features like template ordering, validation modes, deployment history tracking, and comprehensive logging.

## Features

### 🚀 Interactive Deployment
- **Menu-driven interface** with color-coded options
- **Template discovery** - automatically finds all `.bicep` files
- **Individual or batch deployment** with progress tracking
- **Real-time deployment status** with spinners and progress indicators

### 📋 Template Management
- **Enable/disable templates** for selective deployment
- **Template reordering** with dependency management
- **Deployment history tracking** with success/failure status
- **File change detection** to avoid unnecessary deployments

### ✅ Validation Modes
- **All**: Validate all enabled templates before deployment
- **Changed**: Only validate templates that have changed
- **Skip**: Deploy without validation for faster deployment

### 🔧 Advanced Features
- **Timestamped deployment names** for better Azure Portal tracking
- **Multiple deployment modes** (Incremental/Complete)
- **Parameter file selection** with validation
- **Comprehensive logging** with deployment history
- **Azure CLI integration** with authentication support

## Quick Start

### Prerequisites
- **Python 3.7+** (for Python deployment script)
- **PowerShell 5.1+** (for PowerShell deployment script) 
- **Azure CLI** installed and configured
- Valid **Azure subscription** with deployment permissions

### Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/Ruprect/bicepDeployment.git
   cd bicepDeployment
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Copy to your Bicep project:**
   ```bash
   # Copy deployment scripts to your Bicep template project
   cp -r deployScript /path/to/your/bicep/project/
   cp deploy.py /path/to/your/bicep/project/
   cp deploy.ps1 /path/to/your/bicep/project/
   ```

## Usage

### Python Deployment Script (Recommended)

Navigate to your Bicep template directory and run:

```bash
python deploy.py
```

**Interactive Menu:**
```
======================================================================================================================================================
1-25 Deploy template | [A] Deploy all ([V]alidate All) | [O] Reorder | [P] Parameters | [R] Refresh | [C] Config | [Q] Quit
======================================================================================================================================================
```

### PowerShell Deployment Script

For traditional PowerShell users:

```powershell
.\deploy.ps1-old [-ResourceGroup "YourResourceGroup"]
```

## Key Features Explained

### Validation Mode Toggle
Press **V** to cycle through validation modes:
- **🟢 Validate All**: Validates all templates before deployment
- **🟡 Validate Changed**: Only validates templates that have changed since last deployment  
- **🔴 Skip Validation**: Deploys without validation for maximum speed

### Template Management
- **Numbers (1-N)**: Deploy individual templates
- **[A] Deploy All**: Deploy all enabled templates in sequence
- **[O] Reorder**: Enable/disable templates and change deployment order
- **[P] Parameters**: Select different parameter files
- **[R] Refresh**: Rescan directory for new templates

### Deployment Output
Clean, professional deployment output:
```
🚀 Deploying bicep templates as Incremental, only validating changed templates.

▶ Template 1/24: 00.0.connections.bicep
  [Spinner] (34.49s)
  ✅ Successfully deployed 00.0.connections.bicep

▶ Template 2/24: 00.1.StorageAccount.bicep  
  ⏭️ Skipped 00.1.StorageAccount.bicep (unchanged)
```

## Configuration

### Parameter Files
The script automatically looks for parameter files in your project:
- `parameters.local.json` (default)
- `parameters.*.json` (selectable)

### Deployment Settings
Settings are automatically saved to `.deployment-settings.json`:
- Template order and enabled/disabled state
- Deployment history and timestamps
- Validation mode preferences
- Azure configuration

### Azure Configuration
Configure Azure CLI access through the **[C] Config** option:
- Account and subscription management
- Resource group configuration  
- Tenant selection
- Authentication validation

## File Structure

```
bicepDeployment/
├── deployScript/           # Python deployment engine
│   ├── __init__.py
│   ├── azure_client.py     # Azure CLI integration
│   ├── bicep_manager.py    # Template management
│   ├── config.py           # Configuration management
│   ├── deployment.py       # Core deployment logic
│   ├── logger.py           # Logging and output
│   ├── main.py             # Main application entry
│   └── menu.py             # Interactive menu system
├── deploy.py               # Python entry point
├── deploy.ps1              # Simple Python launcher
├── deploy.ps1-old          # Full PowerShell version
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Integration with Your Project

### Method 1: Git Submodule (Recommended)
Add this repository as a submodule to your Bicep project:

```bash
cd your-bicep-project
git submodule add https://github.com/Ruprect/bicepDeployment.git deployment
cd deployment
ln -s deployment/deploy.py deploy.py
```

### Method 2: Copy Files
Copy the deployment scripts directly to your project:

```bash
# Copy to your Bicep project root
cp -r bicepDeployment/deployScript your-project/
cp bicepDeployment/deploy.py your-project/
cp bicepDeployment/requirements.txt your-project/
```

### Method 3: Global Installation
Install as a global tool (requires PATH configuration):

```bash
# Clone to a tools directory
git clone https://github.com/Ruprect/bicepDeployment.git ~/tools/bicepDeployment

# Add to PATH in your shell profile
echo 'export PATH="$PATH:~/tools/bicepDeployment"' >> ~/.bashrc
```

## Development

### Contributing
1. Fork this repository
2. Create a feature branch
3. Make your changes
4. Test with sample Bicep templates
5. Submit a pull request

### Testing
Test the deployment scripts with sample templates:

```bash
# Create test templates
mkdir test-project && cd test-project
echo "param environment string" > test.bicep
echo '{"$schema":"...","parameters":{"environment":{"value":"test"}}}' > parameters.local.json

# Test deployment
python ../bicepDeployment/deploy.py
```

### Architecture
The deployment system follows a modular architecture:
- **`main.py`**: Application entry point and main loop
- **`menu.py`**: Interactive UI and menu system  
- **`azure_client.py`**: Azure CLI wrapper and authentication
- **`bicep_manager.py`**: Template discovery and management
- **`deployment.py`**: Core deployment logic and validation
- **`config.py`**: Configuration and settings persistence
- **`logger.py`**: Structured logging and output formatting

## Troubleshooting

### Common Issues

**Azure CLI not found:**
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login
```

**Permission errors:**
- Ensure you have Contributor or Owner role on the resource group
- Check Azure AD permissions for service principals
- Verify subscription access

**Template validation failures:**
- Check parameter file syntax and values
- Verify all required parameters are provided
- Ensure Bicep syntax is valid

### Logging
Deployment logs are automatically saved to:
- `logs/deployment-YYYY-MM-DD_HH-mm-ss.log` (timestamped)
- `logs/deployment-latest.log` (latest deployment)

### Debug Mode
Enable verbose logging by setting environment variable:
```bash
export BICEP_DEPLOY_DEBUG=1
python deploy.py
```

## Support

For issues and questions:
1. Check the [Issues](https://github.com/Ruprect/bicepDeployment/issues) section
2. Review deployment logs in the `logs/` folder
3. Validate Azure CLI configuration with `az account show`
4. Test with simple Bicep templates first

## License

This project is open source. Feel free to use, modify, and distribute according to your needs.

## Changelog

### Latest Version
- ✨ Timestamped deployment names for better tracking
- 🎨 Enhanced UI with validation mode toggle
- 🚀 Improved deployment output with progress indicators
- 🔧 Better error handling and validation feedback
- 📊 Comprehensive deployment history tracking
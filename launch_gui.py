"""
Launch the Bicep Deploy GUI from any project directory.
Usage: python d:/repos/bicepDeployment/launch_gui.py
"""
import sys
from pathlib import Path

# Ensure the bicepDeployment package root is importable
sys.path.insert(0, str(Path(__file__).parent))

from gui import main
main()

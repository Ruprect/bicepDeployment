"""Logging utilities for the deployment script."""

import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    CONFIG = "CONFIG"
    START = "START"


class Color:
    WHITE = '\033[97m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    RESET = '\033[0m'


class DeploymentLogger:
    def __init__(self):
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.log_file = self.logs_dir / f"deployment-{timestamp}.log"
        self.latest_log_file = self.logs_dir / "deployment-latest.log"
        
        self._spinner_active = False
        self._spinner_thread = None
        
    def start_deployment_log(self, resource_group: str) -> None:
        """Initialize deployment logging."""
        log_header = f"""=== BICEP DEPLOYMENT LOG ===
Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Resource Group: {resource_group}
Script Version: 3.0 (Python)
============================

"""
        
        # Write to both log files
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(log_header)
        with open(self.latest_log_file, 'w', encoding='utf-8') as f:
            f.write(log_header)
            
        self.log("Deployment logging started", LogLevel.START, Color.GREEN)
        self.log(f"Log file: {self.log_file}", LogLevel.INFO, Color.GRAY)
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO, color: str = Color.WHITE) -> None:
        """Write log message to console and files."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level.value}] {message}"
        
        # Write to console with color (Windows compatible)
        if os.name == 'nt':  # Windows
            # Use colorama if available, otherwise plain text
            try:
                import colorama
                colorama.init()
                print(f"{color}{message}{Color.RESET}")
            except ImportError:
                print(message)
        else:
            print(f"{color}{message}{Color.RESET}")
        
        # Write to log files
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
        with open(self.latest_log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    
    def show_progress_spinner(self, message: str, target_function, *args, **kwargs):
        """Show a progress spinner while executing a function."""
        spinner_chars = ['|', '/', '-', '\\']
        spinner_index = 0
        start_time = time.time()
        result = None
        exception = None
        
        def run_target():
            nonlocal result, exception
            try:
                result = target_function(*args, **kwargs)
            except Exception as e:
                exception = e
        
        # Start the target function in a thread
        thread = threading.Thread(target=run_target)
        thread.daemon = True
        thread.start()
        
        # Show spinner while thread is running
        while thread.is_alive():
            elapsed = int(time.time() - start_time)
            spinner = spinner_chars[spinner_index % len(spinner_chars)]
            
            # Clear the current line and write the spinner with timer
            sys.stdout.write(f'\r{message} {spinner} ({elapsed}s)')
            sys.stdout.flush()
            
            time.sleep(0.2)
            spinner_index += 1
        
        # Wait for thread to complete
        thread.join()
        
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * (len(message) + 20) + '\r')
        sys.stdout.flush()
        
        # Show completion message
        final_elapsed = round(time.time() - start_time, 2)
        if exception:
            self.log(f"{message} failed ({final_elapsed}s)", LogLevel.ERROR, Color.RED)
            raise exception
        else:
            self.log(f"{message} completed ({final_elapsed}s)", LogLevel.SUCCESS, Color.GREEN)
            return result


# Global logger instance
logger = DeploymentLogger()
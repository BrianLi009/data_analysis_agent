# -*- coding: utf-8 -*-
"""
Safe code executor, based on IPython providing code execution functionality in notebook environment
"""

import os
import sys
import ast
import traceback
import io
from typing import Dict, Any, List, Optional, Tuple
from contextlib import redirect_stdout, redirect_stderr
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

class CodeExecutor:
    """
    Safe code executor that restricts dependency libraries, captures output, supports image saving and path output
    """   
    ALLOWED_IMPORTS = {
        'pandas', 'pd',
        'numpy', 'np', 
        'matplotlib', 'matplotlib.pyplot', 'plt',
        'duckdb', 'scipy', 'sklearn',
        'plotly', 'dash', 'requests', 'urllib',
        'os', 'sys', 'json', 'csv', 'datetime', 'time',
        'math', 'statistics', 're', 'pathlib', 'io',
        'collections', 'itertools', 'functools', 'operator',
        'warnings', 'logging', 'copy', 'pickle', 'gzip', 'zipfile',
        'typing', 'dataclasses', 'enum', 'sqlite3'
    }
    
    def __init__(self, output_dir: str = "outputs"):
        """
        Initialize code executor
        
        Args:
            output_dir: Output directory for saving images and files
        """
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize IPython shell
        self.shell = InteractiveShell.instance()
        
        # Setup Chinese font
        self._setup_chinese_font()
        
        # Pre-import common libraries
        self._setup_common_imports()
        
        # Image counter
        self.image_counter = 0
        
    def _setup_chinese_font(self):
        """Setup matplotlib Chinese font display"""
        try:
            # Set matplotlib to use Agg backend to avoid GUI issues
            matplotlib.use('Agg')
            
            # Set matplotlib to use SimHei font for Chinese display
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
              # Also set in shell
            self.shell.run_cell("""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
""")
        except Exception as e:
            print(f"Failed to setup Chinese font: {e}")
            
    def _setup_common_imports(self):
        """Pre-import common libraries"""
        common_imports = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import duckdb
import os
import json
from IPython.display import display
"""
        try:
            self.shell.run_cell(common_imports)
            # Ensure display function is available in shell's user namespace
            from IPython.display import display
            self.shell.user_ns['display'] = display
        except Exception as e:
            print(f"Failed to pre-import libraries: {e}")
    
    def _check_code_safety(self, code: str) -> Tuple[bool, str]:
        """
        Check code safety, restrict imported libraries
        
        Returns:
            (is_safe, error_message)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self.ALLOWED_IMPORTS:
                        return False, f"Disallowed import: {alias.name}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module not in self.ALLOWED_IMPORTS:
                    return False, f"Disallowed import: {node.module}"
            
            # Check for dangerous function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['exec', 'eval', 'open', '__import__']:
                        return False, f"Disallowed function call: {node.func.id}"
        
        return True, ""
    
    def get_current_figures_info(self) -> List[Dict[str, Any]]:
        """Get current matplotlib figure information, but don't auto-save"""
        figures_info = []
        
        # Get all current figures
        fig_nums = plt.get_fignums()
        
        for fig_num in fig_nums:
            fig = plt.figure(fig_num)
            if fig.get_axes():  # Only process figures with content
                figures_info.append({
                    'figure_number': fig_num,
                    'axes_count': len(fig.get_axes()),
                    'figure_size': fig.get_size_inches().tolist(),
                    'has_content': True
                })
        
        return figures_info
    
    def _format_table_output(self, obj: Any) -> str:
        """Format table output, limit number of rows"""
        if hasattr(obj, 'shape') and hasattr(obj, 'head'):  # pandas DataFrame
            rows, cols = obj.shape
            print(f"\nData table shape: {rows} rows x {cols} columns")
            print(f"Column names: {list(obj.columns)}")
            
            if rows <= 15:
                return str(obj)
            else:
                head_part = obj.head(5)
                tail_part = obj.tail(5)
                return f"{head_part}\n...\n(omitted {rows-10} rows)\n...\n{tail_part}"
        
        return str(obj)
    
    def execute_code(self, code: str) -> Dict[str, Any]:
        """
        Execute code and return results
        
        Args:
            code: Python code to execute
            
        Returns:
            {
                'success': bool,
                'output': str,
                'error': str,
                'variables': Dict[str, Any]  # Newly generated important variables
            }
        """
        # Check code safety
        is_safe, safety_error = self._check_code_safety(code)
        if not is_safe:
            return {
                'success': False,
                'output': '',
                'error': f"Code safety check failed: {safety_error}",
                'variables': {}
            }
        
        # Record variables before execution
        vars_before = set(self.shell.user_ns.keys())
        
        try:
            # Use IPython's capture_output to capture all output
            with capture_output() as captured:
                result = self.shell.run_cell(code)
            
            # Check execution results
            if result.error_before_exec:
                error_msg = str(result.error_before_exec)
                return {
                    'success': False,
                    'output': captured.stdout,
                    'error': f"Error before execution: {error_msg}",
                    'variables': {}
                }
            
            if result.error_in_exec:
                error_msg = str(result.error_in_exec)
                return {
                    'success': False,
                    'output': captured.stdout,
                    'error': f"Execution error: {error_msg}",
                    'variables': {}
                }
            
            # Get output
            output = captured.stdout
            
            # If there's a return value, add it to output
            if result.result is not None:
                formatted_result = self._format_table_output(result.result)
                output += f"\n{formatted_result}"
              # Record newly generated important variables (simplified version)
            vars_after = set(self.shell.user_ns.keys())
            new_vars = vars_after - vars_before
            
            # Only record newly created important data structures like DataFrames
            important_new_vars = {}
            for var_name in new_vars:
                if not var_name.startswith('_'):
                    try:
                        var_value = self.shell.user_ns[var_name]
                        if hasattr(var_value, 'shape'):  # pandas DataFrame, numpy array
                            important_new_vars[var_name] = f"{type(var_value).__name__} with shape {var_value.shape}"
                        elif var_name in ['session_output_dir']:  # Important configuration variables
                            important_new_vars[var_name] = str(var_value)
                    except:
                        pass
            
            return {
                'success': True,
                'output': output,                'error': '',
                'variables': important_new_vars
            }
        except Exception as e:
            return {
                'success': False,
                'output': captured.stdout if 'captured' in locals() else '',
                'error': f"Execution exception: {str(e)}\n{traceback.format_exc()}",
                'variables': {}
            }    
    
    def reset_environment(self):
        """Reset execution environment"""
        self.shell.reset()
        self._setup_common_imports()
        self._setup_chinese_font()
        plt.close('all')
        self.image_counter = 0
    
    def set_variable(self, name: str, value: Any):
        """Set variable in execution environment"""
        self.shell.user_ns[name] = value
    
    def get_environment_info(self) -> str:
        """Get current execution environment variable information for system prompts"""
        info_parts = []
        
        # Get important data variables
        important_vars = {}
        for var_name, var_value in self.shell.user_ns.items():
            if not var_name.startswith('_') and var_name not in ['In', 'Out', 'get_ipython', 'exit', 'quit']:
                try:
                    if hasattr(var_value, 'shape'):  # pandas DataFrame, numpy array
                        important_vars[var_name] = f"{type(var_value).__name__} with shape {var_value.shape}"
                    elif var_name in ['session_output_dir']:  # Important path variables
                        important_vars[var_name] = str(var_value)
                    elif isinstance(var_value, (int, float, str, bool)) and len(str(var_value)) < 100:
                        important_vars[var_name] = f"{type(var_value).__name__}: {var_value}"
                    elif hasattr(var_value, '__module__') and var_value.__module__ in ['pandas', 'numpy', 'matplotlib.pyplot']:
                        important_vars[var_name] = f"Imported module: {var_value.__module__}"
                except:
                    continue
        
        if important_vars:
            info_parts.append("Current environment variables:")
            for var_name, var_info in important_vars.items():
                info_parts.append(f"- {var_name}: {var_info}")
        else:
            info_parts.append("Current environment has pre-installed pandas, numpy, matplotlib and other libraries")
        
        # Add output directory information
        if 'session_output_dir' in self.shell.user_ns:
            info_parts.append(f"Image save directory: session_output_dir = '{self.shell.user_ns['session_output_dir']}'")
        
        return "\n".join(info_parts)

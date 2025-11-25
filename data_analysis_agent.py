# -*- coding: utf-8 -*-
"""
Simplified Notebook Data Analysis Agent
Contains only user and assistant roles. Key constraints:
2. Images must be saved to the specified session directory, output absolute paths, plt.show() is prohibited
3. Table output control: if more than 15 rows, only show first 5 and last 5 rows
4. Force use of SimHei font: plt.rcParams['font.sans-serif'] = ['SimHei']
5. Output format strictly uses YAML for shared context single-turn conversation mode
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional
from utils.create_session_dir import create_session_output_dir
from utils.format_execution_result import format_execution_result
from utils.extract_code import extract_code_from_response
from utils.llm_helper import LLMHelper
from utils.code_executor import CodeExecutor
from config.llm_config import LLMConfig
from prompts import data_analysis_system_prompt, final_report_system_prompt


class DataAnalysisAgent:
    """
    Data Analysis Agent
    
    Responsibilities:
    - Receive user natural language requirements
    - Generate Python analysis code
    - Execute code and collect results
    - Continue generating subsequent analysis code based on execution results
    """
    def __init__(self, llm_config: LLMConfig = None, output_dir: str = "outputs", max_rounds: int = 20):
        """
        Initialize the agent
        
        Args:
            config: LLM configuration
            output_dir: Output directory
            max_rounds: Maximum conversation rounds
        """
        self.config = llm_config or LLMConfig()
        self.llm = LLMHelper(self.config)
        self.base_output_dir = output_dir
        self.max_rounds = max_rounds
          # Conversation history and context
        self.conversation_history = []
        self.analysis_results = []
        self.current_round = 0
        self.session_output_dir = None
        self.executor = None

    def _process_response(self, response: str) -> Dict[str, Any]:
        """
        Unified processing of LLM responses, determine action type and execute corresponding operations
        
        Args:
            response: LLM response content
            
        Returns:
            Processing result dictionary
        """
        try:
            yaml_data = self.llm.parse_yaml_response(response)
            action = yaml_data.get('action', 'generate_code')
            
            print(f"🎯 Detected action: {action}")
            
            if action == 'analysis_complete':
                return self._handle_analysis_complete(response, yaml_data)
            elif action == 'collect_figures':
                return self._handle_collect_figures(response, yaml_data)
            elif action == 'generate_code':
                return self._handle_generate_code(response, yaml_data)
            else:
                print(f"⚠️ Unknown action type: {action}, treating as generate_code")
                return self._handle_generate_code(response, yaml_data)
                
        except Exception as e:
            print(f"⚠️ Failed to parse response: {str(e)}, treating as generate_code")
            return self._handle_generate_code(response, {})
    
    def _handle_analysis_complete(self, response: str, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis complete action"""
        print("✅ Analysis task completed")
        final_report = yaml_data.get('final_report', 'Analysis completed, no final report')
        return {
            'action': 'analysis_complete',
            'final_report': final_report,
            'response': response,
            'continue': False
        }
    
    def _handle_collect_figures(self, response: str, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle figure collection action"""
        print("📊 Starting to collect figures")
        figures_to_collect = yaml_data.get('figures_to_collect', [])
        
        collected_figures = []
        
        for figure_info in figures_to_collect:
            figure_number = figure_info.get('figure_number')
            filename = figure_info.get('filename', f'figure_{figure_number}.png')
            file_path = figure_info.get('file_path', '')  # Get the specific file path
            description = figure_info.get('description', '')
            analysis = figure_info.get('analysis', '')
            
            print(f"📈 Collecting figure {figure_number}: {filename}")
            print(f"   📂 Path: {file_path}")
            print(f"   📝 Description: {description}")
            print(f"   🔍 Analysis: {analysis}")
            
            # Verify if file exists
            if file_path and os.path.exists(file_path):
                print(f"   ✅ File exists: {file_path}")
            elif file_path:
                print(f"   ⚠️ File does not exist: {file_path}")
            else:
                print(f"   ⚠️ File path not provided")
            
            # Record figure information
            collected_figures.append({
                'figure_number': figure_number,
                'filename': filename,
                'file_path': file_path,
                'description': description,
                'analysis': analysis
            })
        
        return {
            'action': 'collect_figures',
            'collected_figures': collected_figures,
            'response': response,
            'continue': True
        }
    def _handle_generate_code(self, response: str, yaml_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle code generation and execution action"""
        # Get code from YAML data (more accurate)
        code = yaml_data.get('code', '')
        
        # If no code in YAML, try to extract from response
        if not code:
            code = extract_code_from_response(response)
        
        if code:
            print(f"🔧 Executing code:\n{code}")
            print("-" * 40)
            
            # Execute code
            result = self.executor.execute_code(code)
            
            # Format execution results
            feedback = format_execution_result(result)
            print(f"📋 Execution feedback:\n{feedback}")
            
            return {
                'action': 'generate_code',
                'code': code,
                'result': result,
                'feedback': feedback,
                'response': response,
                'continue': True
            }
        else:
            # If no code, LLM response format is problematic, need to regenerate
            print("⚠️ No executable code extracted from response, requesting LLM to regenerate")
            return {
                'action': 'invalid_response',
                'error': 'Response missing executable code',
                'response': response,
                'continue': True
            }
        
    def analyze(self, user_input: str, files: List[str] = None) -> Dict[str, Any]:
        """
        Start analysis process
        
        Args:
            user_input: User's natural language requirements
            files: List of data file paths
            
        Returns:
            Analysis result dictionary
        """
        # Reset state
        self.conversation_history = []
        self.analysis_results = []
        self.current_round = 0
        
        # Create dedicated output directory for this analysis
        self.session_output_dir = create_session_output_dir(self.base_output_dir,user_input)
        
        # Initialize code executor using session directory
        self.executor = CodeExecutor(self.session_output_dir)
        
        # Set session directory variable to execution environment
        self.executor.set_variable('session_output_dir', self.session_output_dir)
        
        # Build initial prompt
        initial_prompt = f"""User requirement: {user_input}"""
        if files:
            initial_prompt += f"\nData files: {', '.join(files)}"
        
        print(f"🚀 Starting data analysis task")
        print(f"📝 User requirement: {user_input}")
        if files:
            print(f"📁 Data files: {', '.join(files)}")
        print(f"📂 Output directory: {self.session_output_dir}")
        print(f"🔢 Maximum rounds: {self.max_rounds}")
        print("=" * 60)
          # Add to conversation history
        self.conversation_history.append({
            'role': 'user',
            'content': initial_prompt
        })
        
        while self.current_round < self.max_rounds:
            self.current_round += 1
            print(f"\n🔄 Round {self.current_round} analysis")
              # Call LLM to generate response
            try:                # Get current execution environment variable information
                notebook_variables = self.executor.get_environment_info()
                
                # Format system prompt, fill in dynamic notebook variable information
                formatted_system_prompt = data_analysis_system_prompt.format(
                    notebook_variables=notebook_variables
                )
                
                response = self.llm.call(
                    prompt=self._build_conversation_prompt(),
                    system_prompt=formatted_system_prompt
                )
                
                print(f"🤖 Assistant response:\n{response}")
                
                # Use unified response processing method
                process_result = self._process_response(response)
                
                # Decide whether to continue based on processing result
                if not process_result.get('continue', True):
                    print(f"\n✅ Analysis completed!")
                    break
                
                # Add to conversation history
                self.conversation_history.append({
                    'role': 'assistant',
                    'content': response
                })
                
                # Add different feedback based on action type
                if process_result['action'] == 'generate_code':
                    feedback = process_result.get('feedback', '')
                    self.conversation_history.append({
                        'role': 'user',
                        'content': f"Code execution feedback:\n{feedback}"
                    })
                    
                    # Record analysis results
                    self.analysis_results.append({
                        'round': self.current_round,
                        'code': process_result.get('code', ''),
                        'result': process_result.get('result', {}),
                        'response': response
                    })                
                elif process_result['action'] == 'collect_figures':
                    # Record figure collection results
                    collected_figures = process_result.get('collected_figures', [])
                    feedback = f"Collected {len(collected_figures)} figures and their analysis"
                    self.conversation_history.append({
                        'role': 'user', 
                        'content': f"Figure collection feedback:\n{feedback}\nPlease continue with the next analysis step."
                    })
                    
                    # Record to analysis results
                    self.analysis_results.append({
                        'round': self.current_round,
                        'action': 'collect_figures',
                        'collected_figures': collected_figures,
                        'response': response
                    })
           
            except Exception as e:
                error_msg = f"LLM call error: {str(e)}"
                print(f"❌ {error_msg}")
                self.conversation_history.append({
                    'role': 'user',
                    'content': f"Error occurred: {error_msg}, please regenerate code."
                })
        # Generate final summary
        if self.current_round >= self.max_rounds:
            print(f"\n⚠️ Reached maximum rounds ({self.max_rounds}), analysis ended")
        
        return self._generate_final_report()
    
    def _build_conversation_prompt(self) -> str:
        """Build conversation prompt"""
        prompt_parts = []
        
        for msg in self.conversation_history:
            role = msg['role']
            content = msg['content']
            if role == 'user':
                prompt_parts.append(f"User: {content}")
            else:
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def _extract_filename_from_code(self, code: str) -> Optional[str]:
        """Extract the PNG filename from matplotlib code"""
        import re
        # Look for patterns like: 
        # - os.path.join(session_output_dir, 'filename.png')
        # - plt.savefig('filename.png')
        # - image_filename = 'filename.png'
        # - file_path = os.path.join(..., image_filename) where image_filename = 'xxx.png'
        patterns = [
            r"os\.path\.join\([^,]+,\s*['\"]([^'\"]+\.png)['\"]\)",
            r"plt\.savefig\(['\"]([^'\"]+\.png)['\"]",
            r"file_path\s*=\s*['\"]([^'\"]+\.png)['\"]",
            r"savefig\(['\"]([^'\"]+\.png)['\"]",
            r"image_filename\s*=\s*['\"]([^'\"]+\.png)['\"]",
            r"filename\s*=\s*['\"]([^'\"]+\.png)['\"]",
            r"['\"]([A-Za-z_][A-Za-z0-9_]*\.png)['\"]",  # Generic pattern for any .png string
        ]
        
        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                filename = match.group(1)
                return filename
        
        return None
    
    def _find_all_matplotlib_codes(self) -> List[Dict[str, Any]]:
        """Find all successfully executed matplotlib visualization codes"""
        matplotlib_codes = []
        for result in self.analysis_results:
            if result.get('action') != 'collect_figures':
                code = result.get('code', '')
                exec_result = result.get('result', {})
                # Check if it's matplotlib code and was successful
                # Check for 'matplotlib' OR 'plt.' (since plt is commonly used without re-importing)
                is_matplotlib = 'matplotlib' in code.lower() or 'plt.' in code.lower()
                has_savefig = 'savefig' in code.lower()
                if code and exec_result.get('success') and is_matplotlib and has_savefig:
                    filename = self._extract_filename_from_code(code)
                    matplotlib_codes.append({
                        'code': code,
                        'round': result.get('round', 'Unknown'),
                        'result': exec_result,
                        'filename': filename
                    })
        return matplotlib_codes
    
    def _find_last_matplotlib_code(self) -> Optional[Dict[str, Any]]:
        """Find the last successfully executed matplotlib visualization code"""
        all_codes = self._find_all_matplotlib_codes()
        return all_codes[-1] if all_codes else None
    
    def _identify_variables_in_code(self, code: str) -> List[str]:
        """Identify variable names used in the code that might be DataFrames or data structures"""
        import ast
        import re
        
        variables = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Find variable names (Name nodes that are not function calls)
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Load, ast.Store)):
                    var_name = node.id
                    # Check if it's likely a data variable (not a builtin, not a function call)
                    if not var_name.startswith('_') and var_name not in ['print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'os', 'plt', 'pd', 'np', 'json']:
                        # Check if this variable exists in the environment and is a DataFrame/array
                        if var_name in self.executor.shell.user_ns:
                            var_value = self.executor.shell.user_ns[var_name]
                            if hasattr(var_value, '__class__'):
                                class_name = var_value.__class__.__name__
                                if class_name in ['DataFrame', 'Series', 'ndarray']:
                                    if var_name not in variables:
                                        variables.append(var_name)
        except:
            # Fallback: use regex to find common DataFrame variable patterns
            df_pattern = r'\b([a-z_][a-z0-9_]*)\s*\.\s*(head|tail|plot|pivot|groupby|values|columns|index)\b'
            matches = re.findall(df_pattern, code, re.IGNORECASE)
            for match in matches:
                var_name = match[0]
                if var_name in self.executor.shell.user_ns:
                    var_value = self.executor.shell.user_ns[var_name]
                    if hasattr(var_value, '__class__'):
                        class_name = var_value.__class__.__name__
                        if class_name in ['DataFrame', 'Series', 'ndarray']:
                            if var_name not in variables:
                                variables.append(var_name)
        
        return variables
    
    def _get_variable_data_preview(self, var_names: List[str]) -> str:
        """Get actual data content from specific variables for inclusion in prompt"""
        import json
        data_previews = []
        for var_name in var_names:
            if var_name in self.executor.shell.user_ns:
                var_value = self.executor.shell.user_ns[var_name]
                try:
                    class_name = var_value.__class__.__name__
                    if class_name == 'DataFrame':
                        # Convert DataFrame to dict for preview
                        if len(var_value) <= 30:
                            data_dict = var_value.reset_index().to_dict('records')
                        else:
                            data_dict = var_value.head(15).reset_index().to_dict('records')
                        data_json = json.dumps(data_dict, indent=2, default=str)
                        columns = list(var_value.columns)
                        index_vals = list(var_value.index)
                        data_previews.append(f"""
**Variable `{var_name}` (DataFrame) - THIS IS THE REAL DATA TO EMBED:**
- Columns: {columns}
- Index: {index_vals}
- Data as JSON (embed this in .jsx):
```json
{data_json}
```
- Access code: `{var_name}.reset_index().to_dict('records')`
""")
                    elif class_name == 'Series':
                        data_list = var_value.tolist()
                        data_json = json.dumps(data_list, indent=2, default=str)
                        data_previews.append(f"""
**Variable `{var_name}` (Series) - THIS IS THE REAL DATA:**
```json
{data_json}
```
- Access code: `{var_name}.tolist()`
""")
                    elif class_name == 'ndarray':
                        data_list = var_value.tolist()
                        data_json = json.dumps(data_list[:50] if len(var_value.flatten()) > 50 else data_list, indent=2, default=str)
                        data_previews.append(f"""
**Variable `{var_name}` (numpy array) - THIS IS THE REAL DATA:**
```json
{data_json}
```
- Access code: `{var_name}.tolist()`
""")
                except Exception as e:
                    data_previews.append(f"**Variable `{var_name}`: Could not preview ({e})**")
        
        if data_previews:
            return "\n".join(data_previews)
        return "No data previews available"
    
    def _get_data_structure_info(self) -> str:
        """Get information about data structures in the execution environment"""
        try:
            env_info = self.executor.get_environment_info()
            # Extract DataFrame information WITH ACTUAL DATA
            data_info = []
            for var_name in self.executor.shell.user_ns.keys():
                if not var_name.startswith('_'):
                    var_value = self.executor.shell.user_ns[var_name]
                    if hasattr(var_value, '__class__'):
                        class_name = var_value.__class__.__name__
                        if class_name == 'DataFrame':
                            try:
                                shape = var_value.shape
                                columns = list(var_value.columns)
                                index_vals = list(var_value.index)
                                # Include actual data preview
                                data_preview = var_value.to_dict('records') if len(var_value) <= 20 else var_value.head(10).to_dict('records')
                                data_info.append(f"- {var_name}: pandas DataFrame with shape {shape}\n  Columns: {columns}\n  Index: {index_vals}\n  Data preview (as JSON): {data_preview}")
                            except Exception as e:
                                data_info.append(f"- {var_name}: pandas DataFrame (could not get preview: {e})")
                        elif class_name == 'ndarray':
                            try:
                                data_info.append(f"- {var_name}: numpy array with shape {var_value.shape}\n  Data: {var_value.tolist()[:20] if len(var_value.flatten()) > 20 else var_value.tolist()}")
                            except:
                                data_info.append(f"- {var_name}: numpy array")
            
            if data_info:
                return "\n".join(data_info)
            return "No DataFrame variables found in current environment"
        except Exception as e:
            return f"Could not retrieve data structure info: {str(e)}"
    
    def _build_recharts_conversion_prompt(self, matplotlib_code: str, target_filename: str, conversation_history: List[Dict[str, str]]) -> str:
        """Build the prompt for Recharts conversion with conversation history"""
        prompt_parts = []
        
        # Add initial instruction if this is the first attempt
        if not conversation_history:
            prompt_parts.append("""**Task**: Rewrite the matplotlib code below to output a Recharts `.jsx` file instead of a `.png` image.

The code should perform the SAME data transformations (loading, grouping, pivoting, etc.) but instead of calling `plt.savefig()`, it should:
1. Convert the chart data to JSON format
2. Generate a React component using Recharts with the data embedded
3. Write the `.jsx` file to the output directory

**Original matplotlib code:**
```python
{matplotlib_code}
```

**Target output:** `{target_filename}` → `{target_filename_jsx}`

**Rewrite the code to:**
1. Keep ALL the data loading and transformation logic (pd.read_csv, groupby, pivot, etc.)
2. Instead of matplotlib plotting, convert the final data to JSON
3. Generate a Recharts React component with the data embedded as JavaScript constants
4. Save as `.jsx` file using `open(file_path, 'w', encoding='utf-8')`

**Output structure:**
```python
import pandas as pd
import json
import os

# === KEEP THE SAME DATA TRANSFORMATIONS ===
# (copy the data loading, cleaning, groupby, pivot logic from original code)

# === CONVERT TO JSX INSTEAD OF MATPLOTLIB ===
# Convert data to JSON
data_json = json.dumps(your_data.to_dict('records'), indent=2)

# Generate JSX content
jsx_content = f'''import React from 'react';
import {{ BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer }} from 'recharts';

const data = {{data_json}};

export default function ChartComponent() {{
  return (
    <ResponsiveContainer width="100%" height={{400}}>
      <BarChart data={{data}}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="category" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="value" fill="#5858AA" />
      </BarChart>
    </ResponsiveContainer>
  );
}}
'''

# Save JSX file
jsx_filename = '{target_filename_jsx}'
file_path = os.path.join(session_output_dir, jsx_filename)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(jsx_content)
print(f"Generated: {{file_path}}")
```

**Chart type mapping:**
- `plt.bar()` or `.plot(kind='bar')` → `<BarChart>` with `<Bar>` components
- `plt.plot()` or `.plot(kind='line')` → `<LineChart>` with `<Line>` components  
- `plt.boxplot()` → `<BoxPlot>` (or use `<ComposedChart>` with custom rendering)
- `plt.scatter()` → `<ScatterChart>` with `<Scatter>` components

**REQUIRED COLOR PALETTE (use ONLY these colors):**
```javascript
const COLORS = ['#4A148C', '#5858AA', '#7070BB', '#8888CC', '#9E9ED8', '#B3B3E0', '#C5C5E5', '#D4D4E8', '#E8E8E8', '#F5F5F5', '#FFFFFF'];
```
- Use darker colors (#4A148C, #5858AA, #7070BB) for primary data elements (bars, lines, areas)
- Use lighter colors (#E8E8E8, #F5F5F5) for backgrounds and grid lines
- For multiple data series, cycle through the COLORS array

**Important:**
- The `.jsx` file must be STANDALONE - all data embedded as JavaScript constants
- Match the chart type, labels, and styling from the original matplotlib code
- Use the REQUIRED COLOR PALETTE above (do NOT use default Recharts colors)
- Include Tooltip for interactivity
- Use ResponsiveContainer for responsive sizing

Please rewrite the matplotlib code to generate a `.jsx` file instead.""".format(
                matplotlib_code=matplotlib_code,
                target_filename=target_filename,
                target_filename_jsx=target_filename.replace('.png', '.jsx')
            ))
        else:
            # Add conversation history
            for msg in conversation_history:
                role = msg['role']
                content = msg['content']
                if role == 'user':
                    prompt_parts.append(f"User: {content}")
                else:
                    prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def _fix_jsx_object_braces(self, jsx_file_path: str) -> bool:
        """Post-process JSX file to fix single curly braces for object literals to double curly braces
        
        In JSX:
        - { expression } is for JavaScript expressions
        - {{ object }} is for object literals passed as props
        
        The LLM often generates: margin={ top: 20, right: 30 }
        But it should be:        margin={{ top: 20, right: 30 }}
        """
        import re
        
        try:
            with open(jsx_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Common JSX props that typically take object literals
            object_props = [
                'margin', 'label', 'tick', 'style', 'wrapperStyle', 'contentStyle',
                'labelStyle', 'itemStyle', 'iconStyle', 'domain', 'padding', 
                'viewBox', 'cursor', 'offset', 'position', 'tickFormatter'
            ]
            
            # Process line by line for better control
            lines = content.split('\n')
            fixed_lines = []
            fixes_made = 0
            
            for line in lines:
                fixed_line = line
                
                for prop in object_props:
                    # Pattern to match: prop={ word: value } (single braces with object literal)
                    # The key insight: object literals have "word:" pattern inside
                    # We need to NOT match prop={{ ... }} (already correct)
                    
                    # First, check if this prop exists with single braces and object content
                    # Match: prop={ key: (not preceded by another {)
                    single_brace_obj_pattern = rf'{prop}=\{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:'
                    double_brace_pattern = rf'{prop}=\{{\{{'
                    
                    # Only fix if it's single brace (not already double)
                    if re.search(single_brace_obj_pattern, fixed_line) and not re.search(double_brace_pattern, fixed_line):
                        # Find and replace the full prop assignment
                        # Match prop={ ... } where ... contains key: value patterns
                        # Be careful with nested braces - use a simpler approach
                        
                        # Find the starting position
                        match = re.search(rf'{prop}=\{{', fixed_line)
                        if match:
                            start_pos = match.end() - 1  # Position of opening {
                            
                            # Count braces to find matching closing brace
                            brace_count = 0
                            end_pos = start_pos
                            in_string = False
                            string_char = None
                            
                            for i in range(start_pos, len(fixed_line)):
                                char = fixed_line[i]
                                
                                # Handle string literals
                                if char in '"\'':
                                    if not in_string:
                                        in_string = True
                                        string_char = char
                                    elif char == string_char and fixed_line[i-1] != '\\':
                                        in_string = False
                                    continue
                                
                                if in_string:
                                    continue
                                
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_pos = i
                                        break
                            
                            if end_pos > start_pos:
                                # Extract the content between braces
                                obj_content = fixed_line[start_pos+1:end_pos]
                                
                                # Check if it looks like an object literal (has word: pattern)
                                if re.search(r'[a-zA-Z_][a-zA-Z0-9_]*\s*:', obj_content):
                                    # Replace single braces with double braces
                                    before = fixed_line[:start_pos]
                                    after = fixed_line[end_pos+1:]
                                    fixed_line = f"{before}{{{{{obj_content}}}}}{after}"
                                    fixes_made += 1
                
                fixed_lines.append(fixed_line)
            
            content = '\n'.join(fixed_lines)
            
            if content != original_content:
                with open(jsx_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"🔧 Post-processed JSX file: Fixed {fixes_made} object literal brace(s) in {jsx_file_path}")
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Warning: Could not post-process JSX file: {e}")
            return False
    
    def _convert_matplotlib_to_recharts(self, matplotlib_code: str, target_filename: str, max_attempts: int = 5) -> Optional[str]:
        """Convert matplotlib code to Python code that generates a Recharts React component with iterative error feedback"""
        print(f"\n🔄 Converting matplotlib code to Recharts React component...")
        print(f"\n📝 Step 1: Original matplotlib Python code:")
        print("=" * 80)
        print(matplotlib_code)
        print("=" * 80)
        
        # Create separate conversation history for Recharts conversion
        recharts_conversation_history = []
        
        # Iterative loop with error feedback (same pattern as main analysis)
        for attempt in range(1, max_attempts + 1):
            print(f"\n🔄 Recharts conversion attempt {attempt}/{max_attempts}")
            
            try:
                # Build prompt with conversation history
                conversion_prompt = self._build_recharts_conversion_prompt(
                    matplotlib_code,
                    target_filename,
                    recharts_conversation_history
                )
                
                # Call LLM to generate conversion code
                response = self.llm.call(
                    prompt=conversion_prompt,
                    system_prompt="""You are an expert at converting matplotlib code to Recharts React components.

YOUR TASK: Rewrite matplotlib code to output a `.jsx` file instead of a `.png` image.

APPROACH:
1. KEEP all the data loading and transformation logic (read_csv, groupby, pivot, etc.)
2. REPLACE the matplotlib plotting with JSX generation
3. Convert the chart data to JSON and embed it in the JSX file
4. Save as .jsx file instead of .png

The rewritten code should:
- Perform the SAME data transformations as the original
- Output a STANDALONE .jsx file with all data embedded
- Match the chart type (bar→BarChart, line→LineChart, etc.)
- Include interactive Tooltip
- Use ResponsiveContainer for responsive sizing

Use open(file_path, 'w', encoding='utf-8') to write the .jsx file.""",
                    max_tokens=4096
                )
                
                print(f"🤖 LLM response (attempt {attempt}):")
                print(response)
                
                # Extract code from response
                code = extract_code_from_response(response)
                
                if not code:
                    print(f"⚠️ Could not extract code from response, requesting regeneration...")
                    recharts_conversation_history.append({
                        'role': 'assistant',
                        'content': response
                    })
                    recharts_conversation_history.append({
                        'role': 'user',
                        'content': "No executable Python code was found in your response. Please provide the Python code wrapped in a code block (```python ... ```)."
                    })
                    continue
                
                print(f"\n✅ Step 2 (Attempt {attempt}): Generated Python code that creates Recharts component:")
                print("=" * 80)
                print(code)
                print("=" * 80)
                
                # Execute the conversion code
                print(f"\n🔧 Step 3 (Attempt {attempt}): Executing conversion code...")
                result = self.executor.execute_code(code)
                
                if result.get('success'):
                    print(f"✅ Successfully generated Recharts component!")
                    if result.get('output'):
                        print(f"\n📋 Step 3 Output (full execution result):")
                        print("=" * 80)
                        print(result.get('output'))
                        print("=" * 80)
                    
                    # Post-process the generated JSX file to fix common syntax issues
                    jsx_filename = target_filename.replace('.png', '.jsx')
                    jsx_file_path = os.path.join(self.session_output_dir, jsx_filename)
                    if os.path.exists(jsx_file_path):
                        self._fix_jsx_object_braces(jsx_file_path)
                    
                    return code
                else:
                    # Execution failed - provide feedback and retry
                    error_msg = result.get('error', 'Unknown error')
                    output_msg = result.get('output', '')
                    
                    print(f"\n⚠️ Step 3 (Attempt {attempt}): Conversion code execution failed")
                    print("=" * 80)
                    print(f"Error: {error_msg}")
                    if output_msg:
                        print(f"\nPartial output:\n{output_msg}")
                    print("=" * 80)
                    
                    # Add to conversation history for next attempt
                    recharts_conversation_history.append({
                        'role': 'assistant',
                        'content': response
                    })
                    
                    # Format feedback similar to main analysis loop
                    feedback = format_execution_result(result)
                    
                    # Add specific guidance for common errors
                    additional_feedback = ""
                    if 'environment variable' in error_msg.lower() or 'os.getenv' in code.lower() or 'process.env' in code.lower():
                        additional_feedback = "\n\n**CRITICAL ERROR**: The code is trying to use environment variables. This is NOT allowed. You MUST extract data from Python variables (like pivot_df, groups, labels, etc.) and embed it directly in the .jsx file as JavaScript constants. Do NOT use os.getenv() or process.env. Extract the actual data values from the Python variables and convert them to JSON, then embed the JSON directly in the .jsx file string."
                    
                    recharts_conversation_history.append({
                        'role': 'user',
                        'content': f"Code execution feedback:\n{feedback}{additional_feedback}\nPlease fix the errors and regenerate the code. Remember: ALL data must be extracted from Python variables and embedded directly in the .jsx file - no environment variables, no external file reads at runtime."
                    })
                    
                    # Continue to next attempt
                    continue
                    
            except Exception as e:
                error_msg = f"LLM call error: {str(e)}"
                print(f"❌ {error_msg}")
                recharts_conversation_history.append({
                    'role': 'user',
                    'content': f"Error occurred: {error_msg}, please regenerate code."
                })
                continue
        
        # If we get here, all attempts failed
        print(f"\n⚠️ Reached maximum attempts ({max_attempts}) for Recharts conversion, giving up")
        return None
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate final analysis report"""
        # Convert ALL matplotlib visualizations to Recharts components
        all_matplotlib_codes = self._find_all_matplotlib_codes()
        conversion_results = []  # Track all conversion results
        
        if all_matplotlib_codes:
            print(f"\n🎨 Found {len(all_matplotlib_codes)} matplotlib visualization(s) to convert to Recharts")
            
            successful_conversions = 0
            failed_conversions = 0
            
            for idx, matplotlib_code_info in enumerate(all_matplotlib_codes, 1):
                code = matplotlib_code_info['code']
                round_num = matplotlib_code_info['round']
                # Handle None filename - use default if filename is None or not found
                filename = matplotlib_code_info.get('filename') or f'chart_{idx}.png'
                jsx_filename = filename.replace('.png', '.jsx')
                
                print(f"\n{'='*80}")
                print(f"📊 Converting visualization {idx}/{len(all_matplotlib_codes)}")
                print(f"   Round: {round_num}")
                print(f"   PNG: {filename} → JSX: {jsx_filename}")
                print(f"{'='*80}")
                
                # Convert this matplotlib code to Recharts
                # The conversion will rewrite the matplotlib code to output JSX instead
                conversion_code = self._convert_matplotlib_to_recharts(
                    code,
                    filename,
                    max_attempts=5
                )
                
                # Track the conversion result
                conversion_results.append({
                    'png_filename': filename,
                    'jsx_filename': jsx_filename,
                    'matplotlib_code': code,
                    'conversion_code': conversion_code,
                    'success': conversion_code is not None,
                    'round': round_num
                })
                
                if conversion_code:
                    successful_conversions += 1
                    print(f"✅ Successfully converted {filename} → {jsx_filename}")
                else:
                    failed_conversions += 1
                    print(f"⚠️ Failed to convert {filename} to Recharts")
            
            print(f"\n{'='*80}")
            print(f"📊 Recharts Conversion Summary:")
            print(f"   Total visualizations: {len(all_matplotlib_codes)}")
            print(f"   Successful: {successful_conversions}")
            print(f"   Failed: {failed_conversions}")
            print(f"{'='*80}")
            
            # Save the conversion code to file
            self._save_recharts_conversion_code(conversion_results)
        
        # Collect all generated figure information
        all_figures = []
        for result in self.analysis_results:
            if result.get('action') == 'collect_figures':
                all_figures.extend(result.get('collected_figures', []))
        
        print(f"\n📊 Starting to generate final analysis report...")
        print(f"📂 Output directory: {self.session_output_dir}")
        print(f"🔢 Total rounds: {self.current_round}")
        print(f"📈 Collected figures: {len(all_figures)}")
        
        # Build prompt for generating final report
        final_report_prompt = self._build_final_report_prompt(all_figures)
        
        try:            # Call LLM to generate final report
            response = self.llm.call(
                prompt=final_report_prompt,
                system_prompt="You will receive a final report request for a data analysis task. Please generate a complete analysis report based on the provided analysis results and figure information.",
                max_tokens=16384  # Set larger token limit to accommodate complete report
            )
            
            # Parse response, extract final report
            try:
                yaml_data = self.llm.parse_yaml_response(response)
                if yaml_data.get('action') == 'analysis_complete':
                    final_report_content = yaml_data.get('final_report', 'Report generation failed')
                else:
                    final_report_content = "LLM did not return analysis_complete action, report generation failed"
            except:
                # If parsing fails, use response content directly
                final_report_content = response
            
            print("✅ Final report generation completed")
            
        except Exception as e:
            print(f"❌ Error generating final report: {str(e)}")
            final_report_content = f"Report generation failed: {str(e)}"
        
        # Save final report to file
        report_file_path = os.path.join(self.session_output_dir, "Final_Analysis_Report.md")
        try:
            with open(report_file_path, 'w', encoding='utf-8') as f:
                f.write(final_report_content)
            print(f"📄 Final report saved to: {report_file_path}")
        except Exception as e:
            print(f"❌ Failed to save report file: {str(e)}")
        
        # Save executed code to file
        code_file_path = os.path.join(self.session_output_dir, "Executed_Code.py")
        try:
            with open(code_file_path, 'w', encoding='utf-8') as f:
                f.write("# Executed Code History\n")
                f.write("# This file contains all Python code that was executed during the analysis\n")
                f.write(f"# Total rounds: {self.current_round}\n\n")
                
                code_block_number = 0
                for result in self.analysis_results:
                    # Only save code blocks (not figure collection actions)
                    if result.get('action') != 'collect_figures' and result.get('code'):
                        code_block_number += 1
                        round_num = result.get('round', 'Unknown')
                        code = result.get('code', '')
                        exec_result = result.get('result', {})
                        
                        f.write(f"{'=' * 80}\n")
                        f.write(f"# Round {round_num} - Code Block {code_block_number}\n")
                        f.write(f"{'=' * 80}\n")
                        
                        # Add execution status comment
                        if exec_result.get('success'):
                            f.write("# ✅ Execution: SUCCESS\n")
                            if exec_result.get('output'):
                                output_preview = exec_result.get('output', '')[:200]
                                f.write(f"# Output preview: {output_preview}...\n")
                        else:
                            f.write("# ❌ Execution: FAILED\n")
                            if exec_result.get('error'):
                                f.write(f"# Error: {exec_result.get('error')}\n")
                        
                        f.write("\n")
                        f.write(code)
                        f.write("\n\n")
            
            print(f"💻 Executed code saved to: {code_file_path}")
        except Exception as e:
            print(f"❌ Failed to save code file: {str(e)}")
        
        # Return complete analysis results
        return {
            'session_output_dir': self.session_output_dir,
            'total_rounds': self.current_round,
            'analysis_results': self.analysis_results,
            'collected_figures': all_figures,
            'conversation_history': self.conversation_history,
            'final_report': final_report_content,
            'report_file_path': report_file_path        }

    def _build_final_report_prompt(self, all_figures: List[Dict[str, Any]]) -> str:
        """Build prompt for generating final report"""
        
        # Build figure information summary using relative paths
        figures_summary = ""
        if all_figures:
            figures_summary = "\nGenerated figures and analysis:\n"
            for i, figure in enumerate(all_figures, 1):
                filename = figure.get('filename', 'Unknown filename')
                # Use relative path format, suitable for referencing in report
                relative_path = f"./{filename}"
                figures_summary += f"{i}. {filename}\n"
                figures_summary += f"   Relative path: {relative_path}\n"
                figures_summary += f"   Description: {figure.get('description', 'No description')}\n"
                figures_summary += f"   Analysis: {figure.get('analysis', 'No analysis')}\n\n"
        else:
            figures_summary = "\nNo figures were generated in this analysis.\n"
        
        # Build code execution results summary (only includes successfully executed code blocks)
        code_results_summary = ""
        success_code_count = 0
        for result in self.analysis_results:
            if result.get('action') != 'collect_figures' and result.get('code'):
                exec_result = result.get('result', {})
                if exec_result.get('success'):
                    success_code_count += 1
                    code_results_summary += f"Code block {success_code_count}: Execution successful\n"
                    if exec_result.get('output'):
                        code_results_summary += f"Output: {exec_result.get('output')[:]}\n\n"

        
        # Use unified prompt template from prompts.py and add relative path usage instructions
        prompt = final_report_system_prompt.format(
            current_round=self.current_round,
            session_output_dir=self.session_output_dir,
            figures_summary=figures_summary,
            code_results_summary=code_results_summary
        )
        
        # Explicitly require use of relative paths in prompt
        prompt += """

📁 **Figure Path Usage Instructions**:
The report and figures are in the same directory. Please use relative paths to reference figures in the report:
- Format: ![Figure description](./figure_filename.png)
- Example: ![Revenue Trend](./Revenue_Trend.png)
- This ensures the report can correctly display figures in different environments
"""
        
        return prompt
    
    def _save_recharts_conversion_code(self, conversion_results: List[Dict[str, Any]]) -> None:
        """Save the Python code that generates .jsx files to the output folder"""
        if not conversion_results:
            return
        
        conversion_code_path = os.path.join(self.session_output_dir, "Recharts_Conversion_Code.py")
        
        with open(conversion_code_path, 'w', encoding='utf-8') as f:
            f.write("# Recharts Conversion Code\n")
            f.write("# This file contains the Python code used to generate .jsx Recharts components\n")
            f.write("# from matplotlib visualizations\n")
            f.write("#" + "=" * 79 + "\n\n")
            
            # Summary section
            successful = sum(1 for r in conversion_results if r['success'])
            failed = sum(1 for r in conversion_results if not r['success'])
            f.write(f"# CONVERSION SUMMARY\n")
            f.write(f"# Total visualizations: {len(conversion_results)}\n")
            f.write(f"# Successful: {successful}\n")
            f.write(f"# Failed: {failed}\n")
            f.write("#" + "=" * 79 + "\n\n")
            
            for idx, result in enumerate(conversion_results, 1):
                f.write("#" + "=" * 79 + "\n")
                f.write(f"# Conversion {idx}: {result['png_filename']} → {result['jsx_filename']}\n")
                f.write(f"# Status: {'SUCCESS' if result['success'] else 'FAILED'}\n")
                f.write(f"# Analysis Round: {result['round']}\n")
                f.write("#" + "=" * 79 + "\n\n")
                
                # Original matplotlib code
                f.write(f"# ORIGINAL MATPLOTLIB CODE:\n")
                f.write("#" + "-" * 79 + "\n")
                for line in result['matplotlib_code'].split('\n'):
                    f.write(f"# {line}\n")
                f.write("#" + "-" * 79 + "\n\n")
                
                # Conversion code (if successful)
                if result['success'] and result['conversion_code']:
                    f.write(f"# CONVERSION CODE (generates {result['jsx_filename']}):\n")
                    f.write("#" + "-" * 79 + "\n\n")
                    f.write(result['conversion_code'])
                    f.write("\n\n")
                else:
                    f.write("# CONVERSION FAILED - No code generated\n\n")
        
        print(f"\n📄 Saved Recharts conversion code to: {conversion_code_path}")
        
        # Also log which .png files are missing .jsx counterparts
        missing_jsx = [r for r in conversion_results if not r['success']]
        if missing_jsx:
            print(f"\n⚠️ The following .png files do NOT have corresponding .jsx files:")
            for r in missing_jsx:
                print(f"   - {r['png_filename']}")

    def reset(self):
        """Reset agent state"""
        self.conversation_history = []
        self.analysis_results = []
        self.current_round = 0
        self.executor.reset_environment()

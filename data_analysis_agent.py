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
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate final analysis report"""
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
        
        # 返回完整的分析结果
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

    def reset(self):
        """Reset agent state"""
        self.conversation_history = []
        self.analysis_results = []
        self.current_round = 0
        self.executor.reset_environment()

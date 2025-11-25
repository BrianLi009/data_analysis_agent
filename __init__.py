# -*- coding: utf-8 -*-
"""
Data Analysis Agent Package

An LLM-based intelligent data analysis agent, specifically designed for Jupyter Notebook environments.
"""

from .data_analysis_agent import DataAnalysisAgent
from .config.llm_config import LLMConfig
from .utils.code_executor import CodeExecutor

__version__ = "1.0.0"
__author__ = "Data Analysis Agent Team"

# Main exported classes
__all__ = [
    "DataAnalysisAgent",
    "LLMConfig", 
    "CodeExecutor",
]

# Convenience functions
def create_agent(config=None, output_dir="outputs", max_rounds=20, session_dir=None):
    """
    Create a data analysis agent instance
    
    Args:
        config: LLM configuration, if None uses default configuration
        output_dir: Output directory
        max_rounds: Maximum analysis rounds
        session_dir: Specify session directory (optional)
        
    Returns:
        DataAnalysisAgent: Agent instance
    """
    if config is None:
        config = LLMConfig()
    return DataAnalysisAgent(llm_config=config, output_dir=output_dir, max_rounds=max_rounds, session_dir=session_dir)

def quick_analysis(query, files=None, output_dir="outputs", max_rounds=10):
    """
    Quick data analysis function
    
    Args:
        query: Analysis requirements (natural language)
        files: List of data file paths
        output_dir: Output directory
        max_rounds: Maximum analysis rounds
        
    Returns:
        dict: Analysis results
    """
    agent = create_agent(output_dir=output_dir, max_rounds=max_rounds)
    return agent.analyze(user_input=query, files=files)
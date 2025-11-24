
from typing import Any, Dict


def format_execution_result(result: Dict[str, Any]) -> str:
    """Format execution results into user-readable feedback"""
    feedback = []
    
    if result['success']:
        feedback.append("✅ Code execution successful")
        
        if result['output']:
            feedback.append(f"📊 Output results:\n{result['output']}")
        
        if result.get('variables'):
            feedback.append("📋 Newly generated variables:")
            for var_name, var_info in result['variables'].items():
                feedback.append(f"  - {var_name}: {var_info}")
    else:
        feedback.append("❌ Code execution failed")
        feedback.append(f"Error message: {result['error']}")
        if result['output']:
            feedback.append(f"Partial output: {result['output']}")
    
    return "\n".join(feedback)

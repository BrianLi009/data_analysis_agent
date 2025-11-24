from typing import Optional
import yaml


def extract_code_from_response(response: str) -> Optional[str]:
        """Extract code from LLM response"""
        try:
            # Try to parse YAML
            if '```yaml' in response:
                start = response.find('```yaml') + 7
                end = response.find('```', start)
                yaml_content = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                yaml_content = response[start:end].strip()
            else:
                yaml_content = response.strip()
            
            yaml_data = yaml.safe_load(yaml_content)
            if 'code' in yaml_data:
                return yaml_data['code']
        except:
            pass
        
        # If YAML parsing fails, try to extract ```python code block
        if '```python' in response:
            start = response.find('```python') + 9
            end = response.find('```', start)
            if end != -1:
                return response[start:end].strip()
        elif '```' in response:
            start = response.find('```') + 3
            end = response.find('```', start)
            if end != -1:
                return response[start:end].strip()
        
        return None
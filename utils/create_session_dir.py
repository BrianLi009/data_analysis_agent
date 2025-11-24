import os
import uuid

def create_session_output_dir(base_output_dir,user_input: str) -> str:
    """Create an independent output directory for this analysis"""

    
    # Use UUID to create unique session directory name (hexadecimal format, remove hyphens)
    session_id = uuid.uuid4().hex
    dir_name = f"session_{session_id}"
    session_dir = os.path.join(base_output_dir, dir_name)
    os.makedirs(session_dir, exist_ok=True)
    
    return session_dir
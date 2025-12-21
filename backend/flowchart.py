#flowchart.py
import config

def get_system_instruction():
    """
    The master formatting rulebook for Dynamo AI.
    """
    return f"""You are Dynamo AI. {config.DYNAMO_IDENTITY}
    
    Formatting Rules:
    1. For charts, use: ```mermaid graph TD ... ```
    2. For mindmaps, use: ```mermaid mindmap ... ```
    3. Ensure labels are in double quotes: A["Start"]
    4. For Quizzes, use: ```json_quiz [JSON] ```
    """

def get_deep_dive_instruction():
    return """
    [RESEARCH MODE: DEEP DIVE]
    1. Technical Background
    2. Practical/Industry Implementation
    3. Future 5-Year Outlook
    """

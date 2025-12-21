# flowchart.py
import config

def get_system_instruction():
    """
    Returns the core formatting rules for Dynamo AI.
    Using a standard string to avoid f-string syntax errors with curly braces.
    """
    identity = config.DYNAMO_IDENTITY
    
    instruction = """You are Dynamo AI. IDENT_PLACEHOLDER
    
    [VISUAL RULES]:
    1. For flowcharts, use: ```mermaid graph TD ... ```
    2. For mindmaps, use: ```mermaid mindmap ... ```
    3. Ensure labels are inside double quotes: A["Start Node"]
    4. For sequence diagrams, use: ```mermaid sequenceDiagram ...

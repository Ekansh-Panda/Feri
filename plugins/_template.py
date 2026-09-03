"""Plugin template for JARVIS auto-generated plugins."""

PLUGIN_NAME: str = "template"
PLUGIN_DESCRIPTION: str = "Auto-generated plugin template for JARVIS NEXUS"
PLUGIN_VERSION: str = "1.0.0"


def get_tools() -> list[dict]:
    """Return tool definitions for Gemini function calling."""
    return [
        {
            "name": "example_tool",
            "description": "An example tool that demonstrates the plugin interface.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "A message to process",
                    }
                },
                "required": ["message"],
            },
        }
    ]


def execute(tool_name: str, params: dict) -> dict:
    """Execute a tool by name with the given parameters."""
    if tool_name == "example_tool":
        message = params.get("message", "")
        return {
            "status": "success",
            "result": f"Processed: {message}",
            "plugin": PLUGIN_NAME,
        }
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(get_tools())
    print(execute("example_tool", {"message": "Hello JARVIS"}))

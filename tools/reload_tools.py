import importlib
import sys


def reload_tools():
    """
    Reloads all tool modules to apply code changes without restarting the agent.

    Returns a list of successfully reloaded modules.
    """
    reloaded_modules = []

    # Find all modules from the tools package
    tool_modules = [mod for mod in sys.modules if mod.startswith("tools.")]

    # Reload each module
    for module_name in tool_modules:
        try:
            module = sys.modules[module_name]
            importlib.reload(module)
            reloaded_modules.append(module_name)
        except Exception as e:
            return f"Failed to reload {module_name}: {str(e)}"

    return f"Successfully reloaded {len(reloaded_modules)} modules: {', '.join(reloaded_modules)}"

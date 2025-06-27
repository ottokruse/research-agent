from generative_ai_toolkit.agent import registry


@registry.tool
def think(thought: str) -> None:
    """
    Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning or some cache memory is needed.

    Parameters
    -----
    thought : str
        A thought to think about
    """
    pass

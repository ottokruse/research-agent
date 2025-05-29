#!/usr/bin/env python


import os
import textwrap

from generative_ai_toolkit.agent import BedrockConverseAgent
from generative_ai_toolkit.tracer import BaseTracer, InMemoryTracer, TeeTracer
from generative_ai_toolkit.tracer.trace import Trace
from generative_ai_toolkit.ui import traces_ui
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import HTML

from tools.fetch_html_as_markdown import fetch_html_as_markdown
from tools.github import fetch_github_file, list_github_folder
from tools.local_files import (
    get_git_tracked_tree,
    list_dir,
    patch_file,
    read_file_lines,
    write_file,
)
from tools.web_search import web_search


class ToolInvocationTracer(BaseTracer):
    def persist(self, trace: Trace):
        if trace.attributes.get("ai.trace.type") == "tool-invocation":
            tool_name = trace.attributes.get('ai.tool.name')
            tool_input = trace.attributes.get('ai.tool.input', {})
            
            # Print the tool name
            print_formatted_text(
                HTML(
                    f"<ansiblue>Completed tool invocation:</ansiblue> {tool_name}"
                ),
            )
            
            # Print each input parameter with truncated values
            if tool_input and isinstance(tool_input, dict):
                for key, value in tool_input.items():
                    # Convert value to string and truncate to 100 chars
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:97] + "..."
                    
                    print_formatted_text(
                        HTML(
                            f"  <ansiyellow>- {key}:</ansiyellow> {value_str}"
                        )
                    )

def main():
    cwd = os.getcwd()
    is_git_repository = os.path.isdir(os.path.join(cwd, ".git"))

    agent = BedrockConverseAgent(
        model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        system_prompt=textwrap.dedent(
            """
            You are an advanced AI agent. You excel in internet research.
            You can also read and write local files.
            Before writing or making changes to files, you MUST ask the user for their consent.
            The current working directory is: {cwd}{git_dir}
            """
        )
        .format(
            cwd=os.getcwd(), git_dir=" (a git repository)" if is_git_repository else ""
        )
        .strip(),
        tracer=TeeTracer()
        .add_tracer(InMemoryTracer())
        .add_tracer(ToolInvocationTracer()),
        max_successive_tool_invocations=30,
        # additional_model_request_fields={
        #     "reasoning_config": {"type": "enabled", "budget_tokens": 1024}
        # },
    )

    agent.register_tool(fetch_github_file)
    agent.register_tool(list_github_folder)
    agent.register_tool(fetch_html_as_markdown)
    agent.register_tool(read_file_lines)
    agent.register_tool(web_search)
    # agent.register_tool(read_file)
    agent.register_tool(write_file)
    agent.register_tool(patch_file)
    agent.register_tool(list_dir)
    agent.register_tool(get_git_tracked_tree)

    session = PromptSession()

    try:
        while True:

            user_input = session.prompt(
                HTML("<ansigreen>User:</ansigreen> "), multiline=True
            )

            if not user_input.strip():
                print_formatted_text(HTML("<ansiblue>Exiting ... </ansiblue>"))
                break

            print_formatted_text(
                HTML("<ansimagenta>Agent:</ansimagenta> "), end="", flush=True
            )
            print("...", end="", flush=True)

            first_chunk = True
            for chunk in agent.converse_stream(user_input):
                if first_chunk:
                    print(
                        "\b\b\b   \b\b\b", end="", flush=True
                    )  # backspace + overwrite "..."
                    first_chunk = False
                print_formatted_text(chunk, end="")
            print_formatted_text()

    except (KeyboardInterrupt, EOFError):
        print_formatted_text(HTML("<br/><ansiblue>Exiting ... </ansiblue>"))

    demo = traces_ui(agent.traces)
    demo.launch()


if __name__ == "__main__":
    main()

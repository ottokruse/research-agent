#!/usr/bin/env python


import os
import textwrap

import boto3
import botocore
import botocore.config
from generative_ai_toolkit.agent import BedrockConverseAgent
from generative_ai_toolkit.agent.registry import DEFAULT_TOOL_REGISTRY
from generative_ai_toolkit.ui import chat_ui

import tools


def main():
    cwd = os.getcwd()
    is_git_repository = os.path.isdir(os.path.join(cwd, ".git"))

    agent = BedrockConverseAgent(
        model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        system_prompt=textwrap.dedent(
            """
            You are an advanced AI agent. You help the user with:
            
            - Internet research
            - Coding

            Use the tools at your disposal to do your job.

            The current local working directory is: {cwd}{git_dir}

            Unless it's obvious they mean a file on GitHub, always presume the user is talking about a local file.

            ALWAYS ask user consent before writing or editing local files!

            ## Using the think tool

            Before taking any action or responding to the user after receiving tool results, use the think tool as a scratchpad to:
            - Break down complex problems into manageable steps
            - List the specific rules or constraints that apply to the current task
            - Check if all required information is available before proceeding
            - Verify that planned actions comply with all relevant policies
            - Analyze tool outputs carefully before using the information
            - Plan the sequence of tool calls needed to complete multi-step tasks

            The think tool helps you organize your reasoning. It doesn't retrieve new information or make changes - it's solely for structured thinking. Use it especially when:
            - Processing complex outputs from previous tool calls
            - Following detailed guidelines or policies
            - Making decisions where mistakes would be costly
            - Planning a sequence of actions that build on each other

            When using the think tool, be thorough but concise. Structure your thoughts clearly and focus on the specific reasoning needed for the current step.            
            """
        )
        .format(
            cwd=os.getcwd(), git_dir=" (a git tracked dir)" if is_git_repository else ""
        )
        .strip(),
        # additional_model_request_fields={
        #     "reasoning_config": {"type": "enabled", "budget_tokens": 1024}
        # },
        bedrock_client=boto3.client(
            "bedrock-runtime",
            config=botocore.config.Config(read_timeout=6 * 60, tcp_keepalive=True),
        ),
        tools=DEFAULT_TOOL_REGISTRY.scan_tools(tools),
    )

    print("Tools:")
    print("======")
    for tool in agent.tools:
        print(f"- {tool}")
    print()

    demo = chat_ui(agent)
    demo.launch(inbrowser=True)


if __name__ == "__main__":
    main()

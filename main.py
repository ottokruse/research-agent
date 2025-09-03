#!/usr/bin/env python


import datetime
import os
import textwrap
from typing import Literal

import boto3
from botocore.config import Config
from generative_ai_toolkit.agent import BedrockConverseAgent
from generative_ai_toolkit.agent.registry import ToolRegistry
from generative_ai_toolkit.conversation_history import DynamoDbConversationHistory
from generative_ai_toolkit.tracer import HumanReadableTracer, TeeTracer
from generative_ai_toolkit.tracer.dynamodb import DynamoDbTracer
from generative_ai_toolkit.ui import chat_ui

import tools
from tools.registries import (
    local_files,
    thinking,
    web_research,
)

ToolRegistry.recursive_import(tools)

# Pick one of the LLMs from this list: https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
# For example:
model_id = "eu.mistral.pixtral-large-2502-v1:0"
model_id = "eu.anthropic.claude-sonnet-4-20250514-v1:0"

# Not all model ids support streaming responses with tools.
# If that's the case for the model id you picked, set the following to "converse":
converse_implementation: Literal["converse", "converse-stream"] = "converse-stream"

cwd = os.getcwd()
is_git_repo = os.path.isdir(os.path.join(cwd, ".git"))
boto_session = boto3.Session()
bedrock_client = boto_session.client(
    "bedrock-runtime",
    config=Config(
        read_timeout=120,  # Default is 60, which can be a tad short for LLM responses
        tcp_keepalive=True,
        retries={"mode": "adaptive", "total_max_attempts": 10},
    ),
)


def tracer(identifier: str):
    return (
        TeeTracer()
        .add_tracer(
            DynamoDbTracer(
                table_name="research-agent",
                identifier=identifier,
                session=boto_session,
            )
        )
        .add_tracer(HumanReadableTracer(snapshot_enabled=True))
    )


def conversation_history(identifier: str):
    return DynamoDbConversationHistory(
        table_name="research-agent", identifier=identifier, session=boto_session
    )


def agent():
    orchestrator_agent = BedrockConverseAgent(
        # model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        model_id=model_id,
        system_prompt=textwrap.dedent(
            """
            You are an advanced AI agent. You help the user with:
            
            - Internet research
            - Accessing local files
            - General questions

            Use the tools at your disposal to do your job.

            It's usually best to confirm your answers are up-to-date by using the Web Research Agent. Answer questions that you know an up-to-date answer to straight away.

            The current date is: {date}

            The user's platform is Mac OS 15.5.

            ### Using the local files agent

            NEVER assume the user wants you to write files! It is more likely they want to see your proposal first, before writing to disk.
            ONLY ask the local files agent to write files if instructed by the user **explicitly**, i.e. when they use the phrases "write to file" or "create a file", or say "yes" when you ask them if you should write the file(s).

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
        .strip()
        .format(
            date=datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
        ),
        tools=thinking,
        converse_implementation=converse_implementation,
        tracer=tracer("supervisor"),
        conversation_history=conversation_history("supervisor"),
        bedrock_client=bedrock_client,
    )
    orchestrator_agent.set_trace_context(
        resource_attributes={"service.name": "ResearchAgent"}
    )

    web_research_agent = BedrockConverseAgent(
        # model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        model_id=model_id,
        system_prompt=textwrap.dedent(
            """
            You are an advanced Web Research Agent with capabilities for intelligent web searching and document analysis. Your primary goal is to provide comprehensive, accurate, and up-to-date information through efficient parallel research strategies.

            The current date is: {date}

            The user's platform is Mac OS 15.5.

            ## Core Capabilities
            - Execute multiple web searches simultaneously
            - Fetch and analyze web documents in parallel
            - Synthesize information from diverse sources
            - Provide structured, well-sourced responses
            - Read file from Github repositories, including Pull Requests

            ## Fetching Web pages
            - For each web search result, fetch at least the top 2 web pages.
            - Do this in parallel, for example if you have 3 web search results, you would execute 3 * 2 = 6 fetches
            """
        )
        .strip()
        .format(
            date=datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
        ),
        tools=web_research,
        name="transfer_to_web_research_agent",
        description="Hand-off an inquiry to the Web Research Agent. The web research agent can also access GitHub: access files there and retrieve Pull Request (PR) information",
        input_schema={
            "type": "object",
            "properties": {
                "inquiry_description": {
                    "type": "string",
                    "description": "A detailed description of what the user wants to know, and hopes to find the answer for on the web",
                },
            },
            "required": ["inquiry_description"],
        },
        converse_implementation=converse_implementation,
        tracer=tracer("web-research"),
        conversation_history=conversation_history("web-research"),
        bedrock_client=bedrock_client,
    )

    local_files_agent = BedrockConverseAgent(
        # model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        model_id=model_id,
        system_prompt=textwrap.dedent(
            """
            You are an advanced AI agent for reading and editing local files.

            If you are asked for the contents of a file, return the raw contents as-is.
            If the user is specific about what they want to know about a file; return only that.
            If you're unsure wether the user wants the raw contents, a summary/description, or something specific: ask what they want explicitly.

            The current local working directory is: {cwd}{git_dir}
            """
        )
        .strip()
        .format(
            cwd=os.getcwd(),
            git_dir=" (a git tracked dir)" if is_git_repo else "",
        ),
        tools=local_files,
        name="transfer_to_local_files_agent",
        description=textwrap.dedent(
            """
            Hand-off a task to the local files agent. The local files agents can read, create and update files.
            When asking to read files, if you can, be specific about what you want to know, so the agent doesn't have to return you the full contents of the file.
            """
        ),
        converse_implementation=converse_implementation,
        tracer=tracer("local-files"),
        conversation_history=conversation_history("local-files"),
        bedrock_client=bedrock_client,
    )

    orchestrator_agent.register_tool(web_research_agent)
    orchestrator_agent.register_tool(local_files_agent)

    return orchestrator_agent


if __name__ == "__main__":

    demo = chat_ui(agent)
    demo.queue(default_concurrency_limit=5).launch(inbrowser=True)

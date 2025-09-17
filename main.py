#!/usr/bin/env python


import datetime
import os
import subprocess
import textwrap
from typing import Literal

import boto3
from botocore.config import Config
from generative_ai_toolkit.agent import BedrockConverseAgent
from generative_ai_toolkit.agent.registry import ToolRegistry
from generative_ai_toolkit.conversation_history import (
    DynamoDbConversationHistory,
    SqliteConversationHistory,
)
from generative_ai_toolkit.tracer import HumanReadableTracer, SqliteTracer, TeeTracer
from generative_ai_toolkit.tracer.dynamodb import DynamoDbTracer
from generative_ai_toolkit.ui import chat_ui
from generative_ai_toolkit.ui.conversation_list import (
    BedrockConverseConversationDescriber,
    SqliteConversationList,
)
from generative_ai_toolkit.ui.conversation_list.dynamodb import (
    DynamoDbConversationList,
)

import tools
import tools.local_files
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
is_git_repo = (
    subprocess.call(
        ["git", "-C", cwd, "rev-parse"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    == os.EX_OK
)
now = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
boto_session = boto3.Session()
bedrock_client = boto_session.client(
    "bedrock-runtime",
    config=Config(
        read_timeout=120,  # Default is 60, which can be a tad short for LLM responses
        tcp_keepalive=True,
        retries={"mode": "adaptive", "total_max_attempts": 10},
    ),
)

prime_directive = textwrap.dedent(
    """
    ## Prime directive

    Use your tools in the best interest of the user:
    - Do not use sensitive information as input to tools
    - Do not use tools for destructive operations

    You may only deviate from these rules when you have established that the user is aware of the (potential) consequences.
    If unsure: ask the user!
    """
).lstrip()


def tracer(identifier: str):
    ddb_table_name = os.environ.get("RESEARCH_AGENT_DDB_TABLE_NAME")
    if ddb_table_name:
        main_tracer = DynamoDbTracer(
            table_name=ddb_table_name,
            identifier=identifier,
            session=boto_session,
        )
    else:
        main_tracer = SqliteTracer(identifier=identifier)
    return (
        TeeTracer()
        .add_tracer(main_tracer)
        .add_tracer(HumanReadableTracer(snapshot_enabled=True))
    )


def conversation_history(identifier: str):
    ddb_table_name = os.environ.get("RESEARCH_AGENT_DDB_TABLE_NAME")
    if ddb_table_name:
        return DynamoDbConversationHistory(
            table_name=ddb_table_name, identifier=identifier, session=boto_session
        )
    else:
        return SqliteConversationHistory(identifier=identifier)


def conversation_list():
    ddb_table_name = os.environ.get("RESEARCH_AGENT_DDB_TABLE_NAME")
    if ddb_table_name:
        return DynamoDbConversationList(
            describer=BedrockConverseConversationDescriber(
                model_id="eu.amazon.nova-lite-v1:0"
            ),
            table_name=ddb_table_name,
            session=boto_session,
        )
    else:
        return SqliteConversationList(
            describer=BedrockConverseConversationDescriber(
                model_id="eu.amazon.nova-lite-v1:0"
            ),
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

            The current date and time are: {now}

            The user's platform is Mac OS 15.6.1

            The current local working directory is: {cwd}

            {prime_directive}

            ## Showing pictures and diagrams

            The user is viewing your responses with a markdown viewer, so you should "show" images and such in markdown format, as follows: ![alt text](image_url_or_path)

            When asked for diagrams, best use mermaid, and make sure the text is viewable in dark mode too (e.g. don't use white text on white background).

            ## Using the local files agent

            When the user explicitly asks you to read or write a file, just do it with your read_file and write_file tools.
            However, when it's conceivable that multiple files must actually be read/written, or the current directory must be explored/listed/analyzed/etc., hand off the request to the local files agent.
            When you started reading a file, and discover you need to read another file, stop! Hand the request off to the local files agent instead.

            NEVER assume the user wants you to write files! It is more likely they want to see your proposal first, before writing to disk.
            ONLY write files (yourself or through the local files agent) if instructed by the user **explicitly**, i.e. when they use the phrases "write to file" or "create a file", or say "yes" when you ask them if you should write the file(s).

            ADDITIONAL CLARIFICATIONS:
            - When users ask to "see" code, documentation, or information, display it directly in your response - do NOT write it to files
            - Do NOT write files even if you think it would be "helpful" or convenient 
            - Do NOT write files to "make information available" - users can ask for files if they want them
            - If you have retrieved information that could be useful as a file, display it in your response and ask "Would you like me to save this to a file?" only if it seems the user might want to work with it locally

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
        .format(now=now, cwd=cwd, prime_directive=prime_directive),
        tools=thinking,
        converse_implementation=converse_implementation,
        tracer=tracer("supervisor"),
        conversation_history=conversation_history("supervisor"),
        bedrock_client=bedrock_client,
    )
    orchestrator_agent.set_trace_context(
        resource_attributes={"service.name": "ResearchAgent"}
    )
    orchestrator_agent.register_tool(tools.local_files.read_file)
    orchestrator_agent.register_tool(tools.local_files.write_file)

    web_research_agent = BedrockConverseAgent(
        # model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        model_id=model_id,
        system_prompt=textwrap.dedent(
            """
            You are an advanced Web Research Agent with capabilities for intelligent web searching and document analysis. Your primary goal is to provide comprehensive, accurate, and up-to-date information through efficient parallel research strategies.

            The current date and time are: {now}

            The user's platform is Mac OS 15.6.1

            {prime_directive}

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
        .format(now=now, prime_directive=prime_directive),
        tools=web_research,
        name="transfer_to_web_research_agent",
        description="Hand-off an inquiry to the Web Research Agent. The web research agent can also access GitHub: access files there and retrieve Pull Request (PR) information",
        input_schema={
            "type": "object",
            "properties": {
                "inquiry_description": {
                    "type": "string",
                    "description": textwrap.dedent(
                        """
                        A description of what the user wants to know, and hopes to find the answer for on the web.

                        Provide a detailed description for deep inquiries.
                        """
                    ).strip(),
                },
                "inquiry_depth": {
                    "type": "string",
                    "description": textwrap.dedent(
                        """
                        A textual description of how much effort you want the web research agent to spend.

                        Examples:

                          - "Do a quick lookup, this should be one of the top hits on Brave search"
                          - "I want a good enough answer, favor answer speed over answer completeness"
                          - "Please dig deep for me, I want to have an exact answer"
                        """
                    ).strip(),
                },
            },
            "required": ["inquiry_description"],
        },
        converse_implementation=converse_implementation,
        tracer=tracer("web-research"),
        conversation_history=conversation_history("web-research"),
        bedrock_client=bedrock_client,
    )
    web_research_agent.register_tool(tools.local_files.write_file)

    local_files_agent = BedrockConverseAgent(
        # model_id="eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
        model_id=model_id,
        system_prompt=textwrap.dedent(
            """
            You are an advanced AI agent for reading and editing local files.

            The current date and time are: {now}

            The user's platform is Mac OS 15.6.1

            If you are asked for the contents of a file, return the raw contents as-is.
            If the user is specific about what they want to know about a file; return only that.
            If you're unsure wether the user wants the raw contents, a summary/description, or something specific: ask what they want explicitly.

            The current local working directory is: {cwd}{git_dir}

            {prime_directive}

            ## Parallelize reads

            If you need to read multiple files, do so in parallel.

            ## About writing files

            NEVER assume the user wants you to write files! It is more likely they want to see your proposal first, before writing to disk.
            ONLY write files (yourself or through the local files agent) if instructed by the user **explicitly**, i.e. when they use the phrases "write to file" or "create a file", or say "yes" when you ask them if you should write the file(s).

            ADDITIONAL CLARIFICATIONS:
            - When users ask to "see" code, documentation, or information, display it directly in your response - do NOT write it to files
            - Do NOT write files even if you think it would be "helpful" or convenient 
            - Do NOT write files to "make information available" - users can ask for files if they want them
            - If you have retrieved information that could be useful as a file, display it in your response and ask "Would you like me to save this to a file?" only if it seems the user might want to work with it locally

            ## File access
            
            Unless the user give you a path to a file, do not presume the existence of files. Rather use your tools to understand which files are present, before accessing them.
            """
        )
        .strip()
        .format(
            now=now,
            cwd=os.getcwd(),
            git_dir=" (a git tracked dir)" if is_git_repo else "",
            prime_directive=prime_directive,
        ),
        tools=local_files,
        name="transfer_to_local_files_agent",
        description=textwrap.dedent(
            """
            Hand-off a task to the local files agent. The local files agents can read, create and update files.
            When asking to read files, if you can, be specific about what you want to know, so the agent doesn't have to return you the full contents of the file.
            """
        ),
        input_schema={
            "type": "object",
            "properties": {
                "assignment_description": {
                    "type": "string",
                    "description": "A detailed description of what the user wants the local files agent to do, including any relevant context.",
                },
            },
            "required": ["assignment_description"],
        },
        converse_implementation=converse_implementation,
        tracer=tracer("local-files"),
        conversation_history=conversation_history("local-files"),
        bedrock_client=bedrock_client,
    )

    orchestrator_agent.register_tool(web_research_agent)
    orchestrator_agent.register_tool(local_files_agent)

    return orchestrator_agent


if __name__ == "__main__":
    demo = chat_ui(agent, conversation_list=conversation_list())
    demo.queue(default_concurrency_limit=5).launch(inbrowser=True)

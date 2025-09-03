# AI-powered Research Assistant

Kinda like OpenAI's Deep Research, but way simpler, and your own. Also enhanced with local filesystem access.

Built with [Generative AI Toolkit](https://github.com/awslabs/generative-ai-toolkit/).

## Example Use Cases

- Compare features of different AI frameworks or libraries
- Research technical topics with information from multiple sources
- Explore GitHub repositories without leaving your terminal
- Analyze and extract key information from technical documentation
- Generate reports based on internet research

## Requirements

- Python 3.13+
- [Uv](https://github.com/astral-sh/uv) (Python package installer, recommended)
- AWS Bedrock access (for Claude 3.7 Sonnet)
- AWS credentials properly configured
- Brave Search API key (you can use the default Brave search plan, which requires a CC registered but is free of charge)
- GutHub token

## Installation

```shell
# Clone this repository
git clone git@ssh.gitlab.aws.dev:ottokrus/research-agent.git
cd research-agent

# Create a virtual env
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

## Environment

Populate your Brave Search API key and GitHub token into the environment:

```shell
export BRAVE_SEARCH_API_KEY=your_brave_search_api_key_here
export GITHUB_TOKEN=your_github_token_here
```

## Usage

```shell
# Ensure you have valid AWS credentials in the usual place where boto3 can find them, for example:
isengardcli assume

# Run the research agent
uv run python main.py
```

That will spawn a web ui (see screenshot below) and open your browser so you can enter your questions or research tasks.

## Shell alias

Add this to your .zshrc so you can quickly spawn the UI with `qq`:

```shell
alias qq="AWS_PROFILE=<isengardprofile> AWS_ACCESS_KEY_ID= AWS_SECRET_ACCESS_KEY= AWS_SESSION_TOKEN= GITHUB_TOKEN=<token> BRAVE_SEARCH_API_KEY=<key> /<path>/<to>/research-agent/main.sh"
```

## UI Screenshot

![UI Screenshot](https://raw.githubusercontent.com/awslabs/generative-ai-toolkit/main/assets/images/ui-chat.png)


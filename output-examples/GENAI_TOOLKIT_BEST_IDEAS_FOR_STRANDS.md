# Best Ideas in Generative AI Toolkit to Consider Adopting in Strands

## Introduction

AWS has developed two key frameworks for building AI agents: Strands Agent SDK (officially supported) and Generative AI Toolkit (created by AWS Solution Architects). While both libraries serve the purpose of building AI agents, the Generative AI Toolkit introduces several innovative concepts that could enhance the capabilities of Strands. This report identifies the five most valuable concepts from the Generative AI Toolkit that the Strands team should consider adopting.

## 1. Traces as the Central Foundation for Evaluation

### Overview

While Strands does include a comprehensive tracing system with OpenTelemetry integration, the Generative AI Toolkit elevates traces to a more central role. In the Generative AI Toolkit, traces aren't just for observability—they are the foundation upon which all evaluation, testing, and metrics are built. This "traces-first" approach means that any aspect of agent behavior that's captured in traces can be evaluated, measured, and tested against.

### Code Example

```python
from generative_ai_toolkit.agent import BedrockConverseAgent
from generative_ai_toolkit.tracer import InMemoryTracer

# Create agent with tracing enabled
agent = BedrockConverseAgent(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    tracer=InMemoryTracer,  # Enable tracing
)

def get_weather(city: str) -> str:
    """Gets the weather for a city"""
    return f"It's sunny in {city}"

agent.register_tool(get_weather)

# Interact with the agent
response = agent.converse("What's the weather in Seattle?")

# Access the complete trace of what happened
for trace in agent.traces:
    print(trace.as_human_readable())
```

The traces collected can then be directly used for evaluation:

```python
from generative_ai_toolkit.evaluate.interactive import GenerativeAIToolkit
from generative_ai_toolkit.metrics.modules.latency import LatencyMetric

# Evaluate the traces with metrics
results = GenerativeAIToolkit.eval(
    metrics=[LatencyMetric()],
    traces=[agent.traces]  # Pass traces directly to evaluation
)
```

### Benefits for Strands

1. **Unified Data Model**: One consistent data structure (traces) powers debugging, testing, and metrics.

2. **Full Context for Evaluation**: Metrics and tests can access the complete context of agent execution.

3. **White-Box Testing**: Instead of just testing that the agent produces the correct response (black-box), developers can test the internal execution path (white-box) - did the agent invoke the right tool with the right parameters?

4. **Production-Time Evaluation**: Traces collected in production can be evaluated with the same metrics used during development, enabling continuous quality monitoring.

## 2. Parameter Permutation for Comprehensive Testing

### Overview

One of the most innovative features in the Generative AI Toolkit is its parameter permutation capability. This allows developers to test multiple configurations simultaneously by defining parameter sets to permute across. For example, you can test different system prompts, model providers, and temperature values in all possible combinations.

### Code Example

```python
from generative_ai_toolkit.evaluate.interactive import GenerativeAIToolkit, Permute
from generative_ai_toolkit.agent import BedrockConverseAgent
from generative_ai_toolkit.test import Case

# Define test cases
test_case = Case(
    name="Weather query",
    user_inputs=["What's the weather in Seattle?"]
)

# Generate traces with parameter permutations
traces = GenerativeAIToolkit.generate_traces(
    cases=[test_case],
    nr_runs_per_case=2,  # Run each permutation twice
    agent_factory=BedrockConverseAgent,
    agent_parameters={
        # Try different system prompts
        "system_prompt": Permute([
            "You are a helpful weather assistant.",
            "You are a concise weather assistant that keeps responses brief."
        ]),
        # Try different models
        "model_id": Permute([
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0"
        ]),
        # Try different temperature settings
        "temperature": Permute([0.0, 0.7]),
        # Fixed parameters
        "tools": [get_weather_tool]
    }
)

# This will generate 8 different configurations (2×2×2) and run each twice
# for a total of 16 trace sets
```

### Benefits for Strands

1. **Automated Parameter Tuning**: Easily identify the best combination of parameters for your agent.

2. **Comprehensive Testing**: Test all combinations of relevant parameters instead of testing one at a time.

3. **Model Comparison**: Directly compare different model providers or versions using the same test cases.

4. **Cost/Performance Optimization**: Find the optimal balance between model cost and performance.

5. **Efficient Experimentation**: Run dozens or hundreds of experiments with minimal code.

## 3. Reusable Metrics Framework

### Overview

The Generative AI Toolkit introduces a sophisticated metrics framework based on traces. It not only includes out-of-the-box metrics but provides an extensible framework for creating custom metrics that can evaluate any aspect of the agent's behavior captured in traces.

### Code Example

```python
from generative_ai_toolkit.metrics import BaseMetric, Measurement, Unit

# Define a custom metric for measuring tool usage efficiency
class ToolEfficiencyMetric(BaseMetric):
    def evaluate_conversation(self, conversation_traces, **kwargs):
        tool_invocations = [
            trace for trace in conversation_traces 
            if trace.attributes.get("ai.trace.type") == "tool-invocation"
        ]
        
        if not tool_invocations:
            return None
        
        # Calculate how many tool invocations were successful
        successful = sum(1 for t in tool_invocations if "ai.tool.error" not in t.attributes)
        success_rate = successful / len(tool_invocations) if tool_invocations else 0
        
        return Measurement(
            name="ToolEfficiency",
            value=success_rate,
            unit=Unit.Ratio,
            validation_passed=success_rate > 0.9,  # Fail if success rate below 90%
            additional_info={
                "total_invocations": len(tool_invocations),
                "successful_invocations": successful
            }
        )

# Using the custom metric along with built-in metrics
from generative_ai_toolkit.evaluate.interactive import GenerativeAIToolkit
from generative_ai_toolkit.metrics.modules.latency import LatencyMetric
from generative_ai_toolkit.metrics.modules.cost import CostMetric

results = GenerativeAIToolkit.eval(
    metrics=[ToolEfficiencyMetric(), LatencyMetric(), CostMetric(pricing_config)],
    traces=[agent.traces]
)

# View summary of metrics
results.summary()
```

### Benefits for Strands

1. **Standardized Evaluation**: Creates a consistent way to evaluate agent performance across different deployment environments.

2. **Automated Quality Gates**: Metrics can be used to automatically approve or reject agent updates based on performance thresholds.

3. **Business and Technical Metrics**: The framework accommodates both technical metrics (latency, token count) and business-relevant metrics (response quality, task completion).

4. **Pass/Fail Validation**: Each metric can include a validation check that determines if the agent meets the required standard.

5. **Comparative Analysis**: Easy comparison of different agent configurations or model versions.

## 4. Repeatable Test Cases with Expectations

### Overview

The Generative AI Toolkit introduces a powerful test case framework that goes beyond simple input/output testing. Test cases can include not only sequences of user inputs but also detailed expectations for each turn and the overall conversation flow. These expectations can be checked automatically against traces.

### Code Example

```python
from generative_ai_toolkit.test import Case
from generative_ai_toolkit.evaluate.interactive import GenerativeAIToolkit
from generative_ai_toolkit.metrics.modules.similarity import AgentResponseSimilarityMetric
from generative_ai_toolkit.metrics.modules.conversation import ConversationExpectationMetric

# Create a case with per-turn expected responses
similarity_case = Case(name="User wants to go to a museum")
similarity_case.add_turn(
    "What can I do in Seattle?",
    [
        "I can suggest some activities in Seattle. What kinds of things are you interested in? And how far are you willing to travel?",
        "Seattle has many attractions. To help you better, could you tell me what types of activities interest you and how far you're willing to go?"
    ],
)
similarity_case.add_turn(
    "I'm interested in museums",
    [
        "How far are you willing to travel to visit a museum?",
        "Great! Seattle has several excellent museums. What's the maximum distance you're willing to travel?"
    ]
)

# Create a case with overall conversation expectations
conv_expectation_case = Case(
    name="Museum recommendation workflow",
    user_inputs=[
        "What can I do in Seattle?",
        "Within 30 minutes driving",
        "I'd like to visit a museum",
    ],
    overall_expectations="""
    The agent should first ask for the user's interests and travel constraints.
    When the user provides only travel constraints, the agent should ask about interests.
    When the user provides interests, the agent should recommend relevant museums within the specified travel time.
    The agent should offer to help with directions or more details about the recommended museums.
    """
)

# Run the cases through an agent and evaluate
traces = similarity_case.run(agent)
results = GenerativeAIToolkit.eval(
    metrics=[
        AgentResponseSimilarityMetric(),  # Evaluates similarity to expected responses
        ConversationExpectationMetric(),  # Evaluates against overall expectations
    ],
    traces=[traces]
)

# View results
results.summary()
```

### Benefits for Strands

1. **Complete Workflow Testing**: Test entire conversation flows instead of just single-turn interactions.

2. **Multiple Acceptable Responses**: Define multiple valid response patterns instead of requiring exact matches.

3. **High-Level Test Specifications**: Use natural language to describe expected conversation flows.

4. **Regression Testing**: Easily detect when changes to prompts or model versions affect agent behavior.

5. **User Experience Alignment**: Test cases can encode the desired user experience, ensuring it stays consistent.

## 5. Mock Testing for LLMs

### Overview

The Generative AI Toolkit provides a powerful mocking framework for testing agents without actually calling LLMs. This allows for deterministic testing of complex agent behaviors, including tool invocations and multi-turn conversations.

### Code Example

```python
from generative_ai_toolkit.test import Expect, Case
from generative_ai_toolkit.test.mock import MockBedrockConverse
from generative_ai_toolkit.agent import BedrockConverseAgent

# Create mock LLM
mock = MockBedrockConverse()

# Create agent with mock
agent = BedrockConverseAgent(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    session=mock.session(),  # Use mock instead of real LLM
)

def weather_tool(city: str) -> str:
    """Get weather for city"""
    return f"Sunny in {city}"

agent.register_tool(weather_tool)

# Configure mock responses
mock.add_output(
    text_output=["Let me check the weather for you."],
    tool_use_output=[{"name": "weather_tool", "input": {"city": "Seattle"}}]
)
mock.add_output(text_output=["It's a beautiful sunny day in Seattle!"])

# Run conversation
Case(["What's the weather in Seattle?"]).run(agent)

# Make assertions about the entire agent behavior
Expect(agent.traces).user_input.to_include("weather in Seattle")
Expect(agent.traces).tool_invocations.to_include("weather_tool").with_input(
    {"city": "Seattle"}
).with_output("Sunny in Seattle")
Expect(agent.traces).agent_text_response.to_include("beautiful sunny day")
```

### Benefits for Strands

1. **Deterministic Testing**: Test complex agent behaviors without variation from LLM responses.

2. **Fast Tests**: No need to wait for LLM API calls, making tests run much faster.

3. **Complete Control**: Precisely control the LLM's responses, including tool invocations.

4. **Behavior Verification**: Test the entire agent execution path, not just the final output.

5. **CI/CD Ready**: Mock-based tests can run reliably in continuous integration environments.

## Conclusion

The Generative AI Toolkit introduces several powerful concepts that could significantly enhance Strands' capabilities, particularly in the areas of testing, evaluation, and observability. By adopting these ideas, the Strands team can:

1. Elevate traces from an observability feature to the foundation of testing and evaluation
2. Enable comprehensive testing through parameter permutations
3. Establish standardized metrics and quality gates for agent performance
4. Create more sophisticated test cases with multiple acceptable responses
5. Support deterministic testing with LLM mocking

These enhancements would position Strands as a more comprehensive agent development framework while maintaining its existing strengths in simplicity and flexibility.
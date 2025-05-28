# Best ideas in Generative AI Toolkit to consider adopting in Strands

AWS recently launched the Strands Agent SDK as officially supported open source library. Some time earlier, a group of AWS Solution Architects open sourced Generative AI Toolkit (on awslabs: "generative-ai-toolkit") that has some overlap with Strands.

I want you to determine what are the 5 best "ideas" of the Generative AI Toolkit, that the Strands team should consider adopting also. I want you to write a report in markdown format on this. For each idea, include a code sample of how that works in the Generative AI Toolkit, so the strands developers can more easily understand what you mean. Make sure the benefit to users of the library are clear too.

This is how you must work to produce the report:

1. Research both repositories on GitHub, and follow relevant links to examples and documentation.
2. Tell the user which pages you have read
3. ALWAYS ask if the user thinks you have enough information to create your report
4. If the user confirms you have enough information: write your report to disk

I am one of the main developers of the Generative AI toolkit. A hint I will give you already, is that the Generative AI Toolkit puts the concept of traces front and central. Evaluation and testing are based on these traces, and therefore allow for "white box" inspection: it allows you to test that the agent's response is correct, but also how it got to the response: which tools did it invoke, etc. And because traces are collected by agents in production too, the Generative AI toolkit evaluation can work on those traces too––i.e. agent evaluation is not just a development-time only thing (this is the DynamoDB stream example mentioned in their README).

Note that both libraries are new, and there are no good comparisons yet; it won't help you to web search for their differences, you'll have to come up with it yourself by comparing their docs. Be vigilant against "marketing fluff" in their docs that may advertise capabilities broadly. Draw only conclusions about capabilities from the code samples in the documentation.
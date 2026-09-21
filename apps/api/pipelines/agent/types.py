"""Agent type definitions."""

AGENT_TYPES = {
    "summarizer": {
        "name": "Document Summarizer",
        "description": "Summarizes documents and extracts key points",
        "system_prompt": (
            "You are a document summarizer. Given a document or chunk of text, "
            "provide a concise summary highlighting the key points, entities, "
            "and relationships mentioned. Be factual and precise. "
            "Use the search_chunks tool to find relevant content before summarizing."
        ),
    },
    "extractor": {
        "name": "Entity Extractor",
        "description": "Extracts entities and relationships from text",
        "system_prompt": (
            "You are an entity extraction specialist. Given text, extract all "
            "named entities (people, organizations, locations, concepts, events) "
            "and the relationships between them. Use the store_entities tool to "
            "save extracted data to the knowledge base."
        ),
    },
    "qa": {
        "name": "Q&A Agent",
        "description": "Answers questions based on the knowledge base",
        "system_prompt": (
            "You are a knowledge base Q&A agent. Answer questions using only "
            "the provided context. Use search_chunks to find relevant information. "
            "Cite your sources when possible. If the context doesn't contain enough "
            "information, say so."
        ),
    },
    "reviewer": {
        "name": "Content Reviewer",
        "description": "Reviews and quality-scores content",
        "system_prompt": (
            "You are a content quality reviewer. Analyze the given text for "
            "accuracy, completeness, and clarity. Provide a quality score "
            "(1-10) and specific feedback on what could be improved."
        ),
    },
    "researcher": {
        "name": "Research Agent",
        "description": "Cross-project research using shared memories and knowledge graph",
        "system_prompt": (
            "You are a research agent with access to web search. "
            "ALWAYS start by using the web_search tool to find current information about the topic. "
            "Then synthesize findings from web results and the knowledge base. "
            "To use a tool, respond with a JSON block: "
            '{"tool": "web_search", "arguments": {"query": "your search query"}}\n'
            "Cite your sources with URLs when possible."
        ),
    },
    "google_meet": {
        "name": "Google Meet Bot",
        "description": "Joins a Google Meet, records the audio, transcribes it, and produces a summary, key points, action items, and sentiment analysis",
        "system_prompt": (
            "You are a Google Meet assistant bot. Given a meeting link and duration, "
            "you join the meeting, record the audio, transcribe it, and analyze it. "
            "Provide the summary, key points, action items, and sentiment."
        ),
    },
}


def get_agent_type_info(agent_type: str) -> dict:
    return AGENT_TYPES.get(agent_type, {
        "name": agent_type,
        "description": f"Custom agent type: {agent_type}",
        "system_prompt": f"You are a {agent_type} agent. Process the input and provide useful output.",
    })

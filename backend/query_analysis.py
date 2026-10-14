def analyze_query(question):
    # Normalize whitespace for searching.
    # The original question remains unchanged in graph state.
    search_query = " ".join(question.split())

    # Normalize only for greeting detection.
    greeting_text = search_query.casefold().strip(" .!?")

    greetings = {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    }

    if greeting_text in greetings:
        return {
            "intent": "greeting",
            "route": "direct",
            "search_query": search_query,
        }

    return {
        "intent": "document_question",
        "route": "retrieve",
        "search_query": search_query,
    }
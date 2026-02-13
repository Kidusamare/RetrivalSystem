from project_enterprise_rag.rag.query_engine import (
    get_query_engine,
    query_with_groq,
)

if __name__ == "__main__":
    print("Loading retriever...")
    retriever = get_query_engine("project_enterprise_rag/storage")

    query = "What is Generative AI?"
    print(f"\nQuery: {query}\n")

    response = query_with_groq(retriever, query)

    print("----- RESPONSE -----")
    print(response)

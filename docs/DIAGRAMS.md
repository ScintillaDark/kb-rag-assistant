# System Diagrams

This document describes the KnowledgeBase Assistant with diagrams for architecture, ingestion, retrieval, deployment, and request handling.

## Component architecture

```mermaid
flowchart LR
    User[User] --> UI[Streamlit chat UI]
    UI -->|Bearer-authenticated NDJSON| API[FastAPI runtime]
    API --> Guardrail{Optional scope guardrail}
    Guardrail --> RAG[RAG service]
    RAG --> Embed[Sentence-transformers]
    Embed --> FAISS[(FAISS index)]
    RAG -->|Grounded prompt| Ollama[Ollama model]
    RAG -->|Weak evidence only| Web[Optional web search]
    Web --> Ollama
    Ollama -->|Tokens| API
    API -->|Citations and metadata| UI

    subgraph Build-time ingestion
        Source[Documentation site or Markdown] --> Crawler[Discovery, crawl, extraction]
        Crawler --> Chunker[Heading-aware chunking]
        Chunker --> Indexer[Embeddings and FAISS build]
    end

    Indexer --> FAISS
```

## Ingestion flow

```mermaid
flowchart TD
    Start([Start]) --> Input{Input source}
    Input -->|Website| Discover[Discover URLs]
    Discover --> Robots[Check robots.txt policy]
    Robots -->|Allowed| Crawl[Crawl HTML]
    Robots -->|Unavailable or disallowed| Stop[Fail closed]
    Crawl --> Extract[Extract article content]
    Input -->|Markdown folder| Read[Read Markdown files]
    Extract --> Articles[(data/clean/articles.jsonl)]
    Read --> Articles
    Articles --> Split[Split by headings]
    Split --> Chunk[Create 550-token chunks with 100-token overlap]
    Chunk --> Embed[Generate normalized sentence embeddings]
    Embed --> Build[Index vectors in FAISS IndexFlatIP]
    Build --> Files[(FAISS, chunks, embeddings)]
    Files --> Manifest[Write manifest and SHA-256 checksums]
    Manifest --> Ready([Index ready])
    Stop --> End([End])
```

## Chat request sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit UI
    participant API as FastAPI
    participant Guard as Scope guardrail
    participant RAG as RAG service
    participant FAISS as FAISS index
    participant Ollama

    User->>UI: Ask question
    UI->>API: POST /chat/stream with bearer key
    API->>API: Validate key and rate limit
    API->>API: Acquire generation slot
    alt Guardrail enabled
        API->>Guard: Classify question
        Guard-->>API: Allow or reject
    end
    alt Rejected
        API-->>UI: Rejection token and meta event
    else Allowed
        API->>RAG: Answer stream
        RAG->>RAG: Check response cache
        RAG->>RAG: Embed question
        RAG->>FAISS: Search top-k vectors
        FAISS-->>RAG: Ranked chunks
        RAG->>RAG: Apply score and source thresholds
        alt Evidence sufficient
            RAG->>Ollama: Stream grounded prompt
            Ollama-->>RAG: Generated tokens
        else Evidence weak and web search enabled
            RAG->>Ollama: Prompt from web results
            Ollama-->>RAG: Generated tokens
        else Insufficient evidence
            RAG-->>API: Abstention response
        end
        RAG-->>API: Token and final meta events
        API-->>UI: NDJSON stream
    end
    UI-->>User: Answer and citations
```

## RAG activity

```mermaid
flowchart TD
    Question([Question]) --> Ambiguous{Ambiguity check}
    Ambiguous -->|Ambiguous| Clarify[Generate clarifying questions]
    Clarify --> StopClarify([Ask for clarification])
    Ambiguous -->|Not ambiguous| Cache{Cached response?}
    Cache -->|Hit| Cached([Return cached response])
    Cache -->|Miss| Embed[Embed question]
    Embed --> Search[Search FAISS]
    Search --> Scores[Filter hits by similarity]
    Scores --> Evidence{Enough score and sources?}
    Evidence -->|Yes| PromptKB[Build knowledge-base prompt]
    PromptKB --> Generate[Generate with Ollama]
    Evidence -->|No and web search enabled| SearchWeb[Search configured provider]
    SearchWeb --> WebEvidence{Results found?}
    WebEvidence -->|Yes| PromptWeb[Build web-evidence prompt]
    PromptWeb --> Generate
    WebEvidence -->|No| Abstain[Abstain]
    Evidence -->|No| Abstain
    Generate --> Clean[Clean answer text]
    Clean --> Citations[Resolve KB or web citations]
    Citations --> Options[Generate follow-up options]
    Options --> StoreCache[Store response in memory]
    StoreCache --> Return([Return streamed response])
    Abstain --> Return
```

## Deployment

```mermaid
flowchart TB
    subgraph Host["Host loopback network"]
        Browser[Browser]
        UI[Streamlit container :8501]
        API[FastAPI container :8000]
        Ollama[Ollama container :11434]
        Data[(./data volume)]
        OllamaData[(Ollama named volume)]
    end

    Browser -->|HTTP| UI
    UI -->|Bearer token| API
    API -->|Generate and tags APIs| Ollama
    API --> Data
    Ollama --> OllamaData

    style Host stroke:#666,stroke-width:2px
```

Ports are bound to `127.0.0.1` by default. Public exposure requires TLS, authentication, authorization, durable limits, and deployment-specific monitoring.

## Data model

```mermaid
erDiagram
    ARTICLES ||--o{ CHUNKS : produces
    CHUNKS ||--|| EMBEDDINGS : represented_by
    INDEX_MANIFEST ||--|{ INDEX_ARTIFACT : checks

    ARTICLES {
        string article_id
        string title
        string url
        string text
        string content_hash
    }

    CHUNKS {
        string chunk_id
        string article_id
        string title
        string url
        string heading_path
        string text
        integer token_count
    }

    EMBEDDINGS {
        string chunk_id
        float vector
    }

    INDEX_MANIFEST {
        integer index_version
        string embedding_model
        integer total_articles
        integer total_chunks
        integer chunk_tokens
        integer overlap_tokens
        string faiss_metric
        string index_id
    }

    INDEX_ARTIFACT {
        string filename
        string sha256
    }
```

## Service state

```mermaid
stateDiagram-v2
    [*] --> Starting
    Starting --> NotReady: index or API key missing
    Starting --> Ready: index and Ollama model available
    NotReady --> Starting: configuration fixed and service restarted
    Ready --> Serving
    Serving --> CapacityBusy: generation slots exhausted
    CapacityBusy --> Serving: slot released
    Serving --> RatedLimited: caller exceeds per-minute limit
    RatedLimited --> Serving: next minute window
    Serving --> [*]: stopped

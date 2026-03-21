using System.Text.Json.Serialization;

namespace AgenticAI.Client;

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

/// <summary>
/// Response from GET /health.
/// </summary>
/// <param name="Status">Operational status string, e.g. "ok".</param>
/// <param name="Version">Server semantic version string, e.g. "0.4.0".</param>
public sealed record HealthResponse(
    [property: JsonPropertyName("status")]  string Status,
    [property: JsonPropertyName("version")] string Version
);

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

/// <summary>
/// Response from GET /api/new_chat.
/// </summary>
/// <param name="ChatId">Opaque UUID that identifies the new conversation.</param>
public sealed record NewChatResponse(
    [property: JsonPropertyName("chat_id")] string ChatId
);

/// <summary>
/// Request body for POST /api/chat.
/// </summary>
/// <param name="ChatId">Conversation ID returned by <see cref="NewChatResponse"/>.</param>
/// <param name="Message">The user message to send.</param>
public sealed record ChatRequest(
    [property: JsonPropertyName("chat_id")] string ChatId,
    [property: JsonPropertyName("message")] string Message
);

/// <summary>
/// A single Server-Sent Event emitted by the /api/chat or /api/rag/ask endpoints.
/// </summary>
/// <param name="Event">
/// The SSE event type.  Common values:
/// <list type="bullet">
///   <item><term>token</term><description>Incremental LLM output token.</description></item>
///   <item><term>done</term><description>Stream completed; <see cref="Data"/> may contain a JSON summary.</description></item>
///   <item><term>error</term><description>Server-side error description.</description></item>
/// </list>
/// </param>
/// <param name="Data">Raw data payload for this event.</param>
public sealed record SseEvent(string Event, string Data);

/// <summary>
/// Parsed JSON payload delivered in the final <c>done</c> SSE event of a chat stream.
/// </summary>
/// <param name="ChatId">The conversation ID echoed back by the server.</param>
public sealed record ChatDonePayload(
    [property: JsonPropertyName("chat_id")] string? ChatId
);

// ---------------------------------------------------------------------------
// Ingestion
// ---------------------------------------------------------------------------

/// <summary>
/// Request body for POST /api/ingest.
/// </summary>
/// <param name="Text">Raw text content to index into the knowledge base.</param>
/// <param name="Metadata">Optional key-value metadata attached to the document.</param>
public sealed record IngestTextRequest(
    [property: JsonPropertyName("text")]     string Text,
    [property: JsonPropertyName("metadata")] Dictionary<string, object?>? Metadata = null
);

/// <summary>
/// Request body for POST /api/ingest_url.
/// </summary>
/// <param name="Url">Publicly reachable URL whose content the server will fetch and index.</param>
public sealed record IngestUrlRequest(
    [property: JsonPropertyName("url")] string Url
);

/// <summary>
/// Response from POST /api/ingest or POST /api/ingest_url.
/// </summary>
/// <param name="Ok">Indicates whether the operation succeeded.</param>
/// <param name="Id">Opaque identifier assigned to the newly ingested document.</param>
public sealed record IngestResponse(
    [property: JsonPropertyName("ok")] bool   Ok,
    [property: JsonPropertyName("id")] string Id
);

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

/// <summary>
/// Request body for POST /api/feedback.
/// </summary>
/// <param name="ChatId">Conversation being rated.</param>
/// <param name="Rating">Integer rating in the range 1–5.</param>
/// <param name="Comment">Optional free-text comment.</param>
public sealed record FeedbackRequest(
    [property: JsonPropertyName("chat_id")] string  ChatId,
    [property: JsonPropertyName("rating")]  int     Rating,
    [property: JsonPropertyName("comment")] string? Comment = null
);

/// <summary>
/// Response from POST /api/feedback.
/// </summary>
/// <param name="Ok">Indicates whether the feedback was recorded successfully.</param>
public sealed record FeedbackResponse(
    [property: JsonPropertyName("ok")] bool Ok
);

// ---------------------------------------------------------------------------
// RAG
// ---------------------------------------------------------------------------

/// <summary>
/// Response from GET /api/rag/new_session.
/// </summary>
/// <param name="SessionId">Opaque UUID for the new RAG session.</param>
public sealed record RagNewSessionResponse(
    [property: JsonPropertyName("session_id")] string SessionId
);

/// <summary>
/// Request body for POST /api/rag/ask.
/// </summary>
/// <param name="SessionId">RAG session ID returned by <see cref="RagNewSessionResponse"/>.</param>
/// <param name="Question">Natural-language question to answer using the indexed knowledge base.</param>
public sealed record RagAskRequest(
    [property: JsonPropertyName("session_id")] string SessionId,
    [property: JsonPropertyName("question")]   string Question
);

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/// <summary>
/// Thrown when the server returns a non-2xx HTTP status code.
/// </summary>
public sealed class AgenticAIException : Exception
{
    /// <summary>HTTP status code returned by the server.</summary>
    public int StatusCode { get; }

    /// <summary>Raw response body, when available.</summary>
    public string? ResponseBody { get; }

    /// <inheritdoc cref="AgenticAIException"/>
    public AgenticAIException(int statusCode, string? body, string message)
        : base(message)
    {
        StatusCode   = statusCode;
        ResponseBody = body;
    }
}

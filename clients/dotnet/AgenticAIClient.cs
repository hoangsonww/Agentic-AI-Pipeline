using System.Net.Http.Json;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;

namespace AgenticAI.Client;

/// <summary>
/// Options used to configure <see cref="AgenticAIClient"/>.
/// </summary>
public sealed class AgenticAIClientOptions
{
    /// <summary>
    /// Base URL of the Agentic AI server.  Defaults to <c>http://localhost:8000</c>.
    /// </summary>
    public string BaseUrl { get; init; } = "http://localhost:8000";

    /// <summary>
    /// Maximum time to wait for non-streaming HTTP responses.  Defaults to 60 seconds.
    /// </summary>
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(60);

    /// <summary>
    /// Maximum time allocated for a single SSE stream before it is forcibly cancelled.
    /// Defaults to 5 minutes.  Set to <see cref="System.Threading.Timeout.InfiniteTimeSpan"/>
    /// to disable the per-stream timeout.
    /// </summary>
    public TimeSpan StreamTimeout { get; init; } = TimeSpan.FromMinutes(5);
}

/// <summary>
/// Async .NET 8 client for the Agentic AI REST + SSE API.
/// </summary>
/// <remarks>
/// <para>
/// The preferred way to obtain an instance is via <c>IHttpClientFactory</c>:
/// </para>
/// <code>
/// // In Program.cs / Startup:
/// services.AddHttpClient&lt;AgenticAIClient&gt;(c =>
///     c.BaseAddress = new Uri("http://localhost:8000"));
///
/// // In your service:
/// public MyService(AgenticAIClient client) { ... }
/// </code>
/// <para>
/// If you are not using DI, construct the client directly and dispose it when
/// your application exits:
/// </para>
/// <code>
/// await using var client = new AgenticAIClient();
/// </code>
/// </remarks>
public sealed class AgenticAIClient : IAsyncDisposable, IDisposable
{
    // -----------------------------------------------------------------------
    // Fields
    // -----------------------------------------------------------------------

    private readonly HttpClient            _http;
    private readonly AgenticAIClientOptions _opts;
    private readonly bool                  _ownsHttpClient;

    private static readonly JsonSerializerOptions _jsonOpts = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented               = false,
    };

    // -----------------------------------------------------------------------
    // Constructors
    // -----------------------------------------------------------------------

    /// <summary>
    /// Creates a client that manages its own <see cref="HttpClient"/> lifetime.
    /// </summary>
    /// <param name="options">Optional configuration.  Defaults are used when <c>null</c>.</param>
    public AgenticAIClient(AgenticAIClientOptions? options = null)
    {
        _opts           = options ?? new AgenticAIClientOptions();
        _ownsHttpClient = true;
        _http           = BuildHttpClient(_opts);
    }

    /// <summary>
    /// Creates a client that wraps an externally managed <see cref="HttpClient"/>.
    /// Use this overload when integrating with <c>IHttpClientFactory</c>.
    /// </summary>
    /// <param name="httpClient">
    /// Pre-configured <see cref="HttpClient"/>.  The base address should already
    /// be set on the client, otherwise supply <paramref name="options"/>.
    /// </param>
    /// <param name="options">Optional configuration overrides.</param>
    public AgenticAIClient(HttpClient httpClient, AgenticAIClientOptions? options = null)
    {
        _opts           = options ?? new AgenticAIClientOptions();
        _ownsHttpClient = false;
        _http           = httpClient;

        // Apply base address from options only when the caller has not set one.
        if (_http.BaseAddress is null)
            _http.BaseAddress = new Uri(_opts.BaseUrl.TrimEnd('/'));
    }

    // -----------------------------------------------------------------------
    // Health
    // -----------------------------------------------------------------------

    /// <summary>
    /// Checks server availability.
    /// </summary>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Server status and version.</returns>
    /// <exception cref="AgenticAIException">Thrown when the server returns a non-2xx status.</exception>
    public async Task<HealthResponse> GetHealthAsync(CancellationToken ct = default)
    {
        var response = await _http.GetAsync("/health", ct).ConfigureAwait(false);
        return await ReadJsonAsync<HealthResponse>(response, ct).ConfigureAwait(false);
    }

    // -----------------------------------------------------------------------
    // Chat
    // -----------------------------------------------------------------------

    /// <summary>
    /// Allocates a new conversation and returns its ID.
    /// </summary>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Object containing the new <c>chat_id</c>.</returns>
    public async Task<NewChatResponse> NewChatAsync(CancellationToken ct = default)
    {
        var response = await _http.GetAsync("/api/new_chat", ct).ConfigureAwait(false);
        return await ReadJsonAsync<NewChatResponse>(response, ct).ConfigureAwait(false);
    }

    /// <summary>
    /// Sends a message and streams the LLM response token-by-token via SSE.
    /// </summary>
    /// <param name="chatId">Conversation ID from <see cref="NewChatAsync"/>.</param>
    /// <param name="message">User message text.</param>
    /// <param name="ct">Cancellation token.  Cancel to abort the stream early.</param>
    /// <returns>
    /// An <see cref="IAsyncEnumerable{T}"/> of <see cref="SseEvent"/> objects.
    /// Enumerate until you receive an event whose <see cref="SseEvent.Event"/> is
    /// <c>"done"</c> to know the stream has completed.
    /// </returns>
    /// <example>
    /// <code>
    /// await foreach (var evt in client.ChatStreamAsync(chatId, "Summarise ACME Corp"))
    /// {
    ///     if (evt.Event == "token") Console.Write(evt.Data);
    ///     if (evt.Event == "done")  Console.WriteLine("\n[stream finished]");
    /// }
    /// </code>
    /// </example>
    public IAsyncEnumerable<SseEvent> ChatStreamAsync(
        string            chatId,
        string            message,
        CancellationToken ct = default)
    {
        var body = new ChatRequest(chatId, message);
        return StreamSseAsync("/api/chat", body, ct);
    }

    /// <summary>
    /// Convenience overload that sends a message and collects the full response text.
    /// </summary>
    /// <param name="chatId">Conversation ID.</param>
    /// <param name="message">User message.</param>
    /// <param name="onToken">
    /// Optional callback invoked synchronously for every <c>token</c> event so
    /// callers can display incremental output while still awaiting the final result.
    /// </param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>
    /// The concatenated response text plus the echoed <c>chat_id</c>.
    /// </returns>
    public async Task<(string FullText, string ChatId)> ChatAsync(
        string              chatId,
        string              message,
        Action<string>?     onToken = null,
        CancellationToken   ct      = default)
    {
        var sb = new StringBuilder();

        await foreach (var evt in ChatStreamAsync(chatId, message, ct).ConfigureAwait(false))
        {
            if (evt.Event == "token")
            {
                sb.Append(evt.Data);
                onToken?.Invoke(evt.Data);
            }
            else if (evt.Event == "done")
            {
                // The done payload may carry the echoed chat_id.
                string? resolvedId = TryParseChatIdFromDone(evt.Data) ?? chatId;
                return (sb.ToString(), resolvedId);
            }
        }

        return (sb.ToString(), chatId);
    }

    // -----------------------------------------------------------------------
    // Ingestion
    // -----------------------------------------------------------------------

    /// <summary>
    /// Indexes raw text into the server's knowledge base.
    /// </summary>
    /// <param name="text">Document text to ingest.</param>
    /// <param name="metadata">Optional metadata dictionary attached to the document.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Operation result including the assigned document ID.</returns>
    public async Task<IngestResponse> IngestTextAsync(
        string                        text,
        Dictionary<string, object?>?  metadata = null,
        CancellationToken             ct       = default)
    {
        var body     = new IngestTextRequest(text, metadata);
        var response = await PostJsonAsync("/api/ingest", body, ct).ConfigureAwait(false);
        return await ReadJsonAsync<IngestResponse>(response, ct).ConfigureAwait(false);
    }

    /// <summary>
    /// Instructs the server to fetch the given URL and index its content.
    /// </summary>
    /// <param name="url">Publicly accessible URL to ingest.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Operation result including the assigned document ID.</returns>
    public async Task<IngestResponse> IngestUrlAsync(string url, CancellationToken ct = default)
    {
        var body     = new IngestUrlRequest(url);
        var response = await PostJsonAsync("/api/ingest_url", body, ct).ConfigureAwait(false);
        return await ReadJsonAsync<IngestResponse>(response, ct).ConfigureAwait(false);
    }

    // -----------------------------------------------------------------------
    // Feedback
    // -----------------------------------------------------------------------

    /// <summary>
    /// Records user feedback for a completed conversation.
    /// </summary>
    /// <param name="chatId">Conversation to rate.</param>
    /// <param name="rating">Integer score in the range 1–5 (inclusive).</param>
    /// <param name="comment">Optional free-text comment.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Acknowledgement from the server.</returns>
    /// <exception cref="ArgumentOutOfRangeException">
    /// Thrown when <paramref name="rating"/> is outside [1, 5].
    /// </exception>
    public async Task<FeedbackResponse> SendFeedbackAsync(
        string            chatId,
        int               rating,
        string?           comment = null,
        CancellationToken ct      = default)
    {
        if (rating is < 1 or > 5)
            throw new ArgumentOutOfRangeException(nameof(rating), "Rating must be between 1 and 5.");

        var body     = new FeedbackRequest(chatId, rating, comment);
        var response = await PostJsonAsync("/api/feedback", body, ct).ConfigureAwait(false);
        return await ReadJsonAsync<FeedbackResponse>(response, ct).ConfigureAwait(false);
    }

    // -----------------------------------------------------------------------
    // RAG
    // -----------------------------------------------------------------------

    /// <summary>
    /// Creates a new RAG session and returns its ID.
    /// </summary>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Object containing the new <c>session_id</c>.</returns>
    public async Task<RagNewSessionResponse> RagNewSessionAsync(CancellationToken ct = default)
    {
        var response = await _http.GetAsync("/api/rag/new_session", ct).ConfigureAwait(false);
        return await ReadJsonAsync<RagNewSessionResponse>(response, ct).ConfigureAwait(false);
    }

    /// <summary>
    /// Sends a question to the RAG pipeline and streams the grounded answer via SSE.
    /// </summary>
    /// <param name="sessionId">RAG session ID from <see cref="RagNewSessionAsync"/>.</param>
    /// <param name="question">Natural-language question.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>
    /// An <see cref="IAsyncEnumerable{T}"/> of <see cref="SseEvent"/> objects, identical
    /// in structure to <see cref="ChatStreamAsync"/>.
    /// </returns>
    /// <example>
    /// <code>
    /// await foreach (var evt in client.RagAskStreamAsync(sessionId, "What is the refund policy?"))
    /// {
    ///     if (evt.Event == "token") Console.Write(evt.Data);
    /// }
    /// </code>
    /// </example>
    public IAsyncEnumerable<SseEvent> RagAskStreamAsync(
        string            sessionId,
        string            question,
        CancellationToken ct = default)
    {
        var body = new RagAskRequest(sessionId, question);
        return StreamSseAsync("/api/rag/ask", body, ct);
    }

    /// <summary>
    /// Convenience overload that sends a RAG question and collects the full answer text.
    /// </summary>
    /// <param name="sessionId">RAG session ID.</param>
    /// <param name="question">Question to ask.</param>
    /// <param name="onToken">Optional callback invoked for each incremental token.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The full answer text.</returns>
    public async Task<string> RagAskAsync(
        string              sessionId,
        string              question,
        Action<string>?     onToken = null,
        CancellationToken   ct      = default)
    {
        var sb = new StringBuilder();

        await foreach (var evt in RagAskStreamAsync(sessionId, question, ct).ConfigureAwait(false))
        {
            if (evt.Event == "token")
            {
                sb.Append(evt.Data);
                onToken?.Invoke(evt.Data);
            }
        }

        return sb.ToString();
    }

    // -----------------------------------------------------------------------
    // Internal SSE infrastructure
    // -----------------------------------------------------------------------

    /// <summary>
    /// Posts <paramref name="body"/> to <paramref name="path"/> and returns an
    /// async enumerable of parsed <see cref="SseEvent"/> objects.
    /// The HTTP connection uses <see cref="HttpCompletionOption.ResponseHeadersRead"/>
    /// so the response body is streamed without buffering.
    /// </summary>
    private async IAsyncEnumerable<SseEvent> StreamSseAsync<TRequest>(
        string                                         path,
        TRequest                                       body,
        [EnumeratorCancellation] CancellationToken     ct)
    {
        // Build a linked CTS that also enforces the per-stream wall-clock limit.
        using var streamCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        if (_opts.StreamTimeout != System.Threading.Timeout.InfiniteTimeSpan)
            streamCts.CancelAfter(_opts.StreamTimeout);

        var linkedToken = streamCts.Token;

        // Prepare and send the request with ResponseHeadersRead so the body
        // is not buffered in memory — essential for long-running SSE streams.
        using var request = new HttpRequestMessage(HttpMethod.Post, path)
        {
            Content = JsonContent.Create(body, options: _jsonOpts),
        };

        using var response = await _http
            .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, linkedToken)
            .ConfigureAwait(false);

        await EnsureSuccessAsync(response, linkedToken).ConfigureAwait(false);

        var stream = await response.Content
            .ReadAsStreamAsync(linkedToken)
            .ConfigureAwait(false);

        // StreamReader owns the stream (detectEncodingFromByteOrderMarks: false,
        // bufferSize: 1024, leaveOpen: false) so both are disposed on scope exit.
        using var reader = new StreamReader(stream, Encoding.UTF8,
            detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: false);

        // ---------------------------------------------------------------
        // SSE wire format:
        //   event: <name>\n
        //   data: <payload>\n
        //   \n            <- blank line terminates one event block
        //
        // Multiple data: lines within a block are joined with '\n' per spec.
        // ---------------------------------------------------------------

        string? eventType = null;
        var     dataBuf   = new StringBuilder();
        bool    hasData   = false;

        while (!linkedToken.IsCancellationRequested)
        {
            var line = await reader.ReadLineAsync(linkedToken).ConfigureAwait(false);

            if (line is null)
            {
                // EOF — flush any buffered event then exit.
                if (hasData)
                    yield return new SseEvent(eventType ?? "message", dataBuf.ToString());
                yield break;
            }

            if (line.Length == 0)
            {
                // Blank line dispatches the accumulated event block.
                if (hasData)
                    yield return new SseEvent(eventType ?? "message", dataBuf.ToString());

                // Reset for the next block.
                eventType = null;
                dataBuf.Clear();
                hasData = false;
                continue;
            }

            if (line.StartsWith("event:", StringComparison.Ordinal))
            {
                eventType = line["event:".Length..].Trim();
            }
            else if (line.StartsWith("data:", StringComparison.Ordinal))
            {
                if (hasData) dataBuf.Append('\n');
                dataBuf.Append(line["data:".Length..]);
                hasData = true;
            }
            // ':' prefix = SSE comment; 'id:' / 'retry:' not handled here.
        }
    }

    // -----------------------------------------------------------------------
    // Shared HTTP helpers
    // -----------------------------------------------------------------------

    private Task<HttpResponseMessage> PostJsonAsync<T>(
        string            path,
        T                 body,
        CancellationToken ct)
    {
        var content = JsonContent.Create(body, options: _jsonOpts);
        return _http.PostAsync(path, content, ct);
    }

    private static async Task<T> ReadJsonAsync<T>(
        HttpResponseMessage response,
        CancellationToken   ct)
    {
        await EnsureSuccessAsync(response, ct).ConfigureAwait(false);

        var result = await response.Content
            .ReadFromJsonAsync<T>(_jsonOpts, ct)
            .ConfigureAwait(false);

        return result ?? throw new AgenticAIException(
            (int)response.StatusCode,
            null,
            $"Server returned a null body for type {typeof(T).Name}.");
    }

    private static async Task EnsureSuccessAsync(
        HttpResponseMessage response,
        CancellationToken   ct)
    {
        if (response.IsSuccessStatusCode) return;

        string body = string.Empty;
        try { body = await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false); }
        catch { /* best effort */ }

        throw new AgenticAIException(
            (int)response.StatusCode,
            body,
            $"Agentic AI API error {(int)response.StatusCode} ({response.ReasonPhrase}): {body}");
    }

    private static HttpClient BuildHttpClient(AgenticAIClientOptions opts)
    {
        var handler = new SocketsHttpHandler
        {
            // Keep-alive so multiple requests reuse the same TCP connection.
            PooledConnectionLifetime    = TimeSpan.FromMinutes(10),
            PooledConnectionIdleTimeout = TimeSpan.FromMinutes(2),
        };

        return new HttpClient(handler, disposeHandler: true)
        {
            BaseAddress = new Uri(opts.BaseUrl.TrimEnd('/')),
            Timeout     = opts.Timeout,
            DefaultRequestHeaders =
            {
                { "Accept", "application/json, text/event-stream" },
                { "User-Agent", $"AgenticAI.Client/0.1.0 (.NET {Environment.Version})" },
            },
        };
    }

    private static string? TryParseChatIdFromDone(string data)
    {
        try
        {
            using var doc = JsonDocument.Parse(data);
            if (doc.RootElement.TryGetProperty("chat_id", out var prop))
                return prop.GetString();
        }
        catch { /* not valid JSON — ignore */ }
        return null;
    }

    // -----------------------------------------------------------------------
    // IDisposable / IAsyncDisposable
    // -----------------------------------------------------------------------

    /// <inheritdoc/>
    public void Dispose()
    {
        if (_ownsHttpClient) _http.Dispose();
    }

    /// <inheritdoc/>
    public ValueTask DisposeAsync()
    {
        Dispose();
        return ValueTask.CompletedTask;
    }
}

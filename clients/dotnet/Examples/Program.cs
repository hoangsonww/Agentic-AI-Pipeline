// Examples/Program.cs
// Demonstrates every endpoint of the Agentic AI API through the .NET client SDK.
//
// Run:
//   cd clients/dotnet/Examples
//   dotnet run [--base-url http://localhost:8000]

using AgenticAI.Client;
using Microsoft.Extensions.DependencyInjection;

// ---------------------------------------------------------------------------
// Read CLI arguments
// ---------------------------------------------------------------------------

string baseUrl = "http://localhost:8000";
for (int i = 0; i < args.Length - 1; i++)
{
    if (args[i] is "--base-url" or "-u")
        baseUrl = args[i + 1];
}

Console.WriteLine($"[config] Connecting to {baseUrl}");
Console.WriteLine(new string('-', 60));

// ---------------------------------------------------------------------------
// Example 1 — Direct construction (no DI)
// ---------------------------------------------------------------------------
// Suitable for scripts, tests, or console tools that do not use a DI container.

Console.WriteLine("\n=== Example 1: Direct construction ===\n");

await using var directClient = new AgenticAIClient(new AgenticAIClientOptions
{
    BaseUrl       = baseUrl,
    Timeout       = TimeSpan.FromSeconds(30),
    StreamTimeout = TimeSpan.FromMinutes(3),
});

await RunAllExamplesAsync(directClient);

// ---------------------------------------------------------------------------
// Example 2 — IHttpClientFactory via Microsoft.Extensions.DependencyInjection
// ---------------------------------------------------------------------------
// The recommended approach for ASP.NET Core applications, Worker Services, etc.
// IHttpClientFactory manages connection pooling and handler lifetimes.

Console.WriteLine("\n=== Example 2: IHttpClientFactory (DI) ===\n");

var services = new ServiceCollection();

services.AddHttpClient<AgenticAIClient>(httpClient =>
{
    httpClient.BaseAddress = new Uri(baseUrl);
    httpClient.DefaultRequestHeaders.Add("User-Agent", "AgenticAI.DI.Example/1.0");
});

await using var sp  = services.BuildServiceProvider();
var             diClient = sp.GetRequiredService<AgenticAIClient>();

// Run only the health check in the DI example to avoid duplicate verbose output.
var health = await diClient.GetHealthAsync();
Console.WriteLine($"[health via DI] status={health.Status}  version={health.Version}");

Console.WriteLine("\n[done] All examples completed successfully.");

// ---------------------------------------------------------------------------
// Helper — runs through every endpoint once
// ---------------------------------------------------------------------------

static async Task RunAllExamplesAsync(AgenticAIClient client)
{
    // ------------------------------------------------------------------
    // 1. Health check
    // ------------------------------------------------------------------
    Console.WriteLine("--- Health ---");
    var health = await client.GetHealthAsync();
    Console.WriteLine($"status={health.Status}  version={health.Version}");

    // ------------------------------------------------------------------
    // 2. New chat + SSE streaming (token-by-token)
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- Chat (SSE streaming) ---");
    var chat     = await client.NewChatAsync();
    var chatId   = chat.ChatId;
    Console.WriteLine($"chat_id={chatId}");

    string prompt = "Summarise the key capabilities of Agentic AI systems in three sentences.";
    Console.WriteLine($"prompt: {prompt}");
    Console.WriteLine("response: ");

    // Enumerate SSE events manually for full control.
    await foreach (var evt in client.ChatStreamAsync(chatId, prompt))
    {
        switch (evt.Event)
        {
            case "token":
                Console.Write(evt.Data);
                break;

            case "done":
                Console.WriteLine("\n[stream done]");
                break;

            case "error":
                Console.Error.WriteLine($"\n[stream error] {evt.Data}");
                break;
        }
    }

    // ------------------------------------------------------------------
    // 3. Chat convenience overload — collects full text + optional callback
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- Chat (collect full text) ---");
    var (fullText, _) = await client.ChatAsync(
        chatId,
        "Give me a one-line fun fact about AI.",
        onToken: t => Console.Write(t));

    Console.WriteLine($"\nfull response length: {fullText.Length} chars");

    // ------------------------------------------------------------------
    // 4. Ingest plain text
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- Ingest text ---");
    var ingestResult = await client.IngestTextAsync(
        text:     "Agentic AI systems combine planning, tool use, and memory to act autonomously.",
        metadata: new Dictionary<string, object?> { ["tags"] = "agentic,ai,primer", ["source"] = "example" });

    Console.WriteLine($"ok={ingestResult.Ok}  id={ingestResult.Id}");

    // ------------------------------------------------------------------
    // 5. Ingest URL
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- Ingest URL ---");
    var urlResult = await client.IngestUrlAsync("https://example.com");
    Console.WriteLine($"ok={urlResult.Ok}  id={urlResult.Id}");

    // ------------------------------------------------------------------
    // 6. Feedback
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- Feedback ---");
    var feedback = await client.SendFeedbackAsync(
        chatId:  chatId,
        rating:  5,
        comment: "Very helpful and concise.");
    Console.WriteLine($"ok={feedback.Ok}");

    // ------------------------------------------------------------------
    // 7. RAG — new session + SSE streaming
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- RAG (SSE streaming) ---");
    var ragSession = await client.RagNewSessionAsync();
    Console.WriteLine($"session_id={ragSession.SessionId}");

    Console.Write("answer: ");
    await foreach (var evt in client.RagAskStreamAsync(
        ragSession.SessionId,
        "What is retrieval-augmented generation?"))
    {
        if (evt.Event == "token") Console.Write(evt.Data);
        if (evt.Event == "done")  Console.WriteLine("\n[rag stream done]");
    }

    // ------------------------------------------------------------------
    // 8. RAG — convenience overload (collect full answer)
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- RAG (collect full answer) ---");
    var answer = await client.RagAskAsync(
        ragSession.SessionId,
        "List two benefits of vector databases.",
        onToken: t => Console.Write(t));
    Console.WriteLine($"\nfull answer length: {answer.Length} chars");

    // ------------------------------------------------------------------
    // 9. CancellationToken demo — abort a stream early
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- CancellationToken demo (abort after 2 s) ---");
    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
    try
    {
        await foreach (var evt in client.ChatStreamAsync(
            chatId,
            "Write a very long essay about the history of computing.",
            cts.Token))
        {
            if (evt.Event == "token") Console.Write(evt.Data);
        }
    }
    catch (OperationCanceledException)
    {
        Console.WriteLine("\n[stream cancelled as expected]");
    }

    // ------------------------------------------------------------------
    // 10. Error handling demo
    // ------------------------------------------------------------------
    Console.WriteLine("\n--- Error handling ---");
    try
    {
        // rating=0 should throw ArgumentOutOfRangeException locally before
        // the request is even sent.
        await client.SendFeedbackAsync(chatId, rating: 0);
    }
    catch (ArgumentOutOfRangeException ex)
    {
        Console.WriteLine($"[client-side validation] {ex.Message}");
    }

    try
    {
        // Hitting a non-existent endpoint returns HTTP 404, which the SDK
        // wraps in AgenticAIException.
        await client.GetHealthAsync(CancellationToken.None);
    }
    catch (AgenticAIException ex)
    {
        Console.WriteLine($"[server error] HTTP {ex.StatusCode}: {ex.Message}");
    }
}

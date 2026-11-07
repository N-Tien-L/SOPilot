package com.sopilot.core.outbox;

import com.sopilot.core.config.InternalProperties;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Plain HTTP delivery with {@code X-Internal-Token} and {@code Idempotency-Key = event id}
 * (TECH §8). The response body is never read into logs or errors.
 */
@Component
public class HttpAiServiceClient implements AiServiceClient {

    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private final String baseUrl;
    private final String token;

    public HttpAiServiceClient(InternalProperties properties) {
        this.baseUrl = properties.aiBaseUrl().replaceAll("/+$", "");
        this.token = properties.token();
    }

    @Override
    public Result send(OutboxEvent event) {
        HttpRequest.Builder request = switch (event.type()) {
            case INGEST_REQUESTED -> base("/internal/ingestions")
                    .POST(HttpRequest.BodyPublishers.ofString(event.payload()));
            case ACCESS_UPDATED -> base("/internal/document-access/" + event.aggregateId())
                    .PUT(HttpRequest.BodyPublishers.ofString(event.payload()));
            case DOCUMENT_DELETED -> base("/internal/documents/" + event.aggregateId() + "?workspaceId="
                    + URLEncoder.encode(event.workspaceId().toString(), StandardCharsets.UTF_8)).DELETE();
        };
        try {
            HttpResponse<Void> response = http.send(request
                    .header("X-Internal-Token", token)
                    .header("Idempotency-Key", event.id().toString())
                    .header("Content-Type", "application/json")
                    .timeout(Duration.ofSeconds(10)).build(), HttpResponse.BodyHandlers.discarding());
            return new Result(response.statusCode(), "HTTP " + response.statusCode());
        } catch (IOException e) {
            return new Result(-1, e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new Result(-1, "Interrupted");
        }
    }

    private HttpRequest.Builder base(String path) {
        return HttpRequest.newBuilder(URI.create(baseUrl + path));
    }
}

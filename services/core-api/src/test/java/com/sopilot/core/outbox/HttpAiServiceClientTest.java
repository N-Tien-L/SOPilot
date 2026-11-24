package com.sopilot.core.outbox;

import com.sopilot.core.config.InternalProperties;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;

/** The real HTTP client against a local server: method, path, headers, body and status mapping (TECH §8.1). */
class HttpAiServiceClientTest {

    record Seen(String method, String path, String query, String token, String idempotencyKey, String body) {
    }

    private HttpServer server;
    private final List<Seen> seen = new CopyOnWriteArrayList<>();
    private volatile int status = 202;

    @BeforeEach
    void start() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            seen.add(new Seen(exchange.getRequestMethod(), exchange.getRequestURI().getPath(),
                    exchange.getRequestURI().getQuery(), exchange.getRequestHeaders().getFirst("X-Internal-Token"),
                    exchange.getRequestHeaders().getFirst("Idempotency-Key"), body));
            exchange.sendResponseHeaders(status, -1);
            exchange.close();
        });
        server.start();
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    private HttpAiServiceClient client() {
        return new HttpAiServiceClient(new InternalProperties("secret-token",
                "http://127.0.0.1:" + server.getAddress().getPort() + "/"));
    }

    private OutboxEvent event(OutboxEvent.Type type, String payload) {
        return new OutboxEvent(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), type, payload, 0);
    }

    @Test
    void ingestionIsAPostWithTheTokenAndTheEventIdAsIdempotencyKey() {
        OutboxEvent e = event(OutboxEvent.Type.INGEST_REQUESTED, "{\"versionId\":\"v\"}");

        AiServiceClient.Result r = client().send(e);

        assertThat(r.delivered()).isTrue();
        assertThat(seen).hasSize(1);
        Seen s = seen.get(0);
        assertThat(s.method()).isEqualTo("POST");
        assertThat(s.path()).isEqualTo("/internal/ingestions");
        assertThat(s.token()).isEqualTo("secret-token");
        assertThat(s.idempotencyKey()).isEqualTo(e.id().toString());
        assertThat(s.body()).isEqualTo("{\"versionId\":\"v\"}");
    }

    @Test
    void accessUpdateIsAPutAndDeleteCarriesTheWorkspaceInTheQuery() {
        OutboxEvent access = event(OutboxEvent.Type.ACCESS_UPDATED, "{\"accessRevision\":2}");
        OutboxEvent delete = event(OutboxEvent.Type.DOCUMENT_DELETED, "{}");
        client().send(access);
        client().send(delete);

        assertThat(seen.get(0).method()).isEqualTo("PUT");
        assertThat(seen.get(0).path()).isEqualTo("/internal/document-access/" + access.aggregateId());
        assertThat(seen.get(1).method()).isEqualTo("DELETE");
        assertThat(seen.get(1).path()).isEqualTo("/internal/documents/" + delete.aggregateId());
        assertThat(seen.get(1).query()).isEqualTo("workspaceId=" + delete.workspaceId());
    }

    @Test
    void statusCodesMapToDeliveredRetryableOrContractError() {
        List<AiServiceClient.Result> results = new ArrayList<>();
        for (int code : new int[] {200, 202, 400, 401, 404, 409, 408, 429, 500, 503}) {
            status = code;
            results.add(client().send(event(OutboxEvent.Type.INGEST_REQUESTED, "{}")));
        }

        assertThat(results.stream().map(AiServiceClient.Result::delivered))
                .containsExactly(true, true, false, false, false, false, false, false, false, false);
        assertThat(results.stream().map(AiServiceClient.Result::retryable))
                .containsExactly(false, false, false, false, false, false, true, true, true, true);
    }

    @Test
    void anUnreachableServiceIsARetryableNetworkError() {
        server.stop(0);

        AiServiceClient.Result r = client().send(event(OutboxEvent.Type.INGEST_REQUESTED, "{}"));

        assertThat(r.status()).isEqualTo(-1);
        assertThat(r.retryable()).isTrue();
        assertThat(r.delivered()).isFalse();
        assertThat(r.error()).doesNotContain("secret-token");
    }
}

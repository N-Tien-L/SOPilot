package com.sopilot.core.outbox;

import com.fasterxml.jackson.databind.JsonNode;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** Dispatch, retry, lease, DEAD and the DISPATCH_FAILED hand-back to the user (TECH §7). */
class OutboxDispatcherIT extends ApiIT {

    @Autowired OutboxRepository outbox;
    @Autowired OutboxService outboxService;

    /** The database is shared by every IT class of the run: start from an empty queue. */
    @org.junit.jupiter.api.BeforeEach
    void drainQueue() {
        dispatcher.dispatchDue();
        ai.reset();
    }

    private record Row(String status, int attempts, Instant nextAttemptAt, String lastError) {
    }

    private Row row(Actor ws, UUID document, OutboxEvent.Type type) {
        return asTenant(ws, () -> jdbc.queryForObject("SELECT status, attempts, next_attempt_at, last_error "
                + "FROM core.outbox_events WHERE aggregate_id = ? AND event_type = ? ORDER BY created_at DESC LIMIT 1",
                (rs, i) -> new Row(rs.getString(1), rs.getInt(2), rs.getTimestamp(3).toInstant(), rs.getString(4)),
                document, type.name()));
    }

    private void makeDue(Actor ws, UUID document) {
        asTenant(ws, () -> jdbc.update("UPDATE core.outbox_events SET next_attempt_at = now() - interval '1 second' "
                + "WHERE aggregate_id = ? AND status = 'PENDING'", document));
    }

    private UUID upload(Actor ws, String name) {
        return id(uploadDocument(ws, name, markdown(name)), "id");
    }

    @Test
    void aDueEventIsSentOnceWithItsIdAndMarkedDelivered() {
        Actor owner = newTeamWorkspace("own");
        UUID doc = upload(owner, "a.md");

        assertThat(dispatcher.dispatchDue()).isEqualTo(1);

        assertThat(ai.sent()).hasSize(1);
        assertThat(ai.sent().get(0).type()).isEqualTo(OutboxEvent.Type.INGEST_REQUESTED);
        assertThat(ai.sent().get(0).workspaceId()).isEqualTo(owner.workspaceId());
        Row r = row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED);
        assertThat(r.status()).isEqualTo("DELIVERED");
        assertThat(r.attempts()).isEqualTo(1);
        // Nothing left to send.
        assertThat(dispatcher.dispatchDue()).isZero();
        assertThat(ai.sent()).hasSize(1);
    }

    @Test
    void aClaimedEventIsLeasedSoASecondDispatcherDoesNotSendItAgain() {
        Actor owner = newTeamWorkspace("own");
        upload(owner, "a.md");

        List<OutboxEvent> first = outbox.claim(20);
        List<OutboxEvent> second = outbox.claim(20);

        assertThat(first).hasSize(1);
        assertThat(second).isEmpty();
    }

    @Test
    void aLeasedEventIsNotClaimedUntilItsLeaseEndsAndIsNeverAnnounced() {
        Actor owner = newTeamWorkspace("own");
        UUID doc = UUID.randomUUID();

        OutboxEvent leased = asTenant(owner, () -> outboxService.enqueueLeased(owner.workspaceId(), doc,
                OutboxEvent.Type.ACCESS_UPDATED, java.util.Map.of("accessRevision", 2)));

        assertThat(dispatcher.dispatchDue()).isZero();
        assertThat(outbox.claim(20)).isEmpty();
        assertThat(ai.sent()).isEmpty();
        assertThat(row(owner, doc, OutboxEvent.Type.ACCESS_UPDATED).nextAttemptAt()).isAfter(Instant.now().plusSeconds(30));

        makeDue(owner, doc);
        assertThat(dispatcher.dispatchDue()).isEqualTo(1);
        assertThat(ai.sent().get(0).id()).isEqualTo(leased.id());
        assertThat(row(owner, doc, OutboxEvent.Type.ACCESS_UPDATED).status()).isEqualTo("DELIVERED");
    }

    @Test
    void aServerErrorIsRetriedLaterWithBackoffAndThenDelivered() {
        Actor owner = newTeamWorkspace("own");
        UUID doc = upload(owner, "a.md");
        ai.respondWith(503);

        dispatcher.dispatchDue();

        Row failed = row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED);
        assertThat(failed.status()).isEqualTo("PENDING");
        assertThat(failed.attempts()).isEqualTo(1);
        assertThat(failed.lastError()).isEqualTo("HTTP 503");
        assertThat(failed.nextAttemptAt()).isAfter(Instant.now());
        // Not due yet, so a poll does not hammer ai-service.
        assertThat(dispatcher.dispatchDue()).isZero();

        makeDue(owner, doc);
        dispatcher.dispatchDue();

        assertThat(ai.sent()).hasSize(2);
        assertThat(ai.sent().get(1).id()).as("same Idempotency-Key on every attempt").isEqualTo(ai.sent().get(0).id());
        assertThat(row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED).status()).isEqualTo("DELIVERED");
    }

    @Test
    void networkErrorsAndRateLimitsAreRetriedToo() {
        Actor owner = newTeamWorkspace("own");
        UUID doc = upload(owner, "a.md");

        for (int status : new int[] {-1, 429, 408}) {
            ai.respondWith(status);
            dispatcher.dispatchDue();
            assertThat(row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED).status()).isEqualTo("PENDING");
            makeDue(owner, doc);
        }
        assertThat(row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED).attempts()).isEqualTo(3);
    }

    @Test
    void aContractErrorGoesDeadAtOnceAndTheUserCanRetryTheDocument() {
        Actor owner = newTeamWorkspace("own");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "a.md", markdown("a"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        ai.respondWith(422);

        dispatcher.dispatchDue();

        Row dead = row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED);
        assertThat(dead.status()).isEqualTo("DEAD");
        assertThat(dead.attempts()).isEqualTo(1);
        JsonNode d = get("/api/v1/documents/" + doc, owner).getBody().path("data");
        assertThat(d.path("status").asText()).isEqualTo("FAILED");
        assertThat(d.at("/latestVersion/failureCode").asText()).isEqualTo("DISPATCH_FAILED");
        assertThat(d.at("/latestVersion/failureMessage").asText()).isNotBlank();

        ResponseEntity<JsonNode> retried = post("/api/v1/documents/" + doc + "/retry", owner, null);
        assertThat(retried.getStatusCode()).isEqualTo(HttpStatus.OK);
        dispatcher.dispatchDue();
        assertThat(ai.sent()).hasSize(2);
        assertThat(row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED).status()).isEqualTo("DELIVERED");
        assertThat(ver).isNotNull();
    }

    @Test
    void theLastAllowedAttemptGoesDeadInsteadOfRetryingForever() {
        Actor owner = newTeamWorkspace("own");
        UUID doc = upload(owner, "a.md");
        asTenant(owner, () -> jdbc.update("UPDATE core.outbox_events SET attempts = 19 WHERE aggregate_id = ?", doc));
        ai.respondWith(503);

        dispatcher.dispatchDue();

        Row r = row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED);
        assertThat(r.status()).isEqualTo("DEAD");
        assertThat(r.attempts()).isEqualTo(20);
        assertThat(get("/api/v1/documents/" + doc, owner).getBody().at("/data/latestVersion/failureCode").asText())
                .isEqualTo("DISPATCH_FAILED");
    }

    @Test
    void aDeadEventForAVersionThatAlreadyMovedOnDoesNotOverwriteIt() {
        Actor owner = newTeamWorkspace("own");
        ResponseEntity<JsonNode> created = uploadDocument(owner, "a.md", markdown("a"));
        UUID doc = id(created, "id");
        UUID ver = id(created, "latestVersion", "id");
        asTenant(owner, () -> jdbc.update("UPDATE core.document_versions SET status = 'PROCESSING' WHERE id = ?", ver));
        ai.respondWith(400);

        dispatcher.dispatchDue();

        assertThat(row(owner, doc, OutboxEvent.Type.INGEST_REQUESTED).status()).isEqualTo("DEAD");
        assertThat(get("/api/v1/documents/" + doc, owner).getBody().at("/data/latestVersion/status").asText())
                .isEqualTo("PROCESSING");
    }

    @Test
    void eventsOfEveryWorkspaceAreClaimedAndMarkedInTheirOwnTenant() {
        Actor a = newTeamWorkspace("a");
        Actor b = newTeamWorkspace("b");
        UUID docA = upload(a, "a.md");
        UUID docB = upload(b, "b.md");

        dispatcher.dispatchDue();

        assertThat(ai.sent().stream().map(OutboxEvent::workspaceId)).containsExactlyInAnyOrder(a.workspaceId(),
                b.workspaceId());
        assertThat(row(a, docA, OutboxEvent.Type.INGEST_REQUESTED).status()).isEqualTo("DELIVERED");
        assertThat(row(b, docB, OutboxEvent.Type.INGEST_REQUESTED).status()).isEqualTo("DELIVERED");
        // The application role cannot read another workspace's outbox directly.
        assertThat(asTenant(a, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events WHERE workspace_id = ?",
                Long.class, b.workspaceId()))).isZero();
    }

    @Test
    void claimFunctionIsOnlyForTheCoreRole() {
        assertThat(jdbc.queryForObject("SELECT has_function_privilege('sopilot_ai_app', 'core.claim_outbox_batch(int)', "
                + "'EXECUTE')", Boolean.class)).isFalse();
        assertThat(jdbc.queryForObject("SELECT has_function_privilege('public', 'core.claim_outbox_batch(int)', "
                + "'EXECUTE')", Boolean.class)).isFalse();
        assertThat(jdbc.queryForObject("SELECT prosecdef FROM pg_proc WHERE proname = 'claim_outbox_batch'",
                Boolean.class)).isTrue();
        assertThat(jdbc.queryForObject("SELECT has_function_privilege('sopilot_ai_app', "
                + "'core.referenced_object_keys(text[])', 'EXECUTE')", Boolean.class)).isFalse();
    }

    @Test
    void auditLogIsAppendOnlyForTheApplicationRole() {
        Actor owner = newTeamWorkspace("own");
        upload(owner, "a.md");

        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.audit_logs", Long.class)))
                .isPositive();
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> asTenant(owner,
                        () -> jdbc.update("UPDATE core.audit_logs SET action = 'x'")))
                .rootCause().hasMessageContaining("permission denied");
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> asTenant(owner,
                        () -> jdbc.update("DELETE FROM core.audit_logs")))
                .rootCause().hasMessageContaining("permission denied");
    }
}

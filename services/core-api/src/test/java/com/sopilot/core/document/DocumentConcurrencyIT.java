package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.storage.StorageJanitor;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Races that the advisory locks and row locks must win (TECH §3.3, §10): the document quota, identical
 * uploads, double retry, and the orphan sweep. The default quota (50 documents) is in force.
 */
class DocumentConcurrencyIT extends ApiIT {

    @Autowired DocumentService documents;
    @Autowired StorageJanitor janitor;

    /** Outcome of one call: the HTTP-style error code, or "OK". */
    private List<String> race(int threads, List<Callable<String>> tasks) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        try {
            CountDownLatch ready = new CountDownLatch(tasks.size());
            CountDownLatch go = new CountDownLatch(1);
            List<Future<String>> futures = new ArrayList<>();
            for (Callable<String> task : tasks) {
                futures.add(pool.submit(() -> {
                    ready.countDown();
                    go.await();
                    try {
                        return task.call();
                    } catch (ApiException e) {
                        return e.code();
                    }
                }));
            }
            ready.await();
            go.countDown();
            List<String> results = new ArrayList<>();
            for (Future<String> f : futures) {
                results.add(f.get());
            }
            return results;
        } finally {
            pool.shutdownNow();
        }
    }

    private Callable<String> uploader(Actor actor, String name, byte[] bytes) {
        return () -> {
            documents.upload(actor.principal(), name, bytes, null);
            return "OK";
        };
    }

    private long count(List<String> results, String what) {
        return results.stream().filter(what::equals).count();
    }

    @Test
    void tenConcurrentUploadsIntoAWorkspaceWith48DocumentsAdmitExactlyTwo() throws Exception {
        Actor owner = newTeamWorkspace("own");
        for (int i = 0; i < 48; i++) {
            documents.upload(owner.principal(), "seed" + i + ".md", markdown("seed" + i), null);
        }
        List<Callable<String>> tasks = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            tasks.add(uploader(owner, "race" + i + ".md", markdown("race" + i)));
        }

        List<String> results = race(10, tasks);

        assertThat(count(results, "OK")).isEqualTo(2);
        assertThat(count(results, "QUOTA_EXCEEDED")).isEqualTo(8);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents", Long.class)))
                .isEqualTo(50);
        // Rejected uploads never reached storage, so there is nothing for the janitor to remove.
        assertThat(storage.count()).isEqualTo(50);
        assertThat(janitor.sweep(Duration.ZERO)).isZero();
        assertThat(storage.count()).isEqualTo(50);
    }

    @Test
    void theQuotaErrorReportsLimitAndUsage() {
        Actor owner = newTeamWorkspace("own");
        for (int i = 0; i < 50; i++) {
            documents.upload(owner.principal(), "d" + i + ".md", markdown("d" + i), null);
        }

        org.assertj.core.api.Assertions.assertThatThrownBy(
                        () -> documents.upload(owner.principal(), "extra.md", markdown("extra"), null))
                .isInstanceOfSatisfying(ApiException.class, e -> {
                    assertThat(e.status()).isEqualTo(HttpStatus.CONFLICT);
                    assertThat(e.code()).isEqualTo("QUOTA_EXCEEDED");
                    assertThat(e.details()).containsEntry("limit", 50L).containsEntry("used", 50L);
                });
        // Another workspace is unaffected.
        Actor other = newTeamWorkspace("other");
        assertThat(documents.upload(other.principal(), "ok.md", markdown("ok"), null).created()).isTrue();
    }

    @Test
    void replacingAVersionDoesNotCountAsANewDocumentEvenAtTheLimit() {
        Actor owner = newTeamWorkspace("own");
        DocumentView first = null;
        for (int i = 0; i < 50; i++) {
            DocumentView d = documents.upload(owner.principal(), "d" + i + ".md", markdown("d" + i), null).document();
            first = first == null ? d : first;
        }
        UUID firstId = first.id();
        UUID firstVersion = first.latestVersion().id();
        asTenant(owner, () -> jdbc.update("UPDATE core.document_versions SET status = 'READY' WHERE id = ?", firstVersion));
        asTenant(owner, () -> jdbc.update("UPDATE core.documents SET current_version_id = ? WHERE id = ?",
                firstVersion, firstId));

        DocumentService.UploadResult replaced = documents.uploadVersion(owner.principal(), firstId, "d0.md",
                markdown("replacement"));

        assertThat(replaced.created()).isTrue();
        assertThat(replaced.document().latestVersion().versionNo()).isEqualTo(2);
    }

    @Test
    void fourConcurrentUploadsOfTheSameBytesCreateOneDocument() throws Exception {
        Actor owner = newTeamWorkspace("own");
        byte[] bytes = markdown("identical");
        List<Callable<String>> tasks = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            tasks.add(uploader(owner, "copy" + i + ".md", bytes));
        }

        List<String> results = race(4, tasks);

        assertThat(count(results, "OK")).isEqualTo(1);
        assertThat(count(results, "DUPLICATE_DOCUMENT")).isEqualTo(3);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents", Long.class)))
                .isEqualTo(1);
        assertThat(storage.count()).isEqualTo(1);
    }

    @Test
    void twoConcurrentRetriesCreateOneJob() throws Exception {
        Actor owner = newTeamWorkspace("own");
        DocumentView doc = documents.upload(owner.principal(), "a.md", markdown("a"), null).document();
        asTenant(owner, () -> jdbc.update("UPDATE core.document_versions SET status = 'FAILED', failure_code = "
                + "'EXTRACTION_ERROR' WHERE id = ?", doc.latestVersion().id()));
        List<Callable<String>> tasks = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            tasks.add(() -> {
                documents.retry(owner.principal(), doc.id());
                return "OK";
            });
        }

        List<String> results = race(2, tasks);

        assertThat(count(results, "OK")).isEqualTo(1);
        assertThat(count(results, "VERSION_NOT_FAILED")).isEqualTo(1);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.outbox_events "
                + "WHERE aggregate_id = ? AND event_type = 'INGEST_REQUESTED'", Long.class, doc.id()))).isEqualTo(2);
    }

    @Test
    void twoDifferentFilesReplacingTheSameDocumentAtOnceCreateOneVersion() throws Exception {
        Actor owner = newTeamWorkspace("own");
        DocumentView doc = documents.upload(owner.principal(), "a.md", markdown("a"), null).document();
        asTenant(owner, () -> jdbc.update("UPDATE core.document_versions SET status = 'READY' WHERE id = ?",
                doc.latestVersion().id()));
        asTenant(owner, () -> jdbc.update("UPDATE core.documents SET current_version_id = ? WHERE id = ?",
                doc.latestVersion().id(), doc.id()));
        List<Callable<String>> tasks = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            byte[] bytes = markdown("v" + i);
            tasks.add(() -> {
                documents.uploadVersion(owner.principal(), doc.id(), "a.md", bytes);
                return "OK";
            });
        }

        List<String> results = race(3, tasks);

        assertThat(count(results, "OK")).isEqualTo(1);
        assertThat(count(results, "VERSION_IN_PROGRESS")).isEqualTo(2);
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.document_versions "
                + "WHERE document_id = ?", Long.class, doc.id()))).isEqualTo(2);
    }

    @Test
    void janitorDeletesOnlyOldObjectsNoVersionReferences() {
        Actor owner = newTeamWorkspace("own");
        DocumentView doc = documents.upload(owner.principal(), "a.md", markdown("a"), null).document();
        String referenced = asTenant(owner, () -> jdbc.queryForObject(
                "SELECT object_key FROM core.document_versions WHERE id = ?", String.class, doc.latestVersion().id()));
        storage.plantOrphan("workspaces/" + owner.workspaceId() + "/documents/" + UUID.randomUUID() + "/versions/old",
                Instant.now().minus(Duration.ofHours(3)));
        String fresh = "workspaces/" + owner.workspaceId() + "/documents/" + UUID.randomUUID() + "/versions/fresh";
        storage.plantOrphan(fresh, Instant.now());
        // An old object that a version row still references must survive, whatever its age.
        storage.plantOrphan(referenced, Instant.now().minus(Duration.ofDays(2)));
        // A key with characters that need quoting in an array literal.
        storage.plantOrphan("workspaces/w\"x,y}z\\q/old", Instant.now().minus(Duration.ofHours(3)));

        int deleted = janitor.sweep(Duration.ofHours(1));

        assertThat(deleted).isEqualTo(2);
        assertThat(storage.has(referenced)).isTrue();
        assertThat(storage.has(fresh)).as("an in-flight upload writes its object before its row commits").isTrue();
        assertThat(storage.count()).isEqualTo(2);
    }
}

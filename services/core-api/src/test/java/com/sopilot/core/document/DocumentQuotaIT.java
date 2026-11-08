package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The byte quota and its documented counting rules (TECH §3.3, FR-09). A tiny quota keeps the test cheap. */
@TestPropertySource(properties = {"sopilot.quota.docs-per-workspace=3", "sopilot.quota.bytes-per-workspace=400"})
class DocumentQuotaIT extends ApiIT {

    @Autowired DocumentService documents;

    private static byte[] bytes(int size, char fill) {
        byte[] b = new byte[size];
        java.util.Arrays.fill(b, (byte) fill);
        return b;
    }

    private void makeReady(Actor owner, DocumentView doc) {
        asTenant(owner, () -> jdbc.update("UPDATE core.document_versions SET status = 'READY' WHERE id = ?",
                doc.latestVersion().id()));
        asTenant(owner, () -> jdbc.update("UPDATE core.documents SET current_version_id = ? WHERE id = ?",
                doc.latestVersion().id(), doc.id()));
    }

    @Test
    void bytesAreCountedAcrossLiveVersionsAndSoftDeletedDocumentsAreFreed() {
        Actor owner = newTeamWorkspace("own");
        DocumentView a = documents.upload(owner.principal(), "a.md", bytes(150, 'a'), null).document();
        documents.upload(owner.principal(), "b.md", bytes(150, 'b'), null);

        assertThatThrownBy(() -> documents.upload(owner.principal(), "c.md", bytes(150, 'c'), null))
                .isInstanceOfSatisfying(ApiException.class, e -> {
                    assertThat(e.code()).isEqualTo("QUOTA_EXCEEDED");
                    assertThat(e.details()).containsEntry("kind", "bytes").containsEntry("limit", 400L)
                            .containsEntry("used", 300L);
                });

        // Exactly the remaining 100 bytes fit; deleting a document frees its bytes at once.
        assertThat(documents.upload(owner.principal(), "d.md", bytes(100, 'd'), null).created()).isTrue();
        documents.delete(owner.principal(), a.id());
        assertThat(documents.upload(owner.principal(), "e.md", bytes(150, 'e'), null).created()).isTrue();
    }

    @Test
    void aReplacementCountsAlongsideTheCurrentVersionUntilTheOldOneIsSuperseded() {
        Actor owner = newTeamWorkspace("own");
        DocumentView a = documents.upload(owner.principal(), "a.md", bytes(250, 'a'), null).document();
        makeReady(owner, a);

        assertThatThrownBy(() -> documents.uploadVersion(owner.principal(), a.id(), "a.md", bytes(200, 'b')))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.code()).isEqualTo("QUOTA_EXCEEDED"));
        assertThat(documents.uploadVersion(owner.principal(), a.id(), "a.md", bytes(150, 'b')).created()).isTrue();
    }

    @Test
    void theDocumentCountLimitAppliesToNewDocumentsOnly() {
        Actor owner = newTeamWorkspace("own");
        DocumentView first = documents.upload(owner.principal(), "a.md", bytes(10, 'a'), null).document();
        documents.upload(owner.principal(), "b.md", bytes(10, 'b'), null);
        documents.upload(owner.principal(), "c.md", bytes(10, 'c'), null);
        makeReady(owner, first);

        assertThatThrownBy(() -> documents.upload(owner.principal(), "d.md", bytes(10, 'd'), null))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.details()).containsEntry("kind", "documents")
                        .containsEntry("limit", 3L).containsEntry("used", 3L));
        assertThat(documents.uploadVersion(owner.principal(), first.id(), "a.md", bytes(10, 'z')).created()).isTrue();
    }
}

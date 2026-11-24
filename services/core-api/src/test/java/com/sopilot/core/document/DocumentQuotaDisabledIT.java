package com.sopilot.core.document;

import com.sopilot.core.support.ApiIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;

/** {@code 0} turns both quotas off (eval and large demo corpora). */
@TestPropertySource(properties = {"sopilot.quota.docs-per-workspace=0", "sopilot.quota.bytes-per-workspace=0"})
class DocumentQuotaDisabledIT extends ApiIT {

    @Autowired DocumentService documents;

    @Test
    void noLimitAppliesWhenBothAreZero() {
        Actor owner = newTeamWorkspace("own");

        for (int i = 0; i < 55; i++) {
            assertThat(documents.upload(owner.principal(), "d" + i + ".md", markdown("d" + i), null).created()).isTrue();
        }
        assertThat(asTenant(owner, () -> jdbc.queryForObject("SELECT count(*) FROM core.documents", Long.class)))
                .isEqualTo(55);
    }
}

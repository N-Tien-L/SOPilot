package com.sopilot.core.tenancy;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowCallbackHandler;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.UUID;

/**
 * Sets the RLS variables {@code app.workspace_id} and {@code app.user_id} for the current
 * transaction only ({@code set_config(..., true)}, TECH §4.3), so a pooled connection never
 * carries a tenant into the next transaction. Values must come from verified identity or token,
 * never from request input. The per-request listener driven by the access token is V2-29.
 */
@Component
public class RlsContext {

    private static final RowCallbackHandler IGNORE = rs -> { };

    private final JdbcTemplate jdbc;

    public RlsContext(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void bind(UUID workspaceId, UUID userId) {
        if (!TransactionSynchronizationManager.isActualTransactionActive()) {
            throw new IllegalStateException("RLS context requires an active transaction");
        }
        jdbc.query("SELECT set_config('app.workspace_id', ?, true), set_config('app.user_id', ?, true)",
                IGNORE,
                workspaceId == null ? "" : workspaceId.toString(),
                userId == null ? "" : userId.toString());
    }
}

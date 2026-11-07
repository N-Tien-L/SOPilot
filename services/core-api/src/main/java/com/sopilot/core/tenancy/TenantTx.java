package com.sopilot.core.tenancy;

import com.sopilot.core.security.AuthPrincipal;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.UUID;
import java.util.function.Supplier;

/**
 * Runs a block in one transaction whose RLS variables are bound first (TECH §4.3). The tenant
 * comes from the verified principal or, for internal callbacks and background jobs, from the
 * event being processed; never from request input. {@code set_config(..., true)} makes the binding
 * end with the transaction, so a pooled connection never carries a tenant to the next caller.
 */
@Component
public class TenantTx {

    private final TransactionTemplate tx;
    private final RlsContext rls;

    public TenantTx(TransactionTemplate tx, RlsContext rls) {
        this.tx = tx;
        this.rls = rls;
    }

    public <T> T run(AuthPrincipal principal, Supplier<T> body) {
        return run(principal.workspaceId(), principal.userId(), body);
    }

    public <T> T run(UUID workspaceId, UUID userId, Supplier<T> body) {
        return tx.execute(status -> {
            rls.bind(workspaceId, userId);
            return body.get();
        });
    }

    public void runVoid(UUID workspaceId, UUID userId, Runnable body) {
        run(workspaceId, userId, () -> {
            body.run();
            return null;
        });
    }
}

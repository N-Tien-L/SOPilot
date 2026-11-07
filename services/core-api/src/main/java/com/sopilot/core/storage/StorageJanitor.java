package com.sopilot.core.storage;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Deletes objects no {@code document_versions} row references (TECH §2.2): leftovers of an upload
 * whose commit failed after the object was written. Objects younger than the grace period are left
 * alone, because an in-flight upload writes its object before its row commits.
 */
@Component
public class StorageJanitor {

    private static final Logger log = LoggerFactory.getLogger(StorageJanitor.class);
    private static final int BATCH = 500;

    private final StorageClient storage;
    private final JdbcTemplate jdbc;

    public StorageJanitor(StorageClient storage, JdbcTemplate jdbc) {
        this.storage = storage;
        this.jdbc = jdbc;
    }

    @Scheduled(fixedDelayString = "${sopilot.janitor.interval:PT1H}", initialDelayString = "${sopilot.janitor.initial-delay:PT10M}")
    void scheduled() {
        try {
            sweep(Duration.ofHours(1));
        } catch (RuntimeException e) {
            log.warn("Storage janitor skipped: {}", e.getClass().getSimpleName());
        }
    }

    /** Returns how many orphaned objects were deleted. */
    public int sweep(Duration grace) {
        Instant cutoff = Instant.now().minus(grace);
        List<String> candidates = new ArrayList<>();
        for (StorageClient.StoredObject object : storage.list("workspaces/", 100_000)) {
            if (object.lastModified().isBefore(cutoff)) {
                candidates.add(object.key());
            }
        }
        int deleted = 0;
        for (int from = 0; from < candidates.size(); from += BATCH) {
            List<String> batch = candidates.subList(from, Math.min(from + BATCH, candidates.size()));
            Set<String> referenced = new HashSet<>(jdbc.queryForList(
                    "SELECT core.referenced_object_keys(?::text[])", String.class,
                    "{" + String.join(",", batch.stream().map(StorageJanitor::quote).toList()) + "}"));
            for (String key : batch) {
                if (!referenced.contains(key)) {
                    storage.delete(key);
                    deleted++;
                }
            }
        }
        return deleted;
    }

    private static String quote(String key) {
        return "\"" + key.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
}

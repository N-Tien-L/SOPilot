package com.sopilot.core.storage;

import java.time.Duration;
import java.time.Instant;
import java.util.List;

/**
 * Object storage behind the standard S3 API (TECH §3.3, §8.3). Keys are
 * {@code workspaces/{wid}/documents/{docId}/versions/{verId}}; the original file name lives only in
 * the database. Implementations must not log keys' content or credentials.
 */
public interface StorageClient {

    /** Replaces any object with the same key. */
    void put(String key, byte[] content, String contentType);

    /** Deleting a missing key is not an error. */
    void delete(String key);

    /** Pre-signed GET URL; {@code downloadName} becomes the {@code Content-Disposition} file name. */
    String presignGet(String key, String downloadName, Duration ttl);

    /** Objects under {@code prefix} (at most {@code max}), for the orphan janitor. */
    List<StoredObject> list(String prefix, int max);

    record StoredObject(String key, Instant lastModified) {
    }
}

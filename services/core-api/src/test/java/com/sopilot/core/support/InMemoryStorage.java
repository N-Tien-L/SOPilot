package com.sopilot.core.support;

import com.sopilot.core.storage.StorageClient;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Object storage in memory for integration tests that are not about S3 itself. */
public class InMemoryStorage implements StorageClient {

    private final Map<String, byte[]> objects = new ConcurrentHashMap<>();
    private final Map<String, Instant> modified = new ConcurrentHashMap<>();
    private volatile boolean failPuts;

    @Override
    public void put(String key, byte[] content, String contentType) {
        if (failPuts) {
            throw new IllegalStateException("storage down");
        }
        objects.put(key, content.clone());
        modified.put(key, Instant.now());
    }

    @Override
    public void delete(String key) {
        objects.remove(key);
        modified.remove(key);
    }

    @Override
    public String presignGet(String key, String downloadName, Duration ttl) {
        return "http://storage.test/" + key + "?ttl=" + ttl.toSeconds();
    }

    @Override
    public List<StoredObject> list(String prefix, int max) {
        return objects.keySet().stream().filter(k -> k.startsWith(prefix)).limit(max)
                .map(k -> new StoredObject(k, modified.get(k))).toList();
    }

    public boolean has(String key) {
        return objects.containsKey(key);
    }

    public int count() {
        return objects.size();
    }

    public byte[] get(String key) {
        return objects.get(key);
    }

    /** Plants an object that no database row references, as a failed commit would leave behind. */
    public void plantOrphan(String key, Instant lastModified) {
        objects.put(key, new byte[] {1});
        modified.put(key, lastModified);
    }

    public void failPuts(boolean fail) {
        this.failPuts = fail;
    }

    public void clear() {
        objects.clear();
        modified.clear();
        failPuts = false;
    }
}

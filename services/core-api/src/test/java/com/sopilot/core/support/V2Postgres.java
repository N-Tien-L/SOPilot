package com.sopilot.core.support;

import org.flywaydb.core.Flyway;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.util.HexFormat;

/**
 * One disposable V2 Postgres per test JVM, built like {@code docker-compose.v2.yml}: same image,
 * the real {@code infrastructure/db/init/01-roles.sh}, and both Flyway chains applied as
 * {@code sopilot_migrator}. core-api connects as {@code sopilot_core_app}, so RLS and schema
 * grants are the production ones. Passwords are random per run; nothing touches local volumes.
 */
public final class V2Postgres {

    private static final DockerImageName IMAGE =
            DockerImageName.parse("pgvector/pgvector:0.8.0-pg16").asCompatibleSubstituteFor("postgres");

    public static final String MIGRATOR_PASSWORD = randomPassword();
    public static final String CORE_APP_PASSWORD = randomPassword();
    public static final String AI_APP_PASSWORD = randomPassword();

    private static final PostgreSQLContainer<?> CONTAINER = start();

    private V2Postgres() {
    }

    public static PostgreSQLContainer<?> container() {
        return CONTAINER;
    }

    public static void register(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", CONTAINER::getJdbcUrl);
        registry.add("spring.datasource.username", () -> "sopilot_core_app");
        registry.add("spring.datasource.password", () -> CORE_APP_PASSWORD);
        // Migrations are applied above as the migrator; the app role must never run them.
        registry.add("spring.flyway.enabled", () -> false);
    }

    private static PostgreSQLContainer<?> start() {
        Path init = dir("sopilot.db.init.dir", "../../infrastructure/db/init").resolve("01-roles.sh");
        PostgreSQLContainer<?> pg = new PostgreSQLContainer<>(IMAGE)
                .withDatabaseName("sopilot")
                .withUsername("postgres")
                .withPassword(randomPassword())
                .withEnv("V2_DB_MIGRATOR_PASSWORD", MIGRATOR_PASSWORD)
                .withEnv("V2_DB_CORE_APP_PASSWORD", CORE_APP_PASSWORD)
                .withEnv("V2_DB_AI_APP_PASSWORD", AI_APP_PASSWORD)
                .withCopyFileToContainer(MountableFile.forHostPath(init, 0755), "/docker-entrypoint-initdb.d/01-roles.sh");
        pg.start();

        Path migrations = dir("sopilot.migrations.dir", "../../infrastructure/db/migrations");
        migrate(pg, migrations, "core", "latest");
        // rag only up to its bootstrap (schema, grants): enough for the isolation checks, and it keeps
        // core-api tests independent of ai-service table migrations.
        migrate(pg, migrations, "rag", "2");
        return pg;
    }

    private static void migrate(PostgreSQLContainer<?> pg, Path migrations, String schema, String target) {
        Flyway.configure()
                .dataSource(pg.getJdbcUrl(), "sopilot_migrator", MIGRATOR_PASSWORD)
                .schemas(schema)
                .defaultSchema(schema)
                .table("flyway_schema_history")
                .locations("filesystem:" + migrations.resolve(schema).toAbsolutePath())
                .target(target)
                .load()
                .migrate();
    }

    private static Path dir(String property, String fallback) {
        Path path = Path.of(System.getProperty(property, fallback));
        if (!Files.isDirectory(path)) {
            throw new IllegalStateException("Missing directory " + path.toAbsolutePath());
        }
        return path;
    }

    private static String randomPassword() {
        byte[] bytes = new byte[16];
        new SecureRandom().nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }
}

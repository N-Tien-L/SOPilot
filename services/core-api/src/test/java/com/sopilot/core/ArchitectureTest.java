package com.sopilot.core;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.config.WebConfig;
import com.sopilot.core.identity.IdentityService;
import com.sopilot.core.security.PrincipalArgumentResolver;
import com.sopilot.core.storage.StorageJanitor;
import com.sopilot.core.tenancy.RlsContext;
import com.sopilot.core.tenancy.TenantTx;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

/**
 * Layer and tenancy boundaries of core-api, checked on every {@code mvnw test} (no Docker).
 * Exceptions are listed by class so a rename breaks the build instead of silently widening a rule.
 */
@AnalyzeClasses(packages = "com.sopilot.core", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    private static final Class<?>[] JDBC = {
            JdbcTemplate.class, NamedParameterJdbcTemplate.class, JdbcClient.class, DataSource.class};

    /** Controllers map HTTP to a service call; data access and its RLS binding live behind the service. */
    @ArchTest
    static final ArchRule controllersDoNotTouchRepositoriesOrJdbc = noClasses()
            .that().areAnnotatedWith(RestController.class)
            .should().dependOnClassesThat().haveSimpleNameEndingWith("Repository")
            .orShould().dependOnClassesThat().belongToAnyOf(JDBC)
            .because("controllers delegate to a service, which runs repository calls inside TenantTx");

    /**
     * SQL lives in {@code *Repository} classes. Baseline exceptions (2026-11-08): AuditService
     * (append-only audit table), IdentityService (JIT bootstrap before a workspace exists) and
     * StorageJanitor (SECURITY DEFINER lookup across workspaces). Do not add to this list without review.
     */
    @ArchTest
    static final ArchRule jdbcOnlyInRepositories = noClasses()
            .that().haveSimpleNameNotEndingWith("Repository")
            .and().resideOutsideOfPackage("com.sopilot.core.tenancy..")
            .and().doNotBelongToAnyOf(AuditService.class, IdentityService.class, StorageJanitor.class)
            .should().dependOnClassesThat().belongToAnyOf(JDBC)
            .because("SQL belongs in repositories so tenant scoping is reviewed in one place");

    /** RLS variables are bound only through TenantTx; IdentityService binds them once during JIT signup. */
    @ArchTest
    static final ArchRule rlsBoundOnlyThroughTenantTx = classes()
            .that().belongToAnyOf(RlsContext.class)
            .should().onlyHaveDependentClassesThat().belongToAnyOf(RlsContext.class, TenantTx.class, IdentityService.class)
            .because("the tenant must come from verified identity inside one transaction (TECH-V2-core-api §4.3)");

    /**
     * Who may write a document is {@code DocumentWritePolicy} (ADR-009), never the role. {@code deleteAll} (workspace
     * delete) uses {@code requireOwner}; nothing in {@code DocumentService} may fall back to {@code requireManager}.
     */
    @ArchTest
    static final ArchRule documentServiceDoesNotGateWritesOnTheRole = noClasses()
            .that().belongToAnyOf(com.sopilot.core.document.DocumentService.class)
            .should().callMethod(com.sopilot.core.security.AuthPrincipal.class, "requireManager")
            .because("document writes belong to publishers (TECH-V2-core-api §15.3)");

    /** {@code common} is shared infrastructure and must not know feature modules. */
    @ArchTest
    static final ArchRule commonDoesNotDependOnFeatures = noClasses()
            .that().resideInAPackage("com.sopilot.core.common..")
            .should().dependOnClassesThat().resideInAnyPackage(
                    "com.sopilot.core.audit..", "com.sopilot.core.department..", "com.sopilot.core.document..",
                    "com.sopilot.core.identity..", "com.sopilot.core.member..", "com.sopilot.core.outbox..",
                    "com.sopilot.core.storage..", "com.sopilot.core.workspace..");

    /** Baseline exception: WebConfig registers the security argument resolver (Spring MVC wiring only). */
    @ArchTest
    static final ArchRule modulesAreFreeOfCycles = slices()
            .matching("com.sopilot.core.(*)..")
            .should().beFreeOfCycles()
            .ignoreDependency(WebConfig.class, PrincipalArgumentResolver.class);

    /** Use SLF4J; never print tokens or stack traces to stdout. */
    @ArchTest
    static final ArchRule noStandardStreams = NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS;
}

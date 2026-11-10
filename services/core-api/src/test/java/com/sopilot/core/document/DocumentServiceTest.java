package com.sopilot.core.document;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.category.CategoryRepository;
import com.sopilot.core.category.CategoryRepository.Category;
import com.sopilot.core.category.CategoryRepository.CategoryStatus;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.config.QuotaProperties;
import com.sopilot.core.department.DepartmentRepository;
import com.sopilot.core.department.DepartmentRepository.Department;
import com.sopilot.core.department.DepartmentRepository.DepartmentStatus;
import com.sopilot.core.document.DocumentRepository.CategoryRef;
import com.sopilot.core.document.DocumentRepository.DepartmentRef;
import com.sopilot.core.document.DocumentRepository.DocumentDetail;
import com.sopilot.core.document.DocumentRepository.DocumentHead;
import com.sopilot.core.document.DocumentRepository.FieldSources;
import com.sopilot.core.document.DocumentRepository.MetaSources;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.outbox.OutboxDispatcher;
import com.sopilot.core.outbox.OutboxService;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import com.sopilot.core.storage.StorageClient;
import com.sopilot.core.tag.TagService;
import com.sopilot.core.tenancy.TenantTx;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.function.Supplier;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * Unit tests of {@link DocumentService} with mocked collaborators (no Docker): the ADR-007 §4.4 read
 * matrix and manager-only writes, metadata field sources, and category rules (TECH-V2-core-api §5.5-§5.6).
 */
class DocumentServiceTest {

    private final UUID wid = UUID.randomUUID();
    private final UUID docId = UUID.randomUUID();
    private final UUID deptA = UUID.randomUUID();
    private final UUID deptB = UUID.randomUUID();
    private final UUID categoryId = UUID.randomUUID();

    private final AuthPrincipal owner = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.OWNER, null);
    private final AuthPrincipal admin = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.ADMIN, null);
    private final AuthPrincipal memberA = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.MEMBER, deptA);
    private final AuthPrincipal memberB = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.MEMBER, deptB);
    private final AuthPrincipal memberNoDept = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.MEMBER, null);

    private DocumentRepository docs;
    private CategoryRepository categories;
    private DepartmentRepository departments;
    private TagService tags;
    private StorageClient storage;
    private OutboxService outbox;
    private OutboxDispatcher dispatcher;
    private AuditService audit;
    private DocumentService service;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        docs = mock(DocumentRepository.class);
        categories = mock(CategoryRepository.class);
        departments = mock(DepartmentRepository.class);
        tags = mock(TagService.class);
        storage = mock(StorageClient.class);
        outbox = mock(OutboxService.class);
        dispatcher = mock(OutboxDispatcher.class);
        audit = mock(AuditService.class);
        TenantTx tenant = mock(TenantTx.class);
        when(tenant.run(any(AuthPrincipal.class), any())).thenAnswer(i -> ((Supplier<?>) i.getArgument(1)).get());
        when(tenant.run(any(UUID.class), any(), any())).thenAnswer(i -> ((Supplier<?>) i.getArgument(2)).get());
        service = new DocumentService(docs, categories, departments, tags, storage, outbox, dispatcher, audit, tenant,
                new QuotaProperties(0, 0));
    }

    // ---- fixtures -------------------------------------------------------------------------------

    private VersionRow version() {
        return new VersionRow(UUID.randomUUID(), docId, 1, "READY", null, null, "sop.md", "text/markdown", "MD",
                10L, new byte[32], "object-key", 1, "vi", null, null, LocalDate.now(), new String[0], 0,
                OffsetDateTime.now());
    }

    private DocumentDetail detail(String visibility, List<DepartmentRef> departmentRefs) {
        VersionRow v = version();
        return new DocumentDetail(docId, "Title", null, "vi", visibility, 1L, owner.userId(), "Creator",
                OffsetDateTime.now(), OffsetDateTime.now(), v, v, null, List.of(), departmentRefs,
                new FieldSources("SYSTEM", "SYSTEM", "SYSTEM", "SYSTEM", "SYSTEM"));
    }

    /** The ADR-007 §4.4 read rule, applied by the mocked repository exactly as the SQL filter does. */
    private void stubReadRule(String visibility, Set<UUID> documentDepartments) {
        List<DepartmentRef> refs = documentDepartments.stream().map(d -> new DepartmentRef(d, "dept")).toList();
        DocumentDetail detail = detail(visibility, refs);
        when(docs.findVisible(any(AuthPrincipal.class), eq(docId))).thenAnswer(i -> {
            AuthPrincipal p = i.getArgument(0);
            boolean allowed = p.isManager() || "WORKSPACE".equals(visibility)
                    || (p.departmentId() != null && documentDepartments.contains(p.departmentId()));
            return allowed ? Optional.of(detail) : Optional.empty();
        });
        when(storage.presignGet(anyString(), anyString(), any())).thenReturn("https://download");
    }

    private static void assertApi(Runnable call, HttpStatus status, String code) {
        assertThatThrownBy(call::run).isInstanceOfSatisfying(ApiException.class, e -> {
            assertThat(e.status()).isEqualTo(status);
            assertThat(e.code()).isEqualTo(code);
        });
    }

    private void stubExistingDocument(MetaSources sources) {
        when(docs.lockDocument(wid, docId)).thenReturn(Optional.of(
                new DocumentHead(docId, sources.title(), "WORKSPACE", 1, null, UUID.randomUUID())));
        when(docs.metaSources(wid, docId)).thenReturn(sources);
        when(docs.findDetail(wid, docId)).thenReturn(Optional.of(detail("WORKSPACE", List.of())));
    }

    private static MetaSources systemSources(UUID category) {
        return new MetaSources("Old title", "SYSTEM", "Old description", "SYSTEM", category, "SUGGESTED", "vi",
                "SYSTEM", "SUGGESTED");
    }

    private static byte[] markdown() {
        return "# SOP\n\nBody\n".getBytes(StandardCharsets.UTF_8);
    }

    private Category category(CategoryStatus status) {
        return new Category(categoryId, wid, "Policies", status, OffsetDateTime.now(), OffsetDateTime.now());
    }

    private Department department(UUID id, DepartmentStatus status) {
        return new Department(id, wid, "Dept", status, OffsetDateTime.now(), OffsetDateTime.now());
    }

    // ---- permission matrix ----------------------------------------------------------------------

    @Test
    void workspaceDocumentIsReadableByEveryMemberOfTheWorkspace() {
        stubReadRule("WORKSPACE", Set.of());

        for (AuthPrincipal viewer : List.of(owner, admin, memberA, memberB, memberNoDept)) {
            assertThat(service.get(viewer, docId).id()).isEqualTo(docId);
            assertThat(service.downloadUrl(viewer, docId).url()).isEqualTo("https://download");
        }
    }

    @Test
    void departmentsDocumentIsReadableByManagersAndMembersOfAListedDepartmentOnly() {
        stubReadRule("DEPARTMENTS", Set.of(deptA));

        for (AuthPrincipal allowed : List.of(owner, admin, memberA)) {
            assertThat(service.get(allowed, docId).id()).isEqualTo(docId);
            assertThat(service.downloadUrl(allowed, docId).url()).isEqualTo("https://download");
        }
        for (AuthPrincipal denied : List.of(memberB, memberNoDept)) {
            assertApi(() -> service.get(denied, docId), HttpStatus.NOT_FOUND, "NOT_FOUND");
            assertApi(() -> service.downloadUrl(denied, docId), HttpStatus.NOT_FOUND, "NOT_FOUND");
        }
    }

    @Test
    void membersNeverSeeDepartmentsOrFieldSourcesButManagersDo() {
        stubReadRule("DEPARTMENTS", Set.of(deptA));

        DocumentView asMember = service.get(memberA, docId);
        DocumentView asAdmin = service.get(admin, docId);

        assertThat(asMember.departments()).isNull();
        assertThat(asMember.fieldSources()).isNull();
        assertThat(asAdmin.departments()).hasSize(1);
        assertThat(asAdmin.fieldSources()).isNotNull();
    }

    @Test
    void membersCannotWrite() {
        AuthPrincipal member = memberA;

        assertApi(() -> service.update(member, docId, Map.of("title", "x")), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertApi(() -> service.updateVisibility(member, docId, "WORKSPACE", List.of()), HttpStatus.FORBIDDEN,
                "FORBIDDEN");
        assertApi(() -> service.upload(member, "a.md", markdown(), "WORKSPACE"), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertApi(() -> service.uploadVersion(member, docId, "a.md", markdown()), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertApi(() -> service.retry(member, docId), HttpStatus.FORBIDDEN, "FORBIDDEN");
        assertApi(() -> service.delete(member, docId), HttpStatus.FORBIDDEN, "FORBIDDEN");

        verifyNoInteractions(docs, outbox, dispatcher, storage, audit, tags);
    }

    // ---- metadata field sources -----------------------------------------------------------------

    @Test
    void patchingOnlyTheTitleMakesTheTitleUserAndLeavesTheOtherSourcesAlone() {
        stubExistingDocument(systemSources(null));

        service.update(admin, docId, Map.of("title", "  New title  "));

        verify(docs).updateMetadata(wid, docId, "New title", "USER", "Old description", "SYSTEM", null, "SUGGESTED",
                "vi", "SYSTEM", "SUGGESTED");
    }

    @Test
    void patchingDescriptionLanguageCategoryAndTagsMakesEachOfThemUserButNotTheTitle() {
        stubExistingDocument(systemSources(null));
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ACTIVE)));

        service.update(owner, docId, Map.of("description", "New description", "language", "en",
                "categoryId", categoryId.toString(), "tags", List.of("ISO")));

        verify(tags).assignTags(wid, docId, List.of("ISO"));
        verify(docs).updateMetadata(wid, docId, "Old title", "SYSTEM", "New description", "USER", categoryId, "USER",
                "en", "USER", "USER");
    }

    @Test
    void clearingTheCategoryOrADescriptionIsAUserDecisionToo() {
        stubExistingDocument(systemSources(categoryId));
        Map<String, Object> patch = new java.util.HashMap<>();
        patch.put("categoryId", null);
        patch.put("description", null);

        service.update(owner, docId, patch);

        verify(docs).updateMetadata(wid, docId, "Old title", "SYSTEM", null, "USER", null, "USER", "vi", "SYSTEM",
                "SUGGESTED");
    }

    @Test
    void unknownEmptyAndMalformedPatchesAreRejectedBeforeAnythingIsWritten() {
        stubExistingDocument(systemSources(null));

        assertApi(() -> service.update(owner, docId, Map.of()), HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");
        assertApi(() -> service.update(owner, docId, Map.of("visibility", "WORKSPACE")), HttpStatus.BAD_REQUEST,
                "VALIDATION_FAILED");
        assertApi(() -> service.update(owner, docId, Map.of("title", "x".repeat(201))), HttpStatus.BAD_REQUEST,
                "VALIDATION_FAILED");
        assertApi(() -> service.update(owner, docId, Map.of("categoryId", "not-a-uuid")), HttpStatus.BAD_REQUEST,
                "VALIDATION_FAILED");

        verify(docs, never()).updateMetadata(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(),
                any());
    }

    // ---- category rules -------------------------------------------------------------------------

    @Test
    void anArchivedCategoryCannotBeAssignedByPatch() {
        stubExistingDocument(systemSources(null));
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ARCHIVED)));

        assertApi(() -> service.update(owner, docId, Map.of("categoryId", categoryId.toString())),
                HttpStatus.BAD_REQUEST, "CATEGORY_ARCHIVED");

        verify(docs, never()).updateMetadata(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(),
                any());
    }

    @Test
    void aCategoryOfAnotherWorkspaceIsNotFoundOnPatch() {
        stubExistingDocument(systemSources(null));
        when(categories.find(wid, categoryId)).thenReturn(Optional.empty());

        assertApi(() -> service.update(owner, docId, Map.of("categoryId", categoryId.toString())),
                HttpStatus.NOT_FOUND, "NOT_FOUND");
    }

    @Test
    void anArchivedCategoryCannotBeAssignedByUploadAndNothingIsStored() {
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ARCHIVED)));

        assertApi(() -> service.upload(owner, "a.md", markdown(), "WORKSPACE", null, categoryId, null, null),
                HttpStatus.BAD_REQUEST, "CATEGORY_ARCHIVED");

        verify(docs, never()).insertDocument(any(), any(), any(), any(), any(), any(), any(), any(), any(), any());
        verifyNoInteractions(storage, outbox);
    }

    @Test
    void uploadWithAnActiveCategoryAndTagsRecordsThemAsUserChoices() {
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ACTIVE)));
        when(docs.findDetail(eq(wid), any())).thenReturn(Optional.of(detail("WORKSPACE", List.of())));

        service.upload(owner, "Quy trinh.md", markdown(), null, null, categoryId, List.of("ISO"), null);

        verify(docs).insertDocument(any(), eq(wid), eq("Quy trinh"), eq("SYSTEM"), any(), eq(owner.userId()),
                eq("WORKSPACE"), eq(categoryId), eq("USER"), eq("USER"));
        verify(tags).assignTags(eq(wid), any(), eq(List.of("ISO")));
    }

    // ---- upload title and departments -----------------------------------------------------------

    @Test
    void anExplicitUploadTitleIsStrippedUsedInsteadOfTheFileNameAndMarkedUser() {
        when(docs.findDetail(eq(wid), any())).thenReturn(Optional.of(detail("WORKSPACE", List.of())));

        service.upload(owner, "file-name.md", markdown(), "WORKSPACE", null, null, null, "  My title ");

        verify(docs).insertDocument(any(), eq(wid), eq("My title"), eq("USER"), any(), any(), eq("WORKSPACE"), any(),
                eq("SYSTEM"), eq("SYSTEM"));
    }

    @Test
    void aBlankOrTooLongUploadTitleIsRejected() {
        assertApi(() -> service.upload(owner, "a.md", markdown(), "WORKSPACE", null, null, null, "  "),
                HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");
        assertApi(() -> service.upload(owner, "a.md", markdown(), "WORKSPACE", null, null, null, "x".repeat(201)),
                HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");

        verify(docs, never()).insertDocument(any(), any(), any(), any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void duplicateDepartmentIdsOnUploadAreStoredOnceInTheirOriginalOrder() {
        when(departments.find(wid, deptA)).thenReturn(Optional.of(department(deptA, DepartmentStatus.ACTIVE)));
        when(departments.find(wid, deptB)).thenReturn(Optional.of(department(deptB, DepartmentStatus.ACTIVE)));
        when(docs.findDetail(eq(wid), any())).thenReturn(Optional.of(detail("DEPARTMENTS", List.of())));

        service.upload(owner, "a.md", markdown(), "DEPARTMENTS", List.of(deptB, deptA, deptB, deptA), null, null, null);

        verify(docs).setDocumentDepartments(eq(wid), any(), eq(List.of(deptB, deptA)));
    }

    @Test
    void duplicateDepartmentIdsOnVisibilityChangeAreStoredOnce() {
        when(departments.find(wid, deptA)).thenReturn(Optional.of(department(deptA, DepartmentStatus.ACTIVE)));
        when(docs.lockDocument(wid, docId)).thenReturn(Optional.of(
                new DocumentHead(docId, "T", "WORKSPACE", 1, null, UUID.randomUUID())));

        service.updateVisibility(owner, docId, "DEPARTMENTS", List.of(deptA, deptA));

        verify(docs).setDocumentDepartments(wid, docId, List.of(deptA));
        verify(docs).updateVisibility(wid, docId, "DEPARTMENTS", 2L);
    }

    @Test
    void departmentErrorsUseFixedMessagesThatDoNotEchoTheId() {
        when(departments.find(wid, deptA)).thenReturn(Optional.empty());
        when(departments.find(wid, deptB)).thenReturn(Optional.of(department(deptB, DepartmentStatus.ARCHIVED)));

        for (UUID bad : List.of(deptA, deptB)) {
            assertThatThrownBy(() -> service.updateVisibility(owner, docId, "DEPARTMENTS", List.of(bad)))
                    .isInstanceOfSatisfying(ApiException.class, e -> {
                        assertThat(e.status()).isEqualTo(HttpStatus.BAD_REQUEST);
                        assertThat(e.clientMessage()).doesNotContain(bad.toString());
                    });
        }
        verify(docs, never()).updateVisibility(any(), any(), anyString(), anyLong());
    }
}

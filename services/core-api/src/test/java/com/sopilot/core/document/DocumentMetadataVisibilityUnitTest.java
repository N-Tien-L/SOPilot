package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.document.DocumentRepository.CategoryRef;
import com.sopilot.core.document.DocumentRepository.DepartmentRef;
import com.sopilot.core.document.DocumentRepository.DocumentDetail;
import com.sopilot.core.document.DocumentRepository.FieldSources;
import com.sopilot.core.document.DocumentRepository.VersionRow;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for metadata sources, view masking, and validation rules (ADR-007 §4.4, TECH-V2-core-api §5.5-§5.6).
 */
class DocumentMetadataVisibilityUnitTest {

    private final UUID wid = UUID.randomUUID();
    private final UUID userId = UUID.randomUUID();
    private final UUID deptA = UUID.randomUUID();
    private final UUID deptB = UUID.randomUUID();

    private VersionRow sampleVersion(UUID docId) {
        return new VersionRow(UUID.randomUUID(), docId, 1, "READY", null, null,
                "test.pdf", "application/pdf", "PDF", 1024L, new byte[32], "key",
                5, "vi", "DOC-01", "01", LocalDate.now(), new String[0], 0, OffsetDateTime.now(), userId);
    }

    private DocumentDetail sampleDetail(UUID docId, String visibility, List<DepartmentRef> depts) {
        VersionRow ver = sampleVersion(docId);
        CategoryRef cat = new CategoryRef(UUID.randomUUID(), "Finance");
        List<String> tags = List.of("ISO", "Finance");
        FieldSources sources = new FieldSources("USER", "SYSTEM", "SUGGESTED", "USER", "SYSTEM");
        return new DocumentDetail(docId, "Title", "Desc", "vi", visibility, 2L,
                userId, "Creator", OffsetDateTime.now(), OffsetDateTime.now(),
                ver, ver, cat, tags, depts, sources, null);
    }

    @Test
    void managersSeeDepartmentsAndFieldSourcesWhileMembersDoNot() {
        UUID docId = UUID.randomUUID();
        List<DepartmentRef> depts = List.of(new DepartmentRef(deptA, "Dept A"));
        DocumentDetail detail = sampleDetail(docId, "DEPARTMENTS", depts);

        AuthPrincipal owner = new AuthPrincipal(userId, wid, WorkspaceRole.OWNER, null);
        AuthPrincipal admin = new AuthPrincipal(userId, wid, WorkspaceRole.ADMIN, null);
        AuthPrincipal memberWithDept = new AuthPrincipal(userId, wid, WorkspaceRole.MEMBER, deptA);
        AuthPrincipal memberWithoutDept = new AuthPrincipal(userId, wid, WorkspaceRole.MEMBER, null);

        DocumentView ownerView = DocumentView.of(detail, owner);
        assertThat(ownerView.departments()).hasSize(1);
        assertThat(ownerView.departments().get(0).name()).isEqualTo("Dept A");
        assertThat(ownerView.fieldSources()).isNotNull();
        assertThat(ownerView.fieldSources().title()).isEqualTo("USER");
        assertThat(ownerView.category()).isNotNull();
        assertThat(ownerView.tags()).containsExactly("ISO", "Finance");

        DocumentView adminView = DocumentView.of(detail, admin);
        assertThat(adminView.departments()).isNotNull();
        assertThat(adminView.fieldSources()).isNotNull();

        DocumentView memberView = DocumentView.of(detail, memberWithDept);
        assertThat(memberView.departments()).isNull();
        assertThat(memberView.fieldSources()).isNull();
        // Category and tags remain visible to members
        assertThat(memberView.category().name()).isEqualTo("Finance");
        assertThat(memberView.tags()).containsExactly("ISO", "Finance");

        DocumentView noDeptMemberView = DocumentView.of(detail, memberWithoutDept);
        assertThat(noDeptMemberView.departments()).isNull();
        assertThat(noDeptMemberView.fieldSources()).isNull();
    }

    @Test
    void failureCodeAndMessageAreMaskedForMembers() {
        UUID docId = UUID.randomUUID();
        VersionRow failedVer = new VersionRow(UUID.randomUUID(), docId, 1, "FAILED",
                "NO_TEXT_LAYER", "PDF lacks text layer", "scan.pdf", "application/pdf", "PDF", 1024L,
                new byte[32], "key", 5, "vi", null, null, null, new String[0], 0, OffsetDateTime.now(), userId);
        DocumentDetail detail = new DocumentDetail(docId, "Scan", null, null, "WORKSPACE", 1L,
                userId, "Creator", OffsetDateTime.now(), OffsetDateTime.now(),
                failedVer, null, null, List.of(), List.of(), null, null);

        AuthPrincipal manager = new AuthPrincipal(userId, wid, WorkspaceRole.ADMIN, null);
        AuthPrincipal member = new AuthPrincipal(userId, wid, WorkspaceRole.MEMBER, null);

        DocumentView managerView = DocumentView.of(detail, manager);
        assertThat(managerView.latestVersion().failureCode()).isEqualTo("NO_TEXT_LAYER");
        assertThat(managerView.latestVersion().failureMessage()).isEqualTo("PDF lacks text layer");

        DocumentView memberView = DocumentView.of(detail, member);
        assertThat(memberView.latestVersion().failureCode()).isNull();
        assertThat(memberView.latestVersion().failureMessage()).isNull();
    }
}

package com.sopilot.core.category;

import com.sopilot.core.audit.AuditService;
import com.sopilot.core.category.CategoryRepository.Category;
import com.sopilot.core.category.CategoryRepository.CategoryStatus;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.security.WorkspaceRole;
import com.sopilot.core.tenancy.TenantTx;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Supplier;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/** Archive and delete rules of categories (TECH-V2-core-api §5.6) without a database. */
class CategoryServiceTest {

    private final UUID wid = UUID.randomUUID();
    private final UUID categoryId = UUID.randomUUID();
    private final AuthPrincipal admin = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.ADMIN, null);
    private final AuthPrincipal member = new AuthPrincipal(UUID.randomUUID(), wid, WorkspaceRole.MEMBER, null);

    private CategoryRepository categories;
    private AuditService audit;
    private CategoryService service;

    @BeforeEach
    void setUp() {
        categories = mock(CategoryRepository.class);
        audit = mock(AuditService.class);
        TenantTx tenant = mock(TenantTx.class);
        when(tenant.run(any(AuthPrincipal.class), any())).thenAnswer(i -> ((Supplier<?>) i.getArgument(1)).get());
        when(tenant.run(any(UUID.class), any(), any())).thenAnswer(i -> ((Supplier<?>) i.getArgument(2)).get());
        org.mockito.Mockito.doAnswer(i -> {
            ((Runnable) i.getArgument(2)).run();
            return null;
        }).when(tenant).runVoid(any(), any(), any());
        service = new CategoryService(categories, audit, tenant);
    }

    private Category category(CategoryStatus status) {
        return new Category(categoryId, wid, "Policies", status, OffsetDateTime.now(), OffsetDateTime.now());
    }

    @Test
    void archivingACategoryKeepsItsNameAndIsAudited() {
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ACTIVE)));

        service.update(admin, categoryId, null, CategoryStatus.ARCHIVED);

        verify(categories).update(wid, categoryId, "Policies", CategoryStatus.ARCHIVED);
        verify(audit).record(admin, "CATEGORY_ARCHIVED", "CATEGORY", categoryId, Map.of("name", "Policies"));
    }

    @Test
    void restoringAnArchivedCategoryIsAudited() {
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ARCHIVED)));

        service.update(admin, categoryId, null, CategoryStatus.ACTIVE);

        verify(categories).update(wid, categoryId, "Policies", CategoryStatus.ACTIVE);
        verify(audit).record(admin, "CATEGORY_RESTORED", "CATEGORY", categoryId, Map.of("name", "Policies"));
    }

    @Test
    void deletingACategoryRemovesItAndIsAudited() {
        when(categories.find(wid, categoryId)).thenReturn(Optional.of(category(CategoryStatus.ACTIVE)));

        service.delete(admin, categoryId);

        verify(categories).delete(wid, categoryId);
        verify(audit).record(admin, "CATEGORY_DELETED", "CATEGORY", categoryId, Map.of("name", "Policies"));
    }

    @Test
    void deletingAnUnknownCategoryIsNotFound() {
        when(categories.find(wid, categoryId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.delete(admin, categoryId)).isInstanceOfSatisfying(ApiException.class,
                e -> assertThat(e.status()).isEqualTo(HttpStatus.NOT_FOUND));
        verify(categories, never()).delete(any(), any());
    }

    @Test
    void membersCannotArchiveOrDeleteCategories() {
        assertThatThrownBy(() -> service.update(member, categoryId, null, CategoryStatus.ARCHIVED))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.status()).isEqualTo(HttpStatus.FORBIDDEN));
        assertThatThrownBy(() -> service.delete(member, categoryId))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.status()).isEqualTo(HttpStatus.FORBIDDEN));

        verifyNoInteractions(categories, audit);
    }
}

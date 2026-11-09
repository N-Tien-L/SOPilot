package com.sopilot.core.workspace;

import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.workspace.WorkspaceRepository.WorkspaceSummary;
import com.sopilot.core.workspace.WorkspaceService.Detail;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

/**
 * Workspaces (TECH-V2-core-api §5.2). Creating one also issues tokens, so {@code POST /api/v1/workspaces}
 * lives in {@code identity.WorkspaceSessionController}.
 */
@RestController
@RequestMapping("/api/v1/workspaces")
public class WorkspaceController {

    private final WorkspaceService service;

    public WorkspaceController(WorkspaceService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<List<WorkspaceView>> mine(AuthPrincipal principal) {
        return ApiResponse.of(service.listMine(principal).stream().map(WorkspaceView::of).toList());
    }

    @GetMapping("/current")
    public ApiResponse<Detail> current(AuthPrincipal principal) {
        return ApiResponse.of(service.current(principal));
    }

    @PatchMapping("/current")
    public ApiResponse<Detail> rename(AuthPrincipal principal, @Valid @RequestBody RenameRequest request) {
        return ApiResponse.of(service.rename(principal, request.name()));
    }

    @DeleteMapping("/current")
    public ResponseEntity<Void> delete(AuthPrincipal principal) {
        service.delete(principal);
        return ResponseEntity.noContent().build();
    }

    public record RenameRequest(@NotNull String name) {
    }

    public record WorkspaceView(UUID id, String name, String kind, String role, String status) {
        static WorkspaceView of(WorkspaceSummary w) {
            return new WorkspaceView(w.id(), w.name(), w.kind().name(), w.role().name(), w.status().name());
        }
    }
}

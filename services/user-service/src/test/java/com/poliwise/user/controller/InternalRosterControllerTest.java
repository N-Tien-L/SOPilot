package com.poliwise.user.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.poliwise.user.dto.roster.ClaimRosterRequest;
import com.poliwise.user.dto.roster.ClaimRosterResponse;
import com.poliwise.user.enums.UserRole;
import com.poliwise.user.security.InternalServiceAuthFilter;
import com.poliwise.user.service.EmployeeRosterService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class InternalRosterControllerTest {

    @Mock
    private EmployeeRosterService employeeRosterService;

    @InjectMocks
    private InternalRosterController internalRosterController;

    private MockMvc mockMvcWithFilter;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final String TEST_TOKEN = "test-internal-secret-token-12345";

    @BeforeEach
    void setUp() {
        InternalServiceAuthFilter filter = new InternalServiceAuthFilter(TEST_TOKEN);

        mockMvcWithFilter = MockMvcBuilders.standaloneSetup(internalRosterController)
                .addFilter(filter)
                .build();
    }

    @Test
    @DisplayName("POST /internal/v1/roster/claim: Claim thành công trả về 200 OK")
    void claimRoster_whenValid_shouldReturnOk() throws Exception {
        UUID userId = UUID.randomUUID();
        UUID deptId = UUID.randomUUID();
        ClaimRosterRequest request = new ClaimRosterRequest(
                "employee@company.com",
                "google-oauth2|123456"
        );
        ClaimRosterResponse response = new ClaimRosterResponse(
                userId,
                "employee@company.com",
                "employee@company.com",
                "Nguyễn Văn A",
                UserRole.USER,
                deptId,
                "Kỹ thuật",
                "ENG"
        );

        when(employeeRosterService.claimRoster(any(ClaimRosterRequest.class))).thenReturn(response);

        mockMvcWithFilter.perform(post("/internal/v1/roster/claim")
                        .header("X-Internal-Service", TEST_TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("employee@company.com"))
                .andExpect(jsonPath("$.fullName").value("Nguyễn Văn A"))
                .andExpect(jsonPath("$.departmentCode").value("ENG"))
                .andExpect(jsonPath("$.userId").value(userId.toString()));
    }

    @Test
    @DisplayName("POST /internal/v1/roster/claim: Chấp nhận header thay thế X-Internal-Token")
    void claimRoster_withAlternativeHeader_shouldReturnOk() throws Exception {
        UUID userId = UUID.randomUUID();
        UUID deptId = UUID.randomUUID();
        ClaimRosterRequest request = new ClaimRosterRequest(
                "employee@company.com",
                "google-oauth2|123456"
        );
        ClaimRosterResponse response = new ClaimRosterResponse(
                userId,
                "employee@company.com",
                "employee@company.com",
                "Nguyễn Văn A",
                UserRole.USER,
                deptId,
                "Kỹ thuật",
                "ENG"
        );

        when(employeeRosterService.claimRoster(any(ClaimRosterRequest.class))).thenReturn(response);

        mockMvcWithFilter.perform(post("/internal/v1/roster/claim")
                        .header("X-Internal-Token", TEST_TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("employee@company.com"))
                .andExpect(jsonPath("$.departmentCode").value("ENG"));
    }

    @Test
    @DisplayName("POST /internal/v1/roster/claim: Từ chối 401 khi token sai")
    void claimRoster_whenInvalidToken_shouldReturnUnauthorized() throws Exception {
        ClaimRosterRequest request = new ClaimRosterRequest(
                "employee@company.com",
                "google-oauth2|123456"
        );

        mockMvcWithFilter.perform(post("/internal/v1/roster/claim")
                        .header("X-Internal-Service", "wrong-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized());
    }
}

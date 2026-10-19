# Java / Spring Boot Test Patterns

## 1. Unit Test (Service Layer)
Use JUnit 5, Mockito, and AssertJ. Isolate the class under test.

```java
package com.sopilot.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import com.sopilot.auth.repository.UserRepository;
import com.sopilot.auth.domain.User;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import java.util.Optional;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private AuthService authService;

    @Test
    void login_ShouldReturnToken_WhenCredentialsAreValid() {
        // Arrange
        String username = "testuser";
        User mockUser = new User(username, "encodedPassword");
        when(userRepository.findByUsername(username)).thenReturn(Optional.of(mockUser));
        
        // Act
        String token = authService.login(username, "rawPassword");

        // Assert
        assertThat(token).isNotNull().isNotEmpty();
        verify(userRepository).findByUsername(username);
    }
}
```

## 2. Controller Test (WebMvcTest)
Mock the service layer and test HTTP serialization/deserialization.

```java
@WebMvcTest(AuthController.class)
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private AuthService authService;

    @Test
    void login_ShouldReturn200_WhenValidRequest() throws Exception {
        when(authService.login(anyString(), anyString())).thenReturn("jwt-token");

        mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"test\",\"password\":\"pass\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").value("jwt-token"));
    }
}
```

## 3. Repository Test (DataJpaTest)
```java
@DataJpaTest
class UserRepositoryTest {

    @Autowired
    private UserRepository userRepository;

    @Test
    void findByUsername_ShouldReturnUser_WhenExists() {
        User user = new User("tester", "pass");
        userRepository.save(user);

        Optional<User> found = userRepository.findByUsername("tester");

        assertThat(found).isPresent();
        assertThat(found.get().getUsername()).isEqualTo("tester");
    }
}
```

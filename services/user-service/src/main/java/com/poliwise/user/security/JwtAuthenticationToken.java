package com.poliwise.user.security;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.Collection;
import java.util.List;
import java.util.UUID;

public class JwtAuthenticationToken extends AbstractAuthenticationToken {

    private final UUID userId;
    private final String username;
    private final String email;
    private final UserRole role;
    private final AccountStatus status;
    private final UUID department;
    private final String token;

    public JwtAuthenticationToken(UUID userId, String username, String email,
                                  UserRole role, AccountStatus status, UUID department, String token,
                                  Collection<? extends GrantedAuthority> authorities) {
        super(authorities);
        this.userId = userId;
        this.username = username;
        this.email = email;
        this.role = role;
        this.status = status;
        this.department = department;
        this.token = token;
        setAuthenticated(true);
    }

    public static List<GrantedAuthority> buildAuthorities(UserRole role) {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }

    @Override
    public Object getCredentials() {
        return token;
    }

    @Override
    public Object getPrincipal() {
        return userId;
    }

    public UUID getUserId() {
        return userId;
    }

    public String getUsername() {
        return username;
    }

    public String getEmail() {
        return email;
    }

    public UserRole getRole() {
        return role;
    }

    public AccountStatus getStatus() {
        return status;
    }

    public UUID getDepartment() {
        return department;
    }
}

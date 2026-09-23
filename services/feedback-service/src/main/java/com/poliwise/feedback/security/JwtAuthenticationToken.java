package com.poliwise.feedback.security;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.Authentication;

import java.util.Collection;

public class JwtAuthenticationToken implements Authentication {

    private final UserPrincipal principal;
    private final String token;
    private final Collection<? extends GrantedAuthority> authorities;
    private boolean authenticated = true;

    public JwtAuthenticationToken(UserPrincipal principal, String token,
                                  Collection<? extends GrantedAuthority> authorities) {
        this.principal = principal;
        this.token = token;
        this.authorities = authorities;
    }

    @Override public Collection<? extends GrantedAuthority> getAuthorities() { return authorities; }
    @Override public Object getCredentials() { return token; }
    @Override public Object getDetails() { return null; }
    @Override public Object getPrincipal() { return principal; }
    @Override public boolean isAuthenticated() { return authenticated; }
    @Override public void setAuthenticated(boolean isAuthenticated) { this.authenticated = isAuthenticated; }
    @Override public String getName() { return principal != null ? principal.getUsername() : null; }
}

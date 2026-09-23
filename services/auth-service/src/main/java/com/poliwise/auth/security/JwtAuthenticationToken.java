package com.poliwise.auth.security;

import com.poliwise.auth.dto.auth.JwtPayload;
import com.poliwise.auth.enums.UserRole;
import java.util.Collection;
import java.util.List;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

public class JwtAuthenticationToken extends AbstractAuthenticationToken {

    private final JwtPayload payload;
    private final String rawToken;

    public JwtAuthenticationToken(JwtPayload payload, String rawToken, Collection<? extends GrantedAuthority> authorities) {
        super(authorities);
        this.payload = payload;
        this.rawToken = rawToken;
        setAuthenticated(true);
    }

    @Override
    public Object getCredentials() {
        return rawToken;
    }

    @Override
    public Object getPrincipal() {
        return payload;
    }

    public JwtPayload getPayload() {
        return payload;
    }

    public static List<GrantedAuthority> buildAuthorities(UserRole role) {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }
}

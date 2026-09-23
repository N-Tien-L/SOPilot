# Build stage
FROM eclipse-temurin:17-jdk-alpine AS builder

WORKDIR /app

COPY pom.xml ./
COPY .mvn .mvn
COPY mvnw ./
RUN sed -i 's/\r$//' mvnw && chmod +x mvnw

RUN ./mvnw dependency:go-offline -B

COPY src ./src

RUN touch .env && \
    ./mvnw verify -B && \
    mv target/*.jar app.jar

# Production stage
FROM eclipse-temurin:17-jre-alpine

RUN apk add --no-cache curl \
    && addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/app.jar app.jar

ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -XX:+UseContainerSupport"
ENV SPRING_PROFILES_ACTIVE=prod

USER appuser

EXPOSE 8083

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8083/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]

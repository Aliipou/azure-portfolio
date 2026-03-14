package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

const (
	tenantKey = "tenant_id"
	roleKey   = "user_role"
	subKey    = "subject"
)

// Logger returns a gin middleware that logs each request with method, path, status, and latency.
func Logger(log *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		log.Info("request",
			zap.String("method", c.Request.Method),
			zap.String("path", c.Request.URL.Path),
			zap.Int("status", c.Writer.Status()),
			zap.Duration("latency", time.Since(start)),
			zap.String("ip", c.ClientIP()),
			zap.String("tenant", c.GetString(tenantKey)),
			zap.String("sub", c.GetString(subKey)),
		)
	}
}

// CORS returns a gin middleware that sets permissive CORS headers for all origins.
func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID, X-User-Role")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// MaxBodySize returns a gin middleware that rejects requests with a body larger than maxBytes.
func MaxBodySize(maxBytes int64) gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.ContentLength > maxBytes {
			c.AbortWithStatusJSON(http.StatusRequestEntityTooLarge, gin.H{
				"error": fmt.Sprintf("request body exceeds limit of %d bytes", maxBytes),
			})
			return
		}
		c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, maxBytes)
		c.Next()
	}
}

// AuthClaims holds the fields extracted from a validated token or dev header.
type AuthClaims struct {
	Subject  string   `json:"sub"`
	TenantID string   `json:"tenant_id"`
	Roles    []string `json:"roles"`
}

// JWTMiddleware validates a Bearer token and populates tenant_id, user_role, and subject
// in the Gin context. In development mode (GIN_MODE != release) it also accepts a
// X-Dev-Claims header containing a JSON-encoded AuthClaims for local testing.
//
// Production use: configure JWKS_URI env var to point at the Azure Entra ID JWKS endpoint.
// The middleware validates the JWT signature, expiry, audience, and issuer.
//
// For the portfolio demonstration this ships with the dev-bypass path enabled;
// replacing validateJWT with a real JWKS verifier is the only change needed for prod.
func JWTMiddleware(isDev bool) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Dev bypass: accept X-Dev-Claims header (only when not in release mode)
		if isDev {
			if raw := c.GetHeader("X-Dev-Claims"); raw != "" {
				var claims AuthClaims
				if err := json.Unmarshal([]byte(raw), &claims); err != nil {
					c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": "invalid X-Dev-Claims JSON"})
					return
				}
				setClaims(c, claims)
				c.Next()
				return
			}
		}

		// Production path: validate Bearer token
		authHeader := c.GetHeader("Authorization")
		if !strings.HasPrefix(authHeader, "Bearer ") {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing or malformed Authorization header"})
			return
		}
		token := strings.TrimPrefix(authHeader, "Bearer ")

		claims, err := validateJWT(c.Request.Context(), token)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token: " + err.Error()})
			return
		}
		setClaims(c, claims)
		c.Next()
	}
}

func setClaims(c *gin.Context, claims AuthClaims) {
	c.Set(subKey, claims.Subject)
	c.Set(tenantKey, claims.TenantID)
	role := "viewer"
	if len(claims.Roles) > 0 {
		// Use the highest-privilege role present
		for _, r := range []string{"admin", "operator", "viewer"} {
			for _, cr := range claims.Roles {
				if strings.EqualFold(cr, r) {
					role = r
					break
				}
			}
			if role != "viewer" {
				break
			}
		}
	}
	c.Set(roleKey, role)
}

// validateJWT is the production JWT validation hook.
// Replace this with a real JWKS-based verifier (e.g. github.com/lestrrat-go/jwx/v2)
// pointed at your Azure Entra ID tenant's JWKS URI:
//
//	https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys
//
// The stub below rejects all tokens so the dev-bypass path is always used in local dev.
func validateJWT(_ context.Context, _ string) (AuthClaims, error) {
	return AuthClaims{}, fmt.Errorf("JWT validation not configured; set JWKS_URI and implement validateJWT")
}

// TenantMiddleware reads the X-Tenant-ID header and stores it in the Gin context.
// Returns HTTP 400 if the header is missing or empty.
// NOTE: when JWTMiddleware is in use, tenant_id is set from the token — this middleware
// is a fallback for unauthenticated endpoints or simple API-key flows.
func TenantMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Already set by JWT middleware? Skip.
		if c.GetString(tenantKey) != "" {
			c.Next()
			return
		}
		tenantID := c.GetHeader("X-Tenant-ID")
		if tenantID == "" {
			c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": "X-Tenant-ID header is required"})
			return
		}
		c.Set(tenantKey, tenantID)
		c.Next()
	}
}

// RoleMiddleware reads the X-User-Role header and stores it in the Gin context.
// Defaults to "viewer" if the header is absent and not already set by JWTMiddleware.
func RoleMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Already set by JWT middleware? Skip.
		if c.GetString(roleKey) != "" {
			c.Next()
			return
		}
		role := c.GetHeader("X-User-Role")
		if role == "" {
			role = "viewer"
		}
		c.Set(roleKey, role)
		c.Next()
	}
}

// RequireRole returns a gin middleware that enforces the caller has one of the allowed roles.
// Returns HTTP 403 if the role stored in context is not in the allowed list.
func RequireRole(allowed ...string) gin.HandlerFunc {
	set := make(map[string]struct{}, len(allowed))
	for _, r := range allowed {
		set[r] = struct{}{}
	}
	return func(c *gin.Context) {
		role := c.GetString(roleKey)
		if _, ok := set[role]; !ok {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": "insufficient role: " + role})
			return
		}
		c.Next()
	}
}

package api_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/aliipou/cloud-calibration/internal/api"
	"github.com/gin-gonic/gin"
)

// ── MaxBodySize ────────────────────────────────────────────────────────────────

func TestMaxBodySize_UnderLimit(t *testing.T) {
	r := gin.New()
	r.Use(api.MaxBodySize(1024))
	r.POST("/echo", func(c *gin.Context) { c.Status(http.StatusOK) })

	body := strings.Repeat("a", 512)
	req, _ := http.NewRequest(http.MethodPost, "/echo", strings.NewReader(body))
	req.ContentLength = int64(len(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestMaxBodySize_OverLimit(t *testing.T) {
	r := gin.New()
	r.Use(api.MaxBodySize(100))
	r.POST("/echo", func(c *gin.Context) { c.Status(http.StatusOK) })

	body := strings.Repeat("a", 512)
	req, _ := http.NewRequest(http.MethodPost, "/echo", strings.NewReader(body))
	req.ContentLength = int64(len(body))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("expected 413, got %d", w.Code)
	}
}

// ── JWTMiddleware dev bypass ───────────────────────────────────────────────────

func TestJWTMiddleware_DevBypass_ValidClaims(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(true)) // isDev=true
	r.GET("/me", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"tenant": c.GetString("tenant_id"),
			"role":   c.GetString("user_role"),
			"sub":    c.GetString("subject"),
		})
	})

	claims := `{"sub":"user-123","tenant_id":"acme","roles":["admin"]}`
	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	req.Header.Set("X-Dev-Claims", claims)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp map[string]string
	_ = json.NewDecoder(w.Body).Decode(&resp)
	if resp["tenant"] != "acme" {
		t.Errorf("tenant = %q, want %q", resp["tenant"], "acme")
	}
	if resp["role"] != "admin" {
		t.Errorf("role = %q, want %q", resp["role"], "admin")
	}
	if resp["sub"] != "user-123" {
		t.Errorf("sub = %q, want %q", resp["sub"], "user-123")
	}
}

func TestJWTMiddleware_DevBypass_OperatorRole(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(true))
	r.GET("/me", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"role": c.GetString("user_role")})
	})

	claims := `{"sub":"op-1","tenant_id":"acme","roles":["operator"]}`
	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	req.Header.Set("X-Dev-Claims", claims)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	var resp map[string]string
	_ = json.NewDecoder(w.Body).Decode(&resp)
	if resp["role"] != "operator" {
		t.Errorf("role = %q, want operator", resp["role"])
	}
}

func TestJWTMiddleware_DevBypass_EmptyRoles_DefaultsViewer(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(true))
	r.GET("/me", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"role": c.GetString("user_role")})
	})

	claims := `{"sub":"guest","tenant_id":"acme","roles":[]}`
	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	req.Header.Set("X-Dev-Claims", claims)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	var resp map[string]string
	_ = json.NewDecoder(w.Body).Decode(&resp)
	if resp["role"] != "viewer" {
		t.Errorf("role = %q, want viewer", resp["role"])
	}
}

func TestJWTMiddleware_DevBypass_InvalidJSON(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(true))
	r.GET("/me", func(c *gin.Context) { c.Status(http.StatusOK) })

	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	req.Header.Set("X-Dev-Claims", "not-valid-json")

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestJWTMiddleware_ProdMode_MissingBearerToken(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(false)) // isDev=false
	r.GET("/me", func(c *gin.Context) { c.Status(http.StatusOK) })

	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	// No Authorization header

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}

func TestJWTMiddleware_ProdMode_InvalidBearerToken(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(false))
	r.GET("/me", func(c *gin.Context) { c.Status(http.StatusOK) })

	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	req.Header.Set("Authorization", "Bearer invalid.token.here")

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}

func TestJWTMiddleware_DevBypassDisabled_InProdMode(t *testing.T) {
	r := gin.New()
	r.Use(api.JWTMiddleware(false)) // isDev=false — dev bypass must be ignored
	r.GET("/me", func(c *gin.Context) { c.Status(http.StatusOK) })

	// Sending X-Dev-Claims in prod mode should NOT grant access
	claims := `{"sub":"attacker","tenant_id":"victim","roles":["admin"]}`
	req, _ := http.NewRequest(http.MethodGet, "/me", nil)
	req.Header.Set("X-Dev-Claims", claims)

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code == http.StatusOK {
		t.Fatal("X-Dev-Claims must not grant access when isDev=false (prod mode)")
	}
}

// ── TenantMiddleware ───────────────────────────────────────────────────────────

func TestTenantMiddleware_Missing(t *testing.T) {
	r := gin.New()
	r.Use(api.TenantMiddleware())
	r.GET("/", func(c *gin.Context) { c.Status(http.StatusOK) })

	req, _ := http.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestTenantMiddleware_Present(t *testing.T) {
	r := gin.New()
	r.Use(api.TenantMiddleware())
	r.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"tenant": c.GetString("tenant_id")})
	})

	req, _ := http.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("X-Tenant-ID", "acme")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]string
	_ = json.NewDecoder(w.Body).Decode(&resp)
	if resp["tenant"] != "acme" {
		t.Errorf("tenant = %q, want acme", resp["tenant"])
	}
}

func TestTenantMiddleware_SkipsIfAlreadySet(t *testing.T) {
	// When JWT middleware already set tenant_id, TenantMiddleware must not overwrite it
	r := gin.New()
	r.Use(func(c *gin.Context) {
		c.Set("tenant_id", "from-jwt") // simulate JWT middleware
		c.Next()
	})
	r.Use(api.TenantMiddleware())
	r.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"tenant": c.GetString("tenant_id")})
	})

	req, _ := http.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("X-Tenant-ID", "from-header") // should be ignored
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	var resp map[string]string
	_ = json.NewDecoder(w.Body).Decode(&resp)
	if resp["tenant"] != "from-jwt" {
		t.Errorf("tenant = %q, want from-jwt (JWT value must win)", resp["tenant"])
	}
}

// ── RequireRole ───────────────────────────────────────────────────────────────

func TestRequireRole_Allowed(t *testing.T) {
	r := gin.New()
	r.Use(func(c *gin.Context) { c.Set("user_role", "admin"); c.Next() })
	r.GET("/", api.RequireRole("admin", "operator"), func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	req, _ := http.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestRequireRole_Forbidden(t *testing.T) {
	r := gin.New()
	r.Use(func(c *gin.Context) { c.Set("user_role", "viewer"); c.Next() })
	r.GET("/", api.RequireRole("admin", "operator"), func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	req, _ := http.NewRequest(http.MethodGet, "/", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d", w.Code)
	}
}


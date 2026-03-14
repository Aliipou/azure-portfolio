package config

import (
	"fmt"

	"github.com/spf13/viper"
)

// Config holds all runtime configuration read from environment variables.
type Config struct {
	Port           string
	PostgresURL    string
	GinMode        string
	JWKSUri        string // Azure Entra ID JWKS endpoint; empty = dev mode
	MaxBodyBytes   int64  // HTTP request body size limit
}

// Load reads configuration from environment variables with sensible defaults.
func Load() (*Config, error) {
	viper.AutomaticEnv()
	viper.SetDefault("PORT", "8080")
	viper.SetDefault("GIN_MODE", "release")
	viper.SetDefault("MAX_BODY_BYTES", 4*1024*1024) // 4 MB

	cfg := &Config{
		Port:         viper.GetString("PORT"),
		PostgresURL:  viper.GetString("DATABASE_URL"),
		GinMode:      viper.GetString("GIN_MODE"),
		JWKSUri:      viper.GetString("JWKS_URI"),
		MaxBodyBytes: viper.GetInt64("MAX_BODY_BYTES"),
	}

	if cfg.PostgresURL == "" {
		return nil, fmt.Errorf("DATABASE_URL environment variable is required")
	}

	return cfg, nil
}

// IsDev returns true when running outside release mode (local development).
func (c *Config) IsDev() bool {
	return c.GinMode != "release"
}

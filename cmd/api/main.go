package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aliipou/cloud-calibration/internal/api"
	"github.com/aliipou/cloud-calibration/internal/calibration"
	"github.com/aliipou/cloud-calibration/internal/config"
	"github.com/aliipou/cloud-calibration/internal/store"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "load config: %v\n", err)
		os.Exit(1)
	}

	log, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "init logger: %v\n", err)
		os.Exit(1)
	}
	defer log.Sync() //nolint:errcheck

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	pg, err := store.NewPostgresStore(ctx, cfg.PostgresURL)
	if err != nil {
		log.Fatal("connect postgres", zap.Error(err))
	}
	defer pg.Close()

	if err := pg.Migrate(ctx); err != nil {
		log.Fatal("run migrations", zap.Error(err))
	}
	log.Info("database migrations applied")

	engine := calibration.New()

	if cfg.IsDev() {
		log.Warn("running in DEVELOPMENT mode — JWT validation bypassed via X-Dev-Claims header")
	}

	gin.SetMode(cfg.GinMode)
	r := gin.New()
	r.Use(
		api.Logger(log),
		api.CORS(),
		api.MaxBodySize(cfg.MaxBodyBytes),
		gin.Recovery(),
	)

	handler := api.NewHandler(pg, pg, engine, log).WithPinger(pg)
	handler.RegisterRoutes(r)

	srv := &http.Server{
		Addr:         fmt.Sprintf(":%s", cfg.Port),
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		log.Info("API server listening", zap.String("port", cfg.Port))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatal("listen and serve", zap.Error(err))
		}
	}()

	<-ctx.Done()
	log.Info("shutdown signal received")

	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutCtx); err != nil {
		log.Error("graceful shutdown", zap.Error(err))
	}
	log.Info("server stopped")
}

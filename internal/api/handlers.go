package api

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aliipou/cloud-calibration/internal/calibration"
	"github.com/aliipou/cloud-calibration/internal/models"
	"github.com/aliipou/cloud-calibration/internal/store"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"go.uber.org/zap"
)

// Handler holds all HTTP handler dependencies.
type Handler struct {
	devices      store.DeviceStore
	calibrations store.CalibrationStore
	engine       *calibration.Engine
	db           store.Pinger
	log          *zap.Logger
}

// NewHandler creates a Handler wired to the given stores and calibration engine.
func NewHandler(ds store.DeviceStore, cs store.CalibrationStore, eng *calibration.Engine, log *zap.Logger) *Handler {
	return &Handler{
		devices:      ds,
		calibrations: cs,
		engine:       eng,
		log:          log,
	}
}

// WithPinger sets the database pinger used by the readiness probe.
func (h *Handler) WithPinger(p store.Pinger) *Handler {
	h.db = p
	return h
}

// RegisterRoutes wires all HTTP routes to the gin engine.
func (h *Handler) RegisterRoutes(r *gin.Engine) {
	r.GET("/healthz", h.Healthz)
	r.GET("/readyz", h.Readyz)
	r.GET("/", func(c *gin.Context) { c.Redirect(http.StatusFound, "/web/") })
	r.Static("/web", "./web")

	api := r.Group("/api/v1", TenantMiddleware(), RoleMiddleware())
	{
		// Devices
		devices := api.Group("/devices")
		devices.GET("", h.ListDevices)
		devices.GET("/:id", h.GetDevice)
		devices.POST("", RequireRole("operator", "admin"), h.CreateDevice)
		devices.PUT("/:id", RequireRole("operator", "admin"), h.UpdateDevice)
		devices.POST("/:id/calibrations", RequireRole("operator", "admin"), h.CreateCalibration)
		devices.GET("/:id/calibrations", h.ListDeviceCalibrations)

		// Calibrations
		cals := api.Group("/calibrations")
		cals.GET("", h.ListCalibrations)
		cals.GET("/:id", h.GetCalibration)

		// Analytics
		analytics := api.Group("/analytics")
		analytics.GET("/summary", h.GetAnalyticsSummary)
		analytics.GET("/devices/:id/trend", h.GetDeviceTrend)
	}
}

// ── Healthz ───────────────────────────────────────────────────────────────────

// Healthz returns a liveness check response (always 200 if process is running).
func (h *Handler) Healthz(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok", "time": time.Now().UTC()})
}

// Readyz checks database connectivity for Kubernetes readiness probes.
func (h *Handler) Readyz(c *gin.Context) {
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
		return
	}
	if err := h.db.Ping(c.Request.Context()); err != nil {
		h.log.Warn("readyz: db ping failed", zap.Error(err))
		c.JSON(http.StatusServiceUnavailable, gin.H{"status": "unavailable", "error": "database unreachable"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

// ── Devices ───────────────────────────────────────────────────────────────────

// ListDevices returns a paginated list of devices for the authenticated tenant.
func (h *Handler) ListDevices(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	limit, offset := parsePagination(c, 50, 200)

	devices, total, err := h.devices.ListDevices(c.Request.Context(), tenantID, limit, offset)
	if err != nil {
		h.log.Error("list devices", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list devices"})
		return
	}
	if devices == nil {
		devices = []*models.Device{}
	}
	c.JSON(http.StatusOK, gin.H{"devices": devices, "total": total, "limit": limit, "offset": offset})
}

// GetDevice retrieves a single device by ID for the authenticated tenant.
func (h *Handler) GetDevice(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	device, err := h.devices.GetDevice(c.Request.Context(), c.Param("id"), tenantID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	c.JSON(http.StatusOK, device)
}

// CreateDevice creates a new calibration device for the authenticated tenant.
func (h *Handler) CreateDevice(c *gin.Context) {
	var req models.CreateDeviceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	tenantID := c.GetString(tenantKey)
	device, err := h.devices.CreateDevice(c.Request.Context(), tenantID, &req)
	if err != nil {
		if isDuplicateError(err) {
			c.JSON(http.StatusConflict, gin.H{"error": "serial number already registered for this tenant"})
			return
		}
		h.log.Error("create device", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create device"})
		return
	}
	c.JSON(http.StatusCreated, device)
}

// UpdateDevice applies a partial update to a device for the authenticated tenant.
func (h *Handler) UpdateDevice(c *gin.Context) {
	var req models.UpdateDeviceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	tenantID := c.GetString(tenantKey)
	device, err := h.devices.UpdateDevice(c.Request.Context(), c.Param("id"), tenantID, &req)
	if err != nil {
		h.log.Error("update device", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update device"})
		return
	}
	c.JSON(http.StatusOK, device)
}

// ── Calibrations ──────────────────────────────────────────────────────────────

// CreateCalibration submits a new calibration record for a device.
// The calibration engine evaluates each measurement and determines overall pass/fail.
func (h *Handler) CreateCalibration(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	deviceID := c.Param("id")

	device, err := h.devices.GetDevice(c.Request.Context(), deviceID, tenantID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}

	var req models.CreateCalibrationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	measuredAt := req.MeasuredAt
	if measuredAt.IsZero() {
		measuredAt = time.Now().UTC()
	}

	recordID := uuid.New().String()
	measurements, passCount, failCount := h.engine.EvaluateRecord(recordID, req.Measurements, device.TolerancePct)

	status := "pass"
	if failCount > 0 {
		status = "fail"
	}

	record := &models.CalibrationRecord{
		ID:           recordID,
		DeviceID:     deviceID,
		TenantID:     tenantID,
		OperatorName: req.OperatorName,
		TemperatureC: req.TemperatureC,
		HumidityPct:  req.HumidityPct,
		Status:       status,
		OverallPass:  failCount == 0,
		PassCount:    passCount,
		FailCount:    failCount,
		MeasuredAt:   measuredAt,
		CreatedAt:    time.Now().UTC(),
	}

	if err := h.calibrations.CreateRecord(c.Request.Context(), record, measurements); err != nil {
		h.log.Error("create calibration record", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create calibration record"})
		return
	}

	// Update device's last calibrated timestamp
	if err := h.devices.UpdateLastCalibratedAt(c.Request.Context(), deviceID, tenantID, measuredAt); err != nil {
		h.log.Warn("update last_calibrated_at", zap.Error(err))
	}

	record.Measurements = measurements
	c.JSON(http.StatusCreated, record)
}

// ListDeviceCalibrations returns paginated calibration records for a specific device.
func (h *Handler) ListDeviceCalibrations(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	limit, offset := parsePagination(c, 50, 200)

	records, total, err := h.calibrations.ListRecordsByDevice(c.Request.Context(), c.Param("id"), tenantID, limit, offset)
	if err != nil {
		h.log.Error("list device calibrations", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list calibrations"})
		return
	}
	if records == nil {
		records = []*models.CalibrationRecord{}
	}
	c.JSON(http.StatusOK, gin.H{"records": records, "total": total, "limit": limit, "offset": offset})
}

// ListCalibrations returns paginated calibration records tenant-wide.
func (h *Handler) ListCalibrations(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	limit, offset := parsePagination(c, 50, 200)

	records, total, err := h.calibrations.ListRecords(c.Request.Context(), tenantID, limit, offset)
	if err != nil {
		h.log.Error("list calibrations", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list calibrations"})
		return
	}
	if records == nil {
		records = []*models.CalibrationRecord{}
	}
	c.JSON(http.StatusOK, gin.H{"records": records, "total": total, "limit": limit, "offset": offset})
}

// GetCalibration retrieves a single calibration record by ID.
func (h *Handler) GetCalibration(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	record, err := h.calibrations.GetRecord(c.Request.Context(), c.Param("id"), tenantID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "calibration record not found"})
		return
	}
	c.JSON(http.StatusOK, record)
}

// ── Analytics ─────────────────────────────────────────────────────────────────

// GetAnalyticsSummary returns aggregated statistics for the authenticated tenant.
func (h *Handler) GetAnalyticsSummary(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	summary, err := h.calibrations.GetAnalyticsSummary(c.Request.Context(), tenantID)
	if err != nil {
		h.log.Error("get analytics summary", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get analytics summary"})
		return
	}
	c.JSON(http.StatusOK, summary)
}

// GetDeviceTrend returns the recent calibration trend for one device.
func (h *Handler) GetDeviceTrend(c *gin.Context) {
	tenantID := c.GetString(tenantKey)
	limit, _ := parsePagination(c, 20, 100)

	records, err := h.calibrations.GetDeviceTrend(c.Request.Context(), c.Param("id"), tenantID, limit)
	if err != nil {
		h.log.Error("get device trend", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get device trend"})
		return
	}
	if records == nil {
		records = []*models.CalibrationRecord{}
	}
	c.JSON(http.StatusOK, gin.H{"records": records, "device_id": c.Param("id")})
}

// ── helpers ───────────────────────────────────────────────────────────────────

// parsePagination reads limit/offset query params and clamps them to safe ranges.
func parsePagination(c *gin.Context, defaultLimit, maxLimit int) (limit, offset int) {
	limit, _ = strconv.Atoi(c.DefaultQuery("limit", strconv.Itoa(defaultLimit)))
	offset, _ = strconv.Atoi(c.DefaultQuery("offset", "0"))
	if limit <= 0 {
		limit = defaultLimit
	}
	if limit > maxLimit {
		limit = maxLimit
	}
	if offset < 0 {
		offset = 0
	}
	return
}

// isDuplicateError reports whether the error is a PostgreSQL unique-constraint violation (23505).
func isDuplicateError(err error) bool {
	return err != nil && strings.Contains(err.Error(), "23505")
}

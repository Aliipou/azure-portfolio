package store

import (
	"context"
	"time"

	"github.com/aliipou/cloud-calibration/internal/models"
)

// Pinger can check database connectivity.
type Pinger interface {
	Ping(ctx context.Context) error
}

// DeviceStore defines persistence operations for device records.
type DeviceStore interface {
	CreateDevice(ctx context.Context, tenantID string, req *models.CreateDeviceRequest) (*models.Device, error)
	ListDevices(ctx context.Context, tenantID string, limit, offset int) ([]*models.Device, int, error)
	GetDevice(ctx context.Context, id, tenantID string) (*models.Device, error)
	UpdateDevice(ctx context.Context, id, tenantID string, req *models.UpdateDeviceRequest) (*models.Device, error)
	UpdateLastCalibratedAt(ctx context.Context, id, tenantID string, t time.Time) error
}

// CalibrationStore defines persistence operations for calibration records and measurements.
type CalibrationStore interface {
	CreateRecord(ctx context.Context, record *models.CalibrationRecord, measurements []models.Measurement) error
	GetRecord(ctx context.Context, id, tenantID string) (*models.CalibrationRecord, error)
	ListRecordsByDevice(ctx context.Context, deviceID, tenantID string, limit, offset int) ([]*models.CalibrationRecord, int, error)
	ListRecords(ctx context.Context, tenantID string, limit, offset int) ([]*models.CalibrationRecord, int, error)
	GetAnalyticsSummary(ctx context.Context, tenantID string) (*models.AnalyticsSummary, error)
	GetDeviceTrend(ctx context.Context, deviceID, tenantID string, limit int) ([]*models.CalibrationRecord, error)
}

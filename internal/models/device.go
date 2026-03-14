package models

import "time"

// Device represents a calibration instrument managed on the platform.
type Device struct {
	ID               string     `json:"id" db:"id"`
	TenantID         string     `json:"tenant_id" db:"tenant_id"`
	Name             string     `json:"name" db:"name"`
	SerialNumber     string     `json:"serial_number" db:"serial_number"`
	DeviceType       string     `json:"device_type" db:"device_type"` // pressure | temperature | electrical | flow
	Location         string     `json:"location" db:"location"`
	Manufacturer     string     `json:"manufacturer" db:"manufacturer"`
	Model            string     `json:"model" db:"model"`
	TolerancePct     float64    `json:"tolerance_pct" db:"tolerance_pct"` // default 0.5
	IsActive         bool       `json:"is_active" db:"is_active"`
	LastCalibratedAt *time.Time `json:"last_calibrated_at,omitempty" db:"last_calibrated_at"`
	CreatedAt        time.Time  `json:"created_at" db:"created_at"`
}

// CreateDeviceRequest is the payload for creating a new device.
type CreateDeviceRequest struct {
	Name         string  `json:"name" binding:"required"`
	SerialNumber string  `json:"serial_number" binding:"required"`
	DeviceType   string  `json:"device_type" binding:"required,oneof=pressure temperature electrical flow"`
	Location     string  `json:"location" binding:"required"`
	Manufacturer string  `json:"manufacturer"`
	Model        string  `json:"model"`
	TolerancePct float64 `json:"tolerance_pct"` // default 0.5 if zero
}

// UpdateDeviceRequest is the payload for updating an existing device.
type UpdateDeviceRequest struct {
	Name         *string  `json:"name"`
	Location     *string  `json:"location"`
	Manufacturer *string  `json:"manufacturer"`
	Model        *string  `json:"model"`
	TolerancePct *float64 `json:"tolerance_pct"`
	IsActive     *bool    `json:"is_active"`
}

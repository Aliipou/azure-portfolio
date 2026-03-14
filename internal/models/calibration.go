package models

import "time"

// CalibrationRecord is the top-level record for one calibration event on a device.
type CalibrationRecord struct {
	ID           string        `json:"id"`
	DeviceID     string        `json:"device_id"`
	TenantID     string        `json:"tenant_id"`
	OperatorName string        `json:"operator_name"`
	TemperatureC *float64      `json:"temperature_c,omitempty"`
	HumidityPct  *float64      `json:"humidity_pct,omitempty"`
	Status       string        `json:"status"` // pending | pass | fail | invalid
	OverallPass  bool          `json:"overall_pass"`
	PassCount    int           `json:"pass_count"`
	FailCount    int           `json:"fail_count"`
	Measurements []Measurement `json:"measurements"`
	MeasuredAt   time.Time     `json:"measured_at"`
	CreatedAt    time.Time     `json:"created_at"`
}

// Measurement is a single measured-versus-reference data point within a record.
type Measurement struct {
	ID                  string  `json:"id"`
	RecordID            string  `json:"record_id"`
	MeasuredValue       float64 `json:"measured_value"`
	ReferenceValue      float64 `json:"reference_value"`
	Unit                string  `json:"unit"`
	Uncertainty         float64 `json:"uncertainty"`
	DeviationPct        float64 `json:"deviation_pct"`        // (measured-ref)/ref*100
	IsPass              bool    `json:"is_pass"`               // |deviation_pct| <= device.TolerancePct
	ExpandedUncertainty float64 `json:"expanded_uncertainty"` // 2*uncertainty (k=2, 95% CI)
}

// MeasurementInput is the user-supplied data for one measurement point.
type MeasurementInput struct {
	MeasuredValue  float64 `json:"measured_value" binding:"required"`
	ReferenceValue float64 `json:"reference_value" binding:"required"`
	Unit           string  `json:"unit" binding:"required"`
	Uncertainty    float64 `json:"uncertainty"`
}

// CreateCalibrationRequest is the payload for submitting a calibration record.
type CreateCalibrationRequest struct {
	OperatorName string             `json:"operator_name" binding:"required"`
	TemperatureC *float64           `json:"temperature_c"`
	HumidityPct  *float64           `json:"humidity_pct"`
	MeasuredAt   time.Time          `json:"measured_at"`
	Measurements []MeasurementInput `json:"measurements" binding:"required,min=1"`
}

// AnalyticsSummary holds aggregated statistics across all devices and records.
type AnalyticsSummary struct {
	TotalDevices  int     `json:"total_devices"`
	TotalRecords  int     `json:"total_records"`
	PassRate      float64 `json:"pass_rate"`
	RecentFails   int     `json:"recent_fails"`
}

package store

import (
	"context"
	_ "embed"
	"fmt"
	"time"

	"github.com/aliipou/cloud-calibration/internal/models"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed migrations/001_init.sql
var migrationSQL string

// PostgresStore implements DeviceStore and CalibrationStore using pgxpool.
type PostgresStore struct {
	pool *pgxpool.Pool
}

// NewPostgresStore creates a new connection pool and verifies connectivity.
func NewPostgresStore(ctx context.Context, connStr string) (*PostgresStore, error) {
	pool, err := pgxpool.New(ctx, connStr)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping postgres: %w", err)
	}
	return &PostgresStore{pool: pool}, nil
}

// Migrate runs the embedded SQL migration to create all tables.
func (s *PostgresStore) Migrate(ctx context.Context) error {
	_, err := s.pool.Exec(ctx, migrationSQL)
	if err != nil {
		return fmt.Errorf("run migration: %w", err)
	}
	return nil
}

// Ping verifies the database connection is alive.
func (s *PostgresStore) Ping(ctx context.Context) error {
	return s.pool.Ping(ctx)
}

// Close releases all pool connections.
func (s *PostgresStore) Close() {
	s.pool.Close()
}

// ── Devices ───────────────────────────────────────────────────────────────────

// CreateDevice inserts a new device record for the given tenant.
func (s *PostgresStore) CreateDevice(ctx context.Context, tenantID string, req *models.CreateDeviceRequest) (*models.Device, error) {
	tol := req.TolerancePct
	if tol == 0 {
		tol = 0.5
	}
	d := &models.Device{
		ID:           uuid.New().String(),
		TenantID:     tenantID,
		Name:         req.Name,
		SerialNumber: req.SerialNumber,
		DeviceType:   req.DeviceType,
		Location:     req.Location,
		Manufacturer: req.Manufacturer,
		Model:        req.Model,
		TolerancePct: tol,
		IsActive:     true,
	}
	_, err := s.pool.Exec(ctx, `
		INSERT INTO devices (id, tenant_id, name, serial_number, device_type, location, manufacturer, model, tolerance_pct, is_active)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
		d.ID, d.TenantID, d.Name, d.SerialNumber, d.DeviceType,
		d.Location, d.Manufacturer, d.Model, d.TolerancePct, d.IsActive,
	)
	if err != nil {
		return nil, fmt.Errorf("insert device: %w", err)
	}
	// Fetch back to get server-generated created_at
	return s.GetDevice(ctx, d.ID, tenantID)
}

// ListDevices returns a paginated list of devices scoped to the given tenant.
func (s *PostgresStore) ListDevices(ctx context.Context, tenantID string, limit, offset int) ([]*models.Device, int, error) {
	var total int
	if err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM devices WHERE tenant_id=$1`, tenantID).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count devices: %w", err)
	}

	rows, err := s.pool.Query(ctx, `
		SELECT id, tenant_id, name, serial_number, device_type, location, manufacturer, model,
		       tolerance_pct, is_active, last_calibrated_at, created_at
		FROM devices WHERE tenant_id=$1
		ORDER BY created_at DESC LIMIT $2 OFFSET $3`,
		tenantID, limit, offset,
	)
	if err != nil {
		return nil, 0, fmt.Errorf("list devices: %w", err)
	}
	defer rows.Close()

	var devices []*models.Device
	for rows.Next() {
		d, err := scanDevice(rows)
		if err != nil {
			return nil, 0, err
		}
		devices = append(devices, d)
	}
	return devices, total, nil
}

// GetDevice retrieves a single device by ID scoped to the tenant.
func (s *PostgresStore) GetDevice(ctx context.Context, id, tenantID string) (*models.Device, error) {
	row := s.pool.QueryRow(ctx, `
		SELECT id, tenant_id, name, serial_number, device_type, location, manufacturer, model,
		       tolerance_pct, is_active, last_calibrated_at, created_at
		FROM devices WHERE id=$1 AND tenant_id=$2`, id, tenantID)
	d, err := scanDevice(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("device not found")
		}
		return nil, err
	}
	return d, nil
}

// UpdateDevice applies partial updates to a device record.
func (s *PostgresStore) UpdateDevice(ctx context.Context, id, tenantID string, req *models.UpdateDeviceRequest) (*models.Device, error) {
	// Fetch current device to ensure it exists and apply partial update
	current, err := s.GetDevice(ctx, id, tenantID)
	if err != nil {
		return nil, err
	}

	if req.Name != nil {
		current.Name = *req.Name
	}
	if req.Location != nil {
		current.Location = *req.Location
	}
	if req.Manufacturer != nil {
		current.Manufacturer = *req.Manufacturer
	}
	if req.Model != nil {
		current.Model = *req.Model
	}
	if req.TolerancePct != nil {
		current.TolerancePct = *req.TolerancePct
	}
	if req.IsActive != nil {
		current.IsActive = *req.IsActive
	}

	_, err = s.pool.Exec(ctx, `
		UPDATE devices SET name=$1, location=$2, manufacturer=$3, model=$4,
		                   tolerance_pct=$5, is_active=$6
		WHERE id=$7 AND tenant_id=$8`,
		current.Name, current.Location, current.Manufacturer, current.Model,
		current.TolerancePct, current.IsActive, id, tenantID,
	)
	if err != nil {
		return nil, fmt.Errorf("update device: %w", err)
	}
	return s.GetDevice(ctx, id, tenantID)
}

// UpdateLastCalibratedAt sets the last calibration timestamp on a device.
func (s *PostgresStore) UpdateLastCalibratedAt(ctx context.Context, id, tenantID string, t time.Time) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE devices SET last_calibrated_at=$1 WHERE id=$2 AND tenant_id=$3`,
		t, id, tenantID,
	)
	return err
}

// ── Calibrations ──────────────────────────────────────────────────────────────

// CreateRecord persists a CalibrationRecord and all its Measurements in a single transaction.
func (s *PostgresStore) CreateRecord(ctx context.Context, record *models.CalibrationRecord, measurements []models.Measurement) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx) //nolint:errcheck

	_, err = tx.Exec(ctx, `
		INSERT INTO calibration_records
		    (id, device_id, tenant_id, operator_name, temperature_c, humidity_pct,
		     status, overall_pass, pass_count, fail_count, measured_at, created_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`,
		record.ID, record.DeviceID, record.TenantID, record.OperatorName,
		record.TemperatureC, record.HumidityPct, record.Status, record.OverallPass,
		record.PassCount, record.FailCount, record.MeasuredAt, record.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("insert calibration record: %w", err)
	}

	for _, m := range measurements {
		_, err = tx.Exec(ctx, `
			INSERT INTO calibration_measurements
			    (id, record_id, measured_value, reference_value, unit,
			     uncertainty, deviation_pct, expanded_uncertainty, is_pass)
			VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
			m.ID, m.RecordID, m.MeasuredValue, m.ReferenceValue, m.Unit,
			m.Uncertainty, m.DeviationPct, m.ExpandedUncertainty, m.IsPass,
		)
		if err != nil {
			return fmt.Errorf("insert measurement: %w", err)
		}
	}

	return tx.Commit(ctx)
}

// GetRecord retrieves a calibration record with its measurements by ID.
func (s *PostgresStore) GetRecord(ctx context.Context, id, tenantID string) (*models.CalibrationRecord, error) {
	row := s.pool.QueryRow(ctx, `
		SELECT id, device_id, tenant_id, operator_name, temperature_c, humidity_pct,
		       status, overall_pass, pass_count, fail_count, measured_at, created_at
		FROM calibration_records WHERE id=$1 AND tenant_id=$2`, id, tenantID)
	record, err := scanRecord(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("calibration record not found")
		}
		return nil, err
	}

	measurements, err := s.loadMeasurements(ctx, id)
	if err != nil {
		return nil, err
	}
	record.Measurements = measurements
	return record, nil
}

// ListRecordsByDevice returns paginated calibration records for a specific device.
func (s *PostgresStore) ListRecordsByDevice(ctx context.Context, deviceID, tenantID string, limit, offset int) ([]*models.CalibrationRecord, int, error) {
	var total int
	if err := s.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM calibration_records WHERE device_id=$1 AND tenant_id=$2`,
		deviceID, tenantID,
	).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count records: %w", err)
	}

	rows, err := s.pool.Query(ctx, `
		SELECT id, device_id, tenant_id, operator_name, temperature_c, humidity_pct,
		       status, overall_pass, pass_count, fail_count, measured_at, created_at
		FROM calibration_records WHERE device_id=$1 AND tenant_id=$2
		ORDER BY measured_at DESC LIMIT $3 OFFSET $4`,
		deviceID, tenantID, limit, offset,
	)
	if err != nil {
		return nil, 0, fmt.Errorf("list records by device: %w", err)
	}
	defer rows.Close()

	records, err := s.scanAndLoadRecords(ctx, rows)
	if err != nil {
		return nil, 0, err
	}
	return records, total, nil
}

// ListRecords returns paginated calibration records tenant-wide.
func (s *PostgresStore) ListRecords(ctx context.Context, tenantID string, limit, offset int) ([]*models.CalibrationRecord, int, error) {
	var total int
	if err := s.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM calibration_records WHERE tenant_id=$1`, tenantID,
	).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count records: %w", err)
	}

	rows, err := s.pool.Query(ctx, `
		SELECT id, device_id, tenant_id, operator_name, temperature_c, humidity_pct,
		       status, overall_pass, pass_count, fail_count, measured_at, created_at
		FROM calibration_records WHERE tenant_id=$1
		ORDER BY measured_at DESC LIMIT $2 OFFSET $3`,
		tenantID, limit, offset,
	)
	if err != nil {
		return nil, 0, fmt.Errorf("list records: %w", err)
	}
	defer rows.Close()

	records, err := s.scanAndLoadRecords(ctx, rows)
	if err != nil {
		return nil, 0, err
	}
	return records, total, nil
}

// GetAnalyticsSummary computes aggregated statistics across all tenant devices and records.
func (s *PostgresStore) GetAnalyticsSummary(ctx context.Context, tenantID string) (*models.AnalyticsSummary, error) {
	summary := &models.AnalyticsSummary{}

	if err := s.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM devices WHERE tenant_id=$1`, tenantID,
	).Scan(&summary.TotalDevices); err != nil {
		return nil, fmt.Errorf("count devices: %w", err)
	}

	var passCount int
	if err := s.pool.QueryRow(ctx, `
		SELECT
			COUNT(*) AS total,
			COUNT(*) FILTER (WHERE overall_pass = TRUE) AS pass_count
		FROM calibration_records WHERE tenant_id=$1`, tenantID,
	).Scan(&summary.TotalRecords, &passCount); err != nil {
		return nil, fmt.Errorf("count records: %w", err)
	}

	if summary.TotalRecords > 0 {
		summary.PassRate = float64(passCount) / float64(summary.TotalRecords) * 100
	}

	// Recent failures: last 7 days
	if err := s.pool.QueryRow(ctx, `
		SELECT COUNT(*) FROM calibration_records
		WHERE tenant_id=$1 AND overall_pass=FALSE AND created_at >= NOW() - INTERVAL '7 days'`,
		tenantID,
	).Scan(&summary.RecentFails); err != nil {
		return nil, fmt.Errorf("count recent fails: %w", err)
	}

	return summary, nil
}

// GetDeviceTrend returns the most recent N calibration records for one device.
func (s *PostgresStore) GetDeviceTrend(ctx context.Context, deviceID, tenantID string, limit int) ([]*models.CalibrationRecord, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT id, device_id, tenant_id, operator_name, temperature_c, humidity_pct,
		       status, overall_pass, pass_count, fail_count, measured_at, created_at
		FROM calibration_records WHERE device_id=$1 AND tenant_id=$2
		ORDER BY measured_at DESC LIMIT $3`,
		deviceID, tenantID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("get device trend: %w", err)
	}
	defer rows.Close()

	return s.scanAndLoadRecords(ctx, rows)
}

// ── helpers ───────────────────────────────────────────────────────────────────

type scannable interface {
	Scan(dest ...any) error
}

func scanDevice(row scannable) (*models.Device, error) {
	d := &models.Device{}
	err := row.Scan(
		&d.ID, &d.TenantID, &d.Name, &d.SerialNumber, &d.DeviceType,
		&d.Location, &d.Manufacturer, &d.Model, &d.TolerancePct,
		&d.IsActive, &d.LastCalibratedAt, &d.CreatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("scan device: %w", err)
	}
	return d, nil
}

func scanRecord(row scannable) (*models.CalibrationRecord, error) {
	r := &models.CalibrationRecord{}
	err := row.Scan(
		&r.ID, &r.DeviceID, &r.TenantID, &r.OperatorName,
		&r.TemperatureC, &r.HumidityPct, &r.Status, &r.OverallPass,
		&r.PassCount, &r.FailCount, &r.MeasuredAt, &r.CreatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("scan record: %w", err)
	}
	return r, nil
}

func (s *PostgresStore) loadMeasurements(ctx context.Context, recordID string) ([]models.Measurement, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT id, record_id, measured_value, reference_value, unit,
		       uncertainty, deviation_pct, expanded_uncertainty, is_pass
		FROM calibration_measurements WHERE record_id=$1
		ORDER BY id`, recordID)
	if err != nil {
		return nil, fmt.Errorf("load measurements: %w", err)
	}
	defer rows.Close()

	var ms []models.Measurement
	for rows.Next() {
		var m models.Measurement
		if err := rows.Scan(
			&m.ID, &m.RecordID, &m.MeasuredValue, &m.ReferenceValue, &m.Unit,
			&m.Uncertainty, &m.DeviationPct, &m.ExpandedUncertainty, &m.IsPass,
		); err != nil {
			return nil, fmt.Errorf("scan measurement: %w", err)
		}
		ms = append(ms, m)
	}
	return ms, nil
}

func (s *PostgresStore) scanAndLoadRecords(ctx context.Context, rows pgx.Rows) ([]*models.CalibrationRecord, error) {
	var records []*models.CalibrationRecord
	for rows.Next() {
		r, err := scanRecord(rows)
		if err != nil {
			return nil, err
		}
		measurements, err := s.loadMeasurements(ctx, r.ID)
		if err != nil {
			return nil, err
		}
		r.Measurements = measurements
		records = append(records, r)
	}
	return records, nil
}

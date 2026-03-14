package api_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/aliipou/cloud-calibration/internal/api"
	"github.com/aliipou/cloud-calibration/internal/calibration"
	"github.com/aliipou/cloud-calibration/internal/models"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

func init() {
	gin.SetMode(gin.TestMode)
}

// ── Fake stores ───────────────────────────────────────────────────────────────

type fakeDeviceStore struct {
	devices map[string]*models.Device
	err     error
}

func newFakeDeviceStore() *fakeDeviceStore {
	return &fakeDeviceStore{devices: map[string]*models.Device{}}
}

func (f *fakeDeviceStore) CreateDevice(_ context.Context, tenantID string, req *models.CreateDeviceRequest) (*models.Device, error) {
	if f.err != nil {
		return nil, f.err
	}
	tol := req.TolerancePct
	if tol == 0 {
		tol = 0.5
	}
	d := &models.Device{
		ID:           "dev-001",
		TenantID:     tenantID,
		Name:         req.Name,
		SerialNumber: req.SerialNumber,
		DeviceType:   req.DeviceType,
		Location:     req.Location,
		Manufacturer: req.Manufacturer,
		Model:        req.Model,
		TolerancePct: tol,
		IsActive:     true,
		CreatedAt:    time.Now(),
	}
	f.devices[d.ID] = d
	return d, nil
}

func (f *fakeDeviceStore) ListDevices(_ context.Context, tenantID string, limit, offset int) ([]*models.Device, int, error) {
	if f.err != nil {
		return nil, 0, f.err
	}
	var out []*models.Device
	for _, d := range f.devices {
		if d.TenantID == tenantID {
			out = append(out, d)
		}
	}
	return out, len(out), nil
}

func (f *fakeDeviceStore) GetDevice(_ context.Context, id, tenantID string) (*models.Device, error) {
	if f.err != nil {
		return nil, f.err
	}
	d, ok := f.devices[id]
	if !ok || d.TenantID != tenantID {
		return nil, errors.New("not found")
	}
	return d, nil
}

func (f *fakeDeviceStore) UpdateDevice(_ context.Context, id, tenantID string, req *models.UpdateDeviceRequest) (*models.Device, error) {
	if f.err != nil {
		return nil, f.err
	}
	d, ok := f.devices[id]
	if !ok || d.TenantID != tenantID {
		return nil, errors.New("not found")
	}
	if req.Name != nil {
		d.Name = *req.Name
	}
	if req.Location != nil {
		d.Location = *req.Location
	}
	if req.IsActive != nil {
		d.IsActive = *req.IsActive
	}
	return d, nil
}

func (f *fakeDeviceStore) UpdateLastCalibratedAt(_ context.Context, id, tenantID string, t time.Time) error {
	if f.err != nil {
		return f.err
	}
	d, ok := f.devices[id]
	if !ok || d.TenantID != tenantID {
		return errors.New("not found")
	}
	d.LastCalibratedAt = &t
	return nil
}

type fakeCalibrationStore struct {
	records map[string]*models.CalibrationRecord
	err     error
}

func newFakeCalibrationStore() *fakeCalibrationStore {
	return &fakeCalibrationStore{records: map[string]*models.CalibrationRecord{}}
}

func (f *fakeCalibrationStore) CreateRecord(_ context.Context, record *models.CalibrationRecord, measurements []models.Measurement) error {
	if f.err != nil {
		return f.err
	}
	record.Measurements = measurements
	f.records[record.ID] = record
	return nil
}

func (f *fakeCalibrationStore) GetRecord(_ context.Context, id, tenantID string) (*models.CalibrationRecord, error) {
	if f.err != nil {
		return nil, f.err
	}
	r, ok := f.records[id]
	if !ok || r.TenantID != tenantID {
		return nil, errors.New("not found")
	}
	return r, nil
}

func (f *fakeCalibrationStore) ListRecordsByDevice(_ context.Context, deviceID, tenantID string, limit, offset int) ([]*models.CalibrationRecord, int, error) {
	if f.err != nil {
		return nil, 0, f.err
	}
	var out []*models.CalibrationRecord
	for _, r := range f.records {
		if r.DeviceID == deviceID && r.TenantID == tenantID {
			out = append(out, r)
		}
	}
	return out, len(out), nil
}

func (f *fakeCalibrationStore) ListRecords(_ context.Context, tenantID string, limit, offset int) ([]*models.CalibrationRecord, int, error) {
	if f.err != nil {
		return nil, 0, f.err
	}
	var out []*models.CalibrationRecord
	for _, r := range f.records {
		if r.TenantID == tenantID {
			out = append(out, r)
		}
	}
	return out, len(out), nil
}

func (f *fakeCalibrationStore) GetAnalyticsSummary(_ context.Context, tenantID string) (*models.AnalyticsSummary, error) {
	if f.err != nil {
		return nil, f.err
	}
	var total, passes int
	for _, r := range f.records {
		if r.TenantID == tenantID {
			total++
			if r.OverallPass {
				passes++
			}
		}
	}
	rate := 0.0
	if total > 0 {
		rate = float64(passes) / float64(total) * 100
	}
	return &models.AnalyticsSummary{
		TotalDevices: 0,
		TotalRecords: total,
		PassRate:     rate,
		RecentFails:  total - passes,
	}, nil
}

func (f *fakeCalibrationStore) GetDeviceTrend(_ context.Context, deviceID, tenantID string, limit int) ([]*models.CalibrationRecord, error) {
	if f.err != nil {
		return nil, f.err
	}
	var out []*models.CalibrationRecord
	for _, r := range f.records {
		if r.DeviceID == deviceID && r.TenantID == tenantID {
			out = append(out, r)
		}
	}
	if len(out) > limit {
		out = out[:limit]
	}
	return out, nil
}

// ── Test helpers ──────────────────────────────────────────────────────────────

func newTestRouter(ds *fakeDeviceStore, cs *fakeCalibrationStore) *gin.Engine {
	log := zap.NewNop()
	eng := calibration.New()
	h := api.NewHandler(ds, cs, eng, log)
	r := gin.New()
	h.RegisterRoutes(r)
	return r
}

func doRequest(r *gin.Engine, method, path string, body interface{}, headers map[string]string) *httptest.ResponseRecorder {
	var buf bytes.Buffer
	if body != nil {
		_ = json.NewEncoder(&buf).Encode(body)
	}
	req := httptest.NewRequest(method, path, &buf)
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func adminHeaders() map[string]string {
	return map[string]string{"X-Tenant-ID": "tenant-acme", "X-User-Role": "admin"}
}

func viewerHeaders() map[string]string {
	return map[string]string{"X-Tenant-ID": "tenant-acme", "X-User-Role": "viewer"}
}

// ── Healthz ───────────────────────────────────────────────────────────────────

func TestHealthz(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/healthz", nil, nil)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]interface{}
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatal(err)
	}
	if resp["status"] != "ok" {
		t.Errorf("status = %v, want ok", resp["status"])
	}
}

// ── Tenant middleware ──────────────────────────────────────────────────────────

func TestMissingTenantHeader_Returns400(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/api/v1/devices", nil, map[string]string{})
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

// ── Devices ───────────────────────────────────────────────────────────────────

func TestListDevices_Empty(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/api/v1/devices", nil, adminHeaders())
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]interface{}
	_ = json.NewDecoder(w.Body).Decode(&resp)
	devs := resp["devices"].([]interface{})
	if len(devs) != 0 {
		t.Errorf("expected empty device list, got %d", len(devs))
	}
}

func TestCreateDevice_Success(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	body := map[string]interface{}{
		"name":          "Pressure Gauge A",
		"serial_number": "PG-001",
		"device_type":   "pressure",
		"location":      "Lab 1",
		"manufacturer":  "Beamex",
		"model":         "MC6-T",
		"tolerance_pct": 0.5,
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices", body, adminHeaders())
	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var device models.Device
	if err := json.NewDecoder(w.Body).Decode(&device); err != nil {
		t.Fatal(err)
	}
	if device.Name != "Pressure Gauge A" {
		t.Errorf("name = %q, want %q", device.Name, "Pressure Gauge A")
	}
	if device.SerialNumber != "PG-001" {
		t.Errorf("serial_number = %q, want %q", device.SerialNumber, "PG-001")
	}
	if device.TenantID != "tenant-acme" {
		t.Errorf("tenant_id = %q, want %q", device.TenantID, "tenant-acme")
	}
	if !device.IsActive {
		t.Error("expected device to be active")
	}
}

func TestCreateDevice_InvalidDeviceType(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	body := map[string]interface{}{
		"name":          "Bad Sensor",
		"serial_number": "BS-001",
		"device_type":   "invalid_type",
		"location":      "Lab",
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices", body, adminHeaders())
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCreateDevice_MissingRequiredFields(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	body := map[string]interface{}{
		"name": "No Serial",
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices", body, adminHeaders())
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCreateDevice_ViewerForbidden(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	body := map[string]interface{}{
		"name":          "Sensor",
		"serial_number": "S-001",
		"device_type":   "temperature",
		"location":      "Lab",
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices", body, viewerHeaders())
	if w.Code != http.StatusForbidden {
		t.Fatalf("expected 403, got %d", w.Code)
	}
}

func TestGetDevice_NotFound(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/api/v1/devices/nonexistent", nil, adminHeaders())
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestGetDevice_TenantIsolation(t *testing.T) {
	ds := newFakeDeviceStore()
	cs := newFakeCalibrationStore()
	// Seed a device for tenant-acme
	ds.devices["dev-001"] = &models.Device{
		ID:           "dev-001",
		TenantID:     "tenant-acme",
		Name:         "Gauge",
		SerialNumber: "G-001",
		DeviceType:   "pressure",
		Location:     "Lab",
		TolerancePct: 0.5,
		IsActive:     true,
		CreatedAt:    time.Now(),
	}
	r := newTestRouter(ds, cs)

	// Different tenant should not see it
	w := doRequest(r, http.MethodGet, "/api/v1/devices/dev-001", nil, map[string]string{
		"X-Tenant-ID": "tenant-other",
		"X-User-Role": "admin",
	})
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for different tenant, got %d", w.Code)
	}

	// Correct tenant can see it
	w = doRequest(r, http.MethodGet, "/api/v1/devices/dev-001", nil, adminHeaders())
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 for owner tenant, got %d", w.Code)
	}
}

// ── Calibrations ──────────────────────────────────────────────────────────────

func TestCreateCalibration_AllPass(t *testing.T) {
	ds := newFakeDeviceStore()
	cs := newFakeCalibrationStore()
	ds.devices["dev-001"] = &models.Device{
		ID: "dev-001", TenantID: "tenant-acme", Name: "Pressure Gauge",
		SerialNumber: "PG-001", DeviceType: "pressure", Location: "Lab",
		TolerancePct: 0.5, IsActive: true, CreatedAt: time.Now(),
	}

	r := newTestRouter(ds, cs)
	body := map[string]interface{}{
		"operator_name": "Ali Pourrahim",
		"temperature_c": 23.5,
		"measurements": []map[string]interface{}{
			{"measured_value": 100.1, "reference_value": 100.0, "unit": "Pa", "uncertainty": 0.05},
			{"measured_value": 200.2, "reference_value": 200.0, "unit": "Pa", "uncertainty": 0.05},
		},
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices/dev-001/calibrations", body, adminHeaders())
	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var record models.CalibrationRecord
	if err := json.NewDecoder(w.Body).Decode(&record); err != nil {
		t.Fatal(err)
	}
	if record.Status != "pass" {
		t.Errorf("status = %q, want %q", record.Status, "pass")
	}
	if !record.OverallPass {
		t.Error("expected OverallPass = true")
	}
	if record.PassCount != 2 {
		t.Errorf("pass_count = %d, want 2", record.PassCount)
	}
	if record.FailCount != 0 {
		t.Errorf("fail_count = %d, want 0", record.FailCount)
	}
	if len(record.Measurements) != 2 {
		t.Errorf("expected 2 measurements, got %d", len(record.Measurements))
	}
	if record.OperatorName != "Ali Pourrahim" {
		t.Errorf("operator_name = %q, want %q", record.OperatorName, "Ali Pourrahim")
	}
}

func TestCreateCalibration_HasFails(t *testing.T) {
	ds := newFakeDeviceStore()
	cs := newFakeCalibrationStore()
	ds.devices["dev-001"] = &models.Device{
		ID: "dev-001", TenantID: "tenant-acme", Name: "Thermometer",
		SerialNumber: "TH-001", DeviceType: "temperature", Location: "Lab",
		TolerancePct: 0.5, IsActive: true, CreatedAt: time.Now(),
	}

	r := newTestRouter(ds, cs)
	body := map[string]interface{}{
		"operator_name": "Technician",
		"measurements": []map[string]interface{}{
			{"measured_value": 100.1, "reference_value": 100.0, "unit": "°C", "uncertainty": 0.05},  // pass
			{"measured_value": 103.0, "reference_value": 100.0, "unit": "°C", "uncertainty": 0.05},  // fail: 3%
		},
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices/dev-001/calibrations", body, adminHeaders())
	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var record models.CalibrationRecord
	_ = json.NewDecoder(w.Body).Decode(&record)

	if record.Status != "fail" {
		t.Errorf("status = %q, want %q", record.Status, "fail")
	}
	if record.OverallPass {
		t.Error("expected OverallPass = false")
	}
	if record.PassCount != 1 || record.FailCount != 1 {
		t.Errorf("expected 1/1 pass/fail, got %d/%d", record.PassCount, record.FailCount)
	}
}

func TestCreateCalibration_DeviceNotFound(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	body := map[string]interface{}{
		"operator_name": "Technician",
		"measurements": []map[string]interface{}{
			{"measured_value": 100.0, "reference_value": 100.0, "unit": "Pa"},
		},
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices/nonexistent/calibrations", body, adminHeaders())
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestCreateCalibration_NoMeasurements(t *testing.T) {
	ds := newFakeDeviceStore()
	ds.devices["dev-001"] = &models.Device{
		ID: "dev-001", TenantID: "tenant-acme", DeviceType: "pressure",
		TolerancePct: 0.5, IsActive: true, CreatedAt: time.Now(),
	}
	r := newTestRouter(ds, newFakeCalibrationStore())
	body := map[string]interface{}{
		"operator_name": "Technician",
		"measurements":  []interface{}{},
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices/dev-001/calibrations", body, adminHeaders())
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for empty measurements, got %d", w.Code)
	}
}

func TestListCalibrations(t *testing.T) {
	ds := newFakeDeviceStore()
	cs := newFakeCalibrationStore()
	cs.records["cal-001"] = &models.CalibrationRecord{
		ID: "cal-001", DeviceID: "dev-001", TenantID: "tenant-acme",
		Status: "pass", OverallPass: true, MeasuredAt: time.Now(), CreatedAt: time.Now(),
	}
	cs.records["cal-002"] = &models.CalibrationRecord{
		ID: "cal-002", DeviceID: "dev-001", TenantID: "tenant-other", // different tenant
		Status: "pass", OverallPass: true, MeasuredAt: time.Now(), CreatedAt: time.Now(),
	}

	r := newTestRouter(ds, cs)
	w := doRequest(r, http.MethodGet, "/api/v1/calibrations", nil, adminHeaders())
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp map[string]interface{}
	_ = json.NewDecoder(w.Body).Decode(&resp)
	records := resp["records"].([]interface{})
	// Should only see tenant-acme's record
	if len(records) != 1 {
		t.Errorf("expected 1 record (tenant-scoped), got %d", len(records))
	}
}

func TestGetCalibration_NotFound(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/api/v1/calibrations/nonexistent", nil, adminHeaders())
	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

// ── Analytics ─────────────────────────────────────────────────────────────────

func TestGetAnalyticsSummary_EmptyTenant(t *testing.T) {
	r := newTestRouter(newFakeDeviceStore(), newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/api/v1/analytics/summary", nil, adminHeaders())
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var summary models.AnalyticsSummary
	if err := json.NewDecoder(w.Body).Decode(&summary); err != nil {
		t.Fatal(err)
	}
	if summary.TotalRecords != 0 {
		t.Errorf("expected 0 records, got %d", summary.TotalRecords)
	}
}

func TestGetAnalyticsSummary_PassRate(t *testing.T) {
	ds := newFakeDeviceStore()
	cs := newFakeCalibrationStore()
	cs.records["c1"] = &models.CalibrationRecord{ID: "c1", TenantID: "tenant-acme", OverallPass: true}
	cs.records["c2"] = &models.CalibrationRecord{ID: "c2", TenantID: "tenant-acme", OverallPass: true}
	cs.records["c3"] = &models.CalibrationRecord{ID: "c3", TenantID: "tenant-acme", OverallPass: false}

	r := newTestRouter(ds, cs)
	w := doRequest(r, http.MethodGet, "/api/v1/analytics/summary", nil, adminHeaders())
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var summary models.AnalyticsSummary
	_ = json.NewDecoder(w.Body).Decode(&summary)

	if summary.TotalRecords != 3 {
		t.Errorf("total_records = %d, want 3", summary.TotalRecords)
	}
	// 2/3 pass rate = 66.67%
	if summary.PassRate < 66.0 || summary.PassRate > 67.0 {
		t.Errorf("pass_rate = %.2f, want ~66.67", summary.PassRate)
	}
	if summary.RecentFails != 1 {
		t.Errorf("recent_fails = %d, want 1", summary.RecentFails)
	}
}

// ── Store error propagation ───────────────────────────────────────────────────

func TestListDevices_StoreError(t *testing.T) {
	ds := newFakeDeviceStore()
	ds.err = errors.New("db connection lost")
	r := newTestRouter(ds, newFakeCalibrationStore())
	w := doRequest(r, http.MethodGet, "/api/v1/devices", nil, adminHeaders())
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", w.Code)
	}
}

func TestCreateCalibration_StoreError(t *testing.T) {
	ds := newFakeDeviceStore()
	ds.devices["dev-001"] = &models.Device{
		ID: "dev-001", TenantID: "tenant-acme", TolerancePct: 0.5, IsActive: true, CreatedAt: time.Now(),
	}
	cs := newFakeCalibrationStore()
	cs.err = errors.New("db timeout")
	r := newTestRouter(ds, cs)

	body := map[string]interface{}{
		"operator_name": "Technician",
		"measurements": []map[string]interface{}{
			{"measured_value": 100.0, "reference_value": 100.0, "unit": "Pa"},
		},
	}
	w := doRequest(r, http.MethodPost, "/api/v1/devices/dev-001/calibrations", body, adminHeaders())
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", w.Code)
	}
}

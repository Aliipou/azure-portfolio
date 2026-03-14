package calibration_test

import (
	"math"
	"testing"

	"github.com/aliipou/cloud-calibration/internal/calibration"
	"github.com/aliipou/cloud-calibration/internal/models"
)

func TestEvaluate(t *testing.T) {
	e := calibration.New()

	tests := []struct {
		name                string
		measured            float64
		reference           float64
		uncertainty         float64
		tolerancePct        float64
		wantDeviationPct    float64
		wantIsPass          bool
		wantExpandedUnc     float64
	}{
		{
			name:             "perfect_measurement_zero_deviation",
			measured:         100.0,
			reference:        100.0,
			uncertainty:      0.05,
			tolerancePct:     0.5,
			wantDeviationPct: 0.0,
			wantIsPass:       true,
			wantExpandedUnc:  0.1,
		},
		{
			name:             "positive_deviation_within_tolerance",
			measured:         100.4,
			reference:        100.0,
			uncertainty:      0.1,
			tolerancePct:     0.5,
			wantDeviationPct: 0.4,
			wantIsPass:       true,
			wantExpandedUnc:  0.2,
		},
		{
			name:             "negative_deviation_within_tolerance",
			measured:         99.7,
			reference:        100.0,
			uncertainty:      0.05,
			tolerancePct:     0.5,
			wantDeviationPct: -0.3,
			wantIsPass:       true,
			wantExpandedUnc:  0.1,
		},
		{
			name:             "positive_deviation_exceeds_tolerance",
			measured:         101.0,
			reference:        100.0,
			uncertainty:      0.1,
			tolerancePct:     0.5,
			wantDeviationPct: 1.0,
			wantIsPass:       false,
			wantExpandedUnc:  0.2,
		},
		{
			name:             "negative_deviation_exceeds_tolerance",
			measured:         98.5,
			reference:        100.0,
			uncertainty:      0.1,
			tolerancePct:     0.5,
			wantDeviationPct: -1.5,
			wantIsPass:       false,
			wantExpandedUnc:  0.2,
		},
		{
			name:             "deviation_exactly_at_tolerance_boundary",
			measured:         100.5,
			reference:        100.0,
			uncertainty:      0.0,
			tolerancePct:     0.5,
			wantDeviationPct: 0.5,
			wantIsPass:       true, // |0.5| <= 0.5
			wantExpandedUnc:  0.0,
		},
		{
			name:             "zero_reference_returns_false",
			measured:         10.0,
			reference:        0.0,
			uncertainty:      0.05,
			tolerancePct:     0.5,
			wantDeviationPct: 0.0,
			wantIsPass:       false,
			wantExpandedUnc:  0.1,
		},
		{
			name:             "expanded_uncertainty_k2",
			measured:         50.0,
			reference:        50.0,
			uncertainty:      0.25,
			tolerancePct:     1.0,
			wantDeviationPct: 0.0,
			wantIsPass:       true,
			wantExpandedUnc:  0.5, // 2 * 0.25
		},
		{
			name:             "tight_tolerance_fail",
			measured:         100.1,
			reference:        100.0,
			uncertainty:      0.02,
			tolerancePct:     0.05,
			wantDeviationPct: 0.1,
			wantIsPass:       false,
			wantExpandedUnc:  0.04,
		},
		{
			name:             "pressure_sensor_typical",
			measured:         1.503,
			reference:        1.500,
			uncertainty:      0.005,
			tolerancePct:     0.5,
			wantDeviationPct: 0.2,
			wantIsPass:       true,
			wantExpandedUnc:  0.01,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotDev, gotPass, gotExpUnc := e.Evaluate(tt.measured, tt.reference, tt.uncertainty, tt.tolerancePct)

			if math.Abs(gotDev-tt.wantDeviationPct) > 1e-9 {
				t.Errorf("deviationPct = %.10f, want %.10f", gotDev, tt.wantDeviationPct)
			}
			if gotPass != tt.wantIsPass {
				t.Errorf("isPass = %v, want %v (deviation=%.4f%%, tolerance=%.4f%%)", gotPass, tt.wantIsPass, gotDev, tt.tolerancePct)
			}
			if math.Abs(gotExpUnc-tt.wantExpandedUnc) > 1e-9 {
				t.Errorf("expandedUncertainty = %.10f, want %.10f", gotExpUnc, tt.wantExpandedUnc)
			}
		})
	}
}

func TestEvaluateRecord_AllPass(t *testing.T) {
	e := calibration.New()
	inputs := []models.MeasurementInput{
		{MeasuredValue: 100.1, ReferenceValue: 100.0, Unit: "Pa", Uncertainty: 0.05},
		{MeasuredValue: 200.2, ReferenceValue: 200.0, Unit: "Pa", Uncertainty: 0.05},
		{MeasuredValue: 300.1, ReferenceValue: 300.0, Unit: "Pa", Uncertainty: 0.05},
	}

	measurements, passCount, failCount := e.EvaluateRecord("record-001", inputs, 0.5)

	if len(measurements) != 3 {
		t.Fatalf("expected 3 measurements, got %d", len(measurements))
	}
	if passCount != 3 {
		t.Errorf("passCount = %d, want 3", passCount)
	}
	if failCount != 0 {
		t.Errorf("failCount = %d, want 0", failCount)
	}
	for i, m := range measurements {
		if m.RecordID != "record-001" {
			t.Errorf("measurement[%d].RecordID = %q, want %q", i, m.RecordID, "record-001")
		}
		if m.ID == "" {
			t.Errorf("measurement[%d].ID is empty", i)
		}
		if !m.IsPass {
			t.Errorf("measurement[%d] expected pass, got fail (dev=%.4f%%)", i, m.DeviationPct)
		}
		if m.ExpandedUncertainty != 2*inputs[i].Uncertainty {
			t.Errorf("measurement[%d].ExpandedUncertainty = %.4f, want %.4f", i, m.ExpandedUncertainty, 2*inputs[i].Uncertainty)
		}
	}
}

func TestEvaluateRecord_MixedPassFail(t *testing.T) {
	e := calibration.New()
	inputs := []models.MeasurementInput{
		{MeasuredValue: 100.1, ReferenceValue: 100.0, Unit: "°C", Uncertainty: 0.05}, // pass: 0.1%
		{MeasuredValue: 102.0, ReferenceValue: 100.0, Unit: "°C", Uncertainty: 0.05}, // fail: 2.0%
		{MeasuredValue: 99.8, ReferenceValue: 100.0, Unit: "°C", Uncertainty: 0.05},  // pass: -0.2%
	}

	measurements, passCount, failCount := e.EvaluateRecord("record-002", inputs, 0.5)

	if len(measurements) != 3 {
		t.Fatalf("expected 3 measurements, got %d", len(measurements))
	}
	if passCount != 2 {
		t.Errorf("passCount = %d, want 2", passCount)
	}
	if failCount != 1 {
		t.Errorf("failCount = %d, want 1", failCount)
	}
	if measurements[0].IsPass != true {
		t.Error("measurement[0] should pass")
	}
	if measurements[1].IsPass != false {
		t.Error("measurement[1] should fail")
	}
	if measurements[2].IsPass != true {
		t.Error("measurement[2] should pass")
	}
}

func TestEvaluateRecord_AllFail(t *testing.T) {
	e := calibration.New()
	inputs := []models.MeasurementInput{
		{MeasuredValue: 103.0, ReferenceValue: 100.0, Unit: "V", Uncertainty: 0.1}, // 3% deviation
		{MeasuredValue: 97.0, ReferenceValue: 100.0, Unit: "V", Uncertainty: 0.1},  // -3% deviation
	}

	_, passCount, failCount := e.EvaluateRecord("record-003", inputs, 0.5)

	if passCount != 0 {
		t.Errorf("passCount = %d, want 0", passCount)
	}
	if failCount != 2 {
		t.Errorf("failCount = %d, want 2", failCount)
	}
}

func TestEvaluateRecord_UniqueIDs(t *testing.T) {
	e := calibration.New()
	inputs := []models.MeasurementInput{
		{MeasuredValue: 10.0, ReferenceValue: 10.0, Unit: "bar", Uncertainty: 0.01},
		{MeasuredValue: 10.0, ReferenceValue: 10.0, Unit: "bar", Uncertainty: 0.01},
		{MeasuredValue: 10.0, ReferenceValue: 10.0, Unit: "bar", Uncertainty: 0.01},
	}

	measurements, _, _ := e.EvaluateRecord("record-004", inputs, 0.5)

	seen := map[string]bool{}
	for _, m := range measurements {
		if seen[m.ID] {
			t.Errorf("duplicate measurement ID: %s", m.ID)
		}
		seen[m.ID] = true
	}
}

func TestEvaluateRecord_EmptyInputs(t *testing.T) {
	e := calibration.New()
	measurements, passCount, failCount := e.EvaluateRecord("record-005", nil, 0.5)

	if len(measurements) != 0 {
		t.Errorf("expected 0 measurements, got %d", len(measurements))
	}
	if passCount != 0 || failCount != 0 {
		t.Errorf("expected 0/0 pass/fail, got %d/%d", passCount, failCount)
	}
}

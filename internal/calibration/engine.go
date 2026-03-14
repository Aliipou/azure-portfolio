package calibration

import (
	"math"

	"github.com/aliipou/cloud-calibration/internal/models"
	"github.com/google/uuid"
)

// Engine executes calibration evaluation logic.
type Engine struct{}

// New returns a new Engine instance.
func New() *Engine { return &Engine{} }

// Evaluate computes deviation and pass/fail for one measurement point.
// expandedUncertainty is calculated using coverage factor k=2 (95% confidence interval).
func (e *Engine) Evaluate(measured, reference, uncertainty, tolerancePct float64) (deviationPct float64, isPass bool, expandedUncertainty float64) {
	expandedUncertainty = 2 * uncertainty // k=2, 95% confidence
	if reference == 0 {
		return 0, false, expandedUncertainty
	}
	deviationPct = (measured - reference) / reference * 100
	isPass = math.Abs(deviationPct) <= tolerancePct
	return
}

// EvaluateRecord evaluates all measurement inputs against the device tolerance,
// returning fully populated Measurement slices and aggregate pass/fail counts.
func (e *Engine) EvaluateRecord(recordID string, inputs []models.MeasurementInput, tolerancePct float64) (measurements []models.Measurement, passCount, failCount int) {
	measurements = make([]models.Measurement, 0, len(inputs))
	for _, inp := range inputs {
		dev, pass, expUnc := e.Evaluate(inp.MeasuredValue, inp.ReferenceValue, inp.Uncertainty, tolerancePct)
		m := models.Measurement{
			ID:                  uuid.New().String(),
			RecordID:            recordID,
			MeasuredValue:       inp.MeasuredValue,
			ReferenceValue:      inp.ReferenceValue,
			Unit:                inp.Unit,
			Uncertainty:         inp.Uncertainty,
			DeviationPct:        dev,
			IsPass:              pass,
			ExpandedUncertainty: expUnc,
		}
		measurements = append(measurements, m)
		if pass {
			passCount++
		} else {
			failCount++
		}
	}
	return
}

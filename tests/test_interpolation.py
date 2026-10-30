from math import exp, log
import unittest

from flightlab.dataset import AeroReference, AnalysisCondition, PolarDataset, PolarRun
from flightlab.flow5 import Flow5Polar
from flightlab.interpolation import ModelDomainError, PolarFamily
from flightlab.mission import FlightConditions


def affine_values(cl, reynolds, mach):
    return (0.01 + 0.02*cl + 0.001*log(reynolds) + 0.01*mach,
            -0.02*cl + 0.003*mach, 10*cl - 1 + 0.1*log(reynolds))


def synthetic_dataset():
    reference = AeroReference(1, 0.4)
    conditions, runs = {}, []
    for h in (0, 5000):
        air = FlightConditions(h).atmosphere()
        for speed in (100, 250):
            name = f"synthetic_{h}_{speed}"
            condition = AnalysisCondition(name, h, speed, air.temperature_k-273.15,
                                           air.density_kg_m3, air.kinematic_viscosity_m2_s)
            rows = []
            for cl in (0.1, 0.4, 0.7):
                re = speed*reference.chord_m/condition.nu_m2_s
                cd, cm, alpha = affine_values(cl, re, condition.mach)
                rows.append({"Ctrl": 0, "CL": cl, "CD": cd, "Cm": cm, "α (°)": alpha, "V (m/s)": speed})
            conditions[name] = condition
            runs.append(PolarRun(name+".csv", condition, Flow5Polar(("synthetic", name), tuple(rows[0]), rows)))
    return PolarDataset(conditions, runs, {}, []), reference


class InterpolationTests(unittest.TestCase):
    def setUp(self):
        self.dataset, self.reference = synthetic_dataset()

    def test_all_source_points_and_affine_interior_reconstructed(self):
        family = PolarFamily(self.dataset, self.reference)
        self.assertEqual(family.sample_count, 12)
        for run in self.dataset.runs:
            c = run.condition
            re = c.speed_m_s*self.reference.chord_m/c.nu_m2_s
            for p in run.polar.points:
                result = family.evaluate(p["CL"], re, c.mach)
                self.assertAlmostEqual(result.cd, p["CD"])
                self.assertAlmostEqual(result.cm, p["Cm"])
                self.assertAlmostEqual(result.alpha_deg, p["α (°)"])
        log_re = sum(log(r.condition.speed_m_s*self.reference.chord_m/r.condition.nu_m2_s)
                     for r in self.dataset.runs)/4
        mach = sum(r.condition.mach for r in self.dataset.runs)/4
        result = family.evaluate(0.4, exp(log_re), mach)
        expected = affine_values(0.4, exp(log_re), mach)
        self.assertAlmostEqual(result.cd, expected[0], places=12)
        self.assertAlmostEqual(result.cm, expected[1], places=12)
        self.assertAlmostEqual(result.alpha_deg, expected[2], places=12)
        self.assertAlmostEqual(sum(c.weight for c in result.contributors), 1)
        self.assertTrue(all(c.weight > 0 for c in result.contributors))

    def test_no_silent_extrapolation_and_explicit_fallback_is_marked(self):
        family = PolarFamily(self.dataset, self.reference)
        with self.assertRaises(ModelDomainError):
            family.evaluate(1.2, 1e9, 2)
        result = family.evaluate(1.2, 1e9, 2, extrapolation="nearest")
        self.assertTrue(any("extrapolation" in w for w in result.warnings))

    def test_high_mach_retained_and_source_warnings_propagated(self):
        family = PolarFamily(self.dataset, self.reference, drag_factor=3)
        run = self.dataset.runs[-1]
        re = run.condition.speed_m_s*self.reference.chord_m/run.condition.nu_m2_s
        point = family.evaluate(0.4, re, run.condition.mach)
        self.assertAlmostEqual(point.cd, affine_values(0.4, re, run.condition.mach)[0]*3)
        self.assertTrue(any("source" in w for w in point.warnings))
        self.assertTrue(any("Flight Mach" in w for w in point.warnings))
        self.assertEqual(family.sample_count, 12)

    def test_conflicting_stall_branches_rejected_without_averaging(self):
        row = dict(self.dataset.runs[0].polar.points[0])
        row["CD"] *= 2
        self.dataset.runs[0].polar.points.append(row)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            PolarFamily(self.dataset, self.reference)

    def test_incomplete_family_is_usable_but_flagged(self):
        self.dataset.runs.pop()
        family = PolarFamily(self.dataset, self.reference)
        run = self.dataset.runs[0]
        re = run.condition.speed_m_s*self.reference.chord_m/run.condition.nu_m2_s
        result = family.evaluate(0.4, re, run.condition.mach)
        self.assertTrue(any("Incomplete" in w for w in result.warnings))

    def test_single_condition_is_not_claimed_to_be_a_3d_family(self):
        self.dataset.runs = self.dataset.runs[:1]
        with self.assertRaisesRegex(ValueError, "two altitudes"):
            PolarFamily(self.dataset, self.reference)

    def test_aircraft_and_reference_mismatch_are_rejected(self):
        run = self.dataset.runs[0]
        run.polar.points[0]["Lift (N)"] = 999999
        with self.assertRaisesRegex(ValueError, "reference area"):
            PolarFamily(self.dataset, self.reference)
        del run.polar.points[0]["Lift (N)"]
        run.polar.metadata_lines = ("Another aircraft", run.condition.name)
        with self.assertRaisesRegex(ValueError, "different aircraft"):
            PolarFamily(self.dataset, self.reference)

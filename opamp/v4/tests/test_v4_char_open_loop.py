from opamp.v4.measure import run_open_loop_test
from opamp.v4.tests._helpers import BaseV4SimTest


class TestV4CharOpenLoop(BaseV4SimTest):
    def test_nominal_open_loop_characterization_runs(self) -> None:
        result = run_open_loop_test()
        metrics = result["metrics"]

        self.assertFinite(float(metrics["aol_db"]))
        self.assertFinite(float(metrics["iq_uA"]))
        self.assertFinite(float(metrics["vout_dc"]))
        self.assertGreater(float(metrics["iq_uA"]), 0.0)
        self.assertGreater(float(metrics["vout_dc"]), 0.0)
        self.assertLess(float(metrics["vout_dc"]), 1.8)

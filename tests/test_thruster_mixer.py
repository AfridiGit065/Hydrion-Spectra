"""Unit tests for the 5-thruster mixer and ThrusterManager (Phase 1).

Run from the project root:

    python -m unittest tests.test_thruster_mixer -v
    # or, if pytest is available:
    python -m pytest tests/test_thruster_mixer.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.controller.controller import MotionState
from modules.thrusters.thruster_manager import (
    ThrusterId,
    ThrusterManager,
    mix,
)

M1 = ThrusterId.M1_FRONT_VERTICAL
M2 = ThrusterId.M2_MIDDLE_RIGHT_HORIZONTAL
M3 = ThrusterId.M3_MIDDLE_LEFT_HORIZONTAL
M4 = ThrusterId.M4_BACK_RIGHT_VERTICAL
M5 = ThrusterId.M5_BACK_LEFT_VERTICAL

_ALL_IDS = (M1, M2, M3, M4, M5)
_ZERO = {t: 0.0 for t in _ALL_IDS}


class FiveThrusterMixerTest(unittest.TestCase):
    def assertMix(self, expected, **kwargs):
        result = mix(**kwargs)
        self.assertEqual(result, expected)

    def test_neutral(self):
        self.assertMix(_ZERO)
        self.assertMix(_ZERO, surge=0.0, yaw=0.0, heave=0.0)

    def test_stop_is_five_zeros(self):
        result = mix(MotionState(surge=1.0, yaw=1.0, heave=1.0))
        self.assertNotEqual(result, _ZERO)
        self.assertMix(_ZERO, surge=0.0, yaw=0.0, heave=0.0)

    def test_forward(self):
        self.assertMix({M1: 0.0, M2: 1.0, M3: 1.0, M4: 0.0, M5: 0.0}, surge=1)

    def test_forward_from_motion(self):
        result = mix(MotionState(surge=1.0))
        self.assertEqual(result, {M1: 0.0, M2: 1.0, M3: 1.0, M4: 0.0, M5: 0.0})

    def test_backward(self):
        self.assertMix({M1: 0.0, M2: -1.0, M3: -1.0, M4: 0.0, M5: 0.0}, surge=-1)

    def test_yaw_left(self):
        self.assertMix({M1: 0.0, M2: -1.0, M3: 1.0, M4: 0.0, M5: 0.0}, yaw=-1)

    def test_yaw_right(self):
        self.assertMix({M1: 0.0, M2: 1.0, M3: -1.0, M4: 0.0, M5: 0.0}, yaw=1)

    def test_up(self):
        self.assertMix({M1: 1.0, M2: 0.0, M3: 0.0, M4: 1.0, M5: 1.0}, heave=1)

    def test_down(self):
        self.assertMix({M1: -1.0, M2: 0.0, M3: 0.0, M4: -1.0, M5: -1.0}, heave=-1)

    def test_forward_yaw(self):
        self.assertMix({M1: 0.0, M2: 1.0, M3: 0.0, M4: 0.0, M5: 0.0}, surge=1, yaw=1)

    def test_forward_up(self):
        self.assertMix({M1: 1.0, M2: 1.0, M3: 1.0, M4: 1.0, M5: 1.0}, surge=1, heave=1)

    def test_yaw_up(self):
        self.assertMix({M1: 1.0, M2: 1.0, M3: -1.0, M4: 1.0, M5: 1.0}, yaw=1, heave=1)

    def test_forward_yaw_up(self):
        self.assertMix({M1: 1.0, M2: 1.0, M3: 0.0, M4: 1.0, M5: 1.0}, surge=1, yaw=1, heave=1)

    def test_saturation_clamping(self):
        for kwargs in (
            dict(surge=1.0, yaw=1.0),
            dict(surge=0.7, yaw=0.7),
            dict(surge=1.0, yaw=1.0, heave=-1.0),
            dict(surge=-1.0, yaw=-1.0, heave=1.0),
        ):
            result = mix(**kwargs)
            self.assertEqual(len(result), 5)
            for thruster in _ALL_IDS:
                self.assertGreaterEqual(result[thruster], -1.0)
                self.assertLessEqual(result[thruster], 1.0)

    def test_unsupported_sway_produces_no_thrust(self):
        self.assertEqual(mix(MotionState(sway=1.0)), _ZERO)

    def test_unsupported_sway_from_motion(self):
        self.assertEqual(mix(MotionState(sway=1.0)), _ZERO)

    def test_unsupported_pitch_produces_no_thrust(self):
        self.assertEqual(mix(MotionState(pitch=1.0)), _ZERO)

    def test_unsupported_roll_produces_no_thrust(self):
        self.assertEqual(mix(MotionState(roll=1.0)), _ZERO)

    def test_always_returns_exactly_five_motor_outputs(self):
        result = mix(MotionState(surge=0.3, yaw=-0.4, heave=0.2))
        self.assertEqual(len(result), 5)
        self.assertEqual(set(result.keys()), set(_ALL_IDS))

    def test_direction_flip(self):
        flip = {M2: -1, M3: -1}
        result = mix(surge=1.0, directions=flip)
        self.assertEqual(result[M2], -1.0)
        self.assertEqual(result[M3], -1.0)
        self.assertEqual(result[M1], 0.0)

    def test_no_directions_is_all_positive(self):
        result = mix(surge=1.0)
        self.assertEqual(result[M2], 1.0)
        self.assertEqual(result[M3], 1.0)


class ThrusterManagerTest(unittest.TestCase):
    def _manager(self):
        config = {
            "provider": "simulated",
            "motors": {
                "M1_FRONT_VERTICAL": {"gpio": 25, "direction": 1},
                "M2_MIDDLE_RIGHT_HORIZONTAL": {"gpio": 33, "direction": 1},
            },
        }
        mgr = ThrusterManager(config, sensors=None)
        self.assertTrue(mgr.initialize())
        mgr.start()
        return mgr

    def test_forward_setpoints(self):
        mgr = self._manager()
        mgr.set_motion(MotionState(surge=1.0))
        mgr.update()
        mgr.update()
        self.assertEqual(mgr.last_setpoints[M2], 1.0)
        self.assertEqual(mgr.last_setpoints[M3], 1.0)
        self.assertEqual(mgr.last_setpoints[M1], 0.0)

    def test_emergency_stop_zeroes_all_motors(self):
        mgr = self._manager()
        mgr.set_motion(MotionState(surge=1.0, heave=1.0))
        mgr.emergency_stop()
        mgr.update()
        mgr.update()
        self.assertEqual(mgr.last_setpoints, _ZERO)

    def test_emergency_stop_cleared(self):
        mgr = self._manager()
        mgr.emergency_stop()
        mgr.clear_emergency_stop()
        mgr.set_motion(MotionState(surge=1.0))
        mgr.update()
        mgr.update()
        self.assertEqual(mgr.last_setpoints[M2], 1.0)

    def test_unknown_provider_falls_back_to_simulated(self):
        mgr = ThrusterManager({"provider": "bogus"}, sensors=None)
        self.assertTrue(mgr.initialize())
        self.assertTrue(mgr.health_check())

    def test_gpio_metadata_loaded(self):
        mgr = self._manager()
        self.assertEqual(mgr.thruster_config.gpio[M1], 25)
        self.assertEqual(mgr.thruster_config.gpio[M2], 33)
        self.assertEqual(mgr.thruster_config.directions[M3], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
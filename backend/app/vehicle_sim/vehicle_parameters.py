"""DKZ33 vehicle parameters used by the local dynamics model.

Mass, car length, wheel radius and the 52-point motor curves come from
``列车仿真参数(1).xlsx``.  The gearbox ratio is not published for DKZ33; 7.8 is
an engineering estimate that maps the 4160.1 rpm curve endpoint to about
92.5 km/h, leaving roughly 15% margin above the 80 km/h operating speed.
"""

TRAIN_MASS_KG = 225_000.0
TRAIN_LENGTH_M = 118.0
WHEEL_RADIUS_M = 0.46
MOTOR_COUNT = 16
GEAR_RATIO = 7.8  # Estimated; replace here when an authoritative value is available.
MAX_CONTROL_LEVEL = 4

# Davis resistance parameters. M is train mass in tonnes, n is axle count,
# N is car count and A is frontal area in square metres.
DAVIS_MASS_T = 225.0
DAVIS_AXLE_COUNT = 24
DAVIS_CAR_COUNT = 6
DAVIS_FRONTAL_AREA_M2 = 10.6

# The workbook stores each curve as [torque_Nm][motor_speed_rpm].
MOTOR_SPEED_RPM_52 = (
    0.0, 83.2, 166.4, 249.6, 332.8, 416.0, 499.2, 582.4, 665.6,
    748.8, 832.0, 915.2, 998.4, 1081.6, 1164.8, 1248.0, 1331.2,
    1414.4, 1497.6, 1580.8, 1664.0, 1747.2, 1830.4, 1913.6,
    1996.9, 2080.1, 2163.3, 2246.5, 2329.7, 2412.9, 2496.1,
    2579.3, 2662.5, 2745.7, 2828.9, 2912.1, 2995.3, 3078.5,
    3161.7, 3244.9, 3328.1, 3411.3, 3494.5, 3577.7, 3660.9,
    3744.1, 3827.3, 3910.5, 3993.7, 4076.9, 4160.1, 4160.1,
)

TRACTION_TORQUE_NM_52 = (
    1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9,
    1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9,
    1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9,
    1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9, 1042.9,
    1042.9, 1042.9, 1036.8, 971.0, 911.2, 856.9, 807.2, 761.7,
    720.0, 681.6, 646.2, 613.5, 583.2, 555.1, 529.0, 504.7,
    482.0, 460.8, 441.0, 422.4, 405.0, 388.6, 373.2, 373.2,
)

BRAKE_TORQUE_NM_52 = (
    0.0, 0.0, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7,
    977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7,
    977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7,
    977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7,
    977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7,
    977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7, 977.7,
    977.7, 977.7, 977.7,
)

assert len(MOTOR_SPEED_RPM_52) == 52
assert len(TRACTION_TORQUE_NM_52) == 52
assert len(BRAKE_TORQUE_NM_52) == 52

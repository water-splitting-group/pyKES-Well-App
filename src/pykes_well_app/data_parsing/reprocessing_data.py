"""Recalculation of dissolved oxygen from the raw phase angle of a PyroScience sensor.

The Workbench writes both the raw phase angle `dphi` and its own oxygen result. This
module recomputes the oxygen concentration from `dphi` and the sensor calibration, so
that a measurement can be reprocessed with a corrected or alternative calibration.

Two stages:

1. `calculate_pO2_from_calibration` turns `dphi` and the compensation temperature into an
   oxygen partial pressure, using the two-site Stern-Volmer model of the sensor. This is
   a Python port of PyroScience's `oxycalc` library (used by pyrotoolbox).
2. `partial_pressure_to_micromolar` converts that partial pressure into a dissolved
   oxygen concentration in µmol/L.

The sensor model is

    tau/tau0 = f/(1 + Ksv*pO2) + (1 - f)/(1 + m*Ksv*pO2)

with the luminescence lifetime `tau` derived from the phase angle, and all four sensor
parameters corrected from their 20 °C reference values to the measurement temperature.
Rearranged, the model is a quadratic in the product `Ksv*pO2`, which is what
`quenching_product` solves for.

Why reprocessing matters here
-----------------------------
The Workbench wrote the oxygen column of this project's FirePlate logfiles with its
temperature compensation stuck at 0 C, even though the channel was configured for optical
temperature compensation. `reproduce_workbench_oxygen` demonstrates this: feeding 0 C into
the model below reproduces the logged column to the six digits the logfile prints, for
every well of AE-852-1.txt and AE-772-1.txt. Recomputing with the measured optical
temperature is therefore the correction, and the reprocessed concentrations are expected
to differ strongly from the logged ones -- roughly a factor of three for wells that run at
25-30 C.
"""

import numpy as np

from pyKES.utilities.unit_handler import Quantity

# The Workbench reports all sensor parameters relative to this reference temperature.
REFERENCE_TEMPERATURE = 20.0  # °C

# Lifetimes are handled in µs, as in the calibration routine of the sensor firmware.
MICROSECONDS_PER_SECOND = 1e6

# Vapour pressure of water, equation (6) of Murray, F.W. (1967),
# "On the computation of saturation vapour pressure", J. Applied Meteorology 6: 203-204.
VAPOUR_PRESSURE_SCALE = 6.1078  # hPa
VAPOUR_PRESSURE_EXPONENT_FACTOR = 17.2694
VAPOUR_PRESSURE_TEMPERATURE_OFFSET = 237.3  # °C

# Oxygen solubility fit of Garcia & Gordon (1992), "Oxygen solubility in seawater:
# better fitting equations", Limnol. Oceanogr. 37: 1307-1312. Polynomial coefficients in
# the scaled temperature, the salinity correction and the quadratic salinity term.
SOLUBILITY_TEMPERATURE_COEFFICIENTS = (2.00856, 3.224, 3.99063, 4.80299, 0.978188, 1.71069)
SOLUBILITY_SALINITY_COEFFICIENTS = (-0.00624097, -0.00693498, -0.00690358, -0.00429155)
SOLUBILITY_SQUARED_SALINITY_COEFFICIENT = -3.1168e-07
SOLUBILITY_SCALED_TEMPERATURE_OFFSET = 298.15  # K, numerator of the scaled temperature
KELVIN_OFFSET = 273.15
MOLAR_VOLUME_OF_OXYGEN = 0.02241  # L/mmol at standard conditions, converts mL/L to µmol/L

# Temperature the Workbench actually used when it wrote the oxygen column of this
# project's logfiles, instead of the optical temperature it was configured to use.
WORKBENCH_COMPENSATION_TEMPERATURE = 0.0  # C

# Reference air used to define 100% air saturation.
STANDARD_PRESSURE = 1013.0  # hPa
OXYGEN_FRACTION_IN_AIR = 0.2095


def vapour_pressure_water(temperature):
    """Saturation vapour pressure of water.

    Parameters
    ----------
    temperature
        Temperature in °C.

    Returns
    -------
    Vapour pressure in hPa.
    """
    return VAPOUR_PRESSURE_SCALE * np.exp(
        VAPOUR_PRESSURE_EXPONENT_FACTOR * temperature / (temperature + VAPOUR_PRESSURE_TEMPERATURE_OFFSET))


def oxygen_solubility(temperature, salinity):
    """Solubility of oxygen in water at air saturation.

    Parameters
    ----------
    temperature
        Water temperature in °C.
    salinity
        Salinity in g/L.

    Returns
    -------
    Solubility in µmol/L.
    """
    scaled_temperature = np.log(
        (SOLUBILITY_SCALED_TEMPERATURE_OFFSET - temperature) / (KELVIN_OFFSET + temperature))

    temperature_terms = sum(coefficient * scaled_temperature ** power
                            for power, coefficient in enumerate(SOLUBILITY_TEMPERATURE_COEFFICIENTS))
    salinity_terms = salinity * sum(coefficient * scaled_temperature ** power
                                    for power, coefficient in enumerate(SOLUBILITY_SALINITY_COEFFICIENTS))

    return np.exp(temperature_terms + salinity_terms
                  + SOLUBILITY_SQUARED_SALINITY_COEFFICIENT * salinity ** 2) / MOLAR_VOLUME_OF_OXYGEN


def partial_pressure_to_micromolar(partial_pressure, temperature, salinity):
    """Convert an oxygen partial pressure into a dissolved oxygen concentration.

    Parameters
    ----------
    partial_pressure
        Oxygen partial pressure in hPa.
    temperature
        Water temperature in °C.
    salinity
        Salinity in g/L.

    Returns
    -------
    Dissolved oxygen in µmol/L.
    """
    air_saturation_pressure = (STANDARD_PRESSURE - vapour_pressure_water(temperature)) * OXYGEN_FRACTION_IN_AIR

    return partial_pressure * oxygen_solubility(temperature, salinity) / air_saturation_pressure

def convert_umol_L_to_mol(data_umol_L: np.ndarray,
                          liquid_phase_volume_ml: float):
    '''
    Convert liquid phase measurement in umol/L to mol.

    Parameters
    ----------
    data_umol_L : np.ndarray
        Liquid phase measurement in umol/L.
    liquid_phase_volume_ml : float
        Liquid phase volume in mL.
    
    Returns
    -------
    amount : Quantity
        Amount of substance (quantity object, substance)
    '''

    data_quantity = Quantity(data_umol_L, 'umol/L')
    liquid_phase_volume_quantity = Quantity(liquid_phase_volume_ml, 'mL')

    amount = Quantity(data_quantity.unit['umol/L']
                      * liquid_phase_volume_quantity.unit['L'],
                      'umol')

    return amount

def calibration_partial_pressure(calibration):
    """Oxygen partial pressure of the upper calibration point.

    The upper calibration point is a gas of known oxygen content at a known pressure and
    humidity, so the water vapour has to be subtracted before scaling by the oxygen
    content.

    Parameters
    ----------
    calibration
        Calibration dictionary; uses `pressure`, `temp100`, `humidity` and `percentO2`.

    Returns
    -------
    Partial pressure of oxygen in hPa.
    """
    water_vapour = vapour_pressure_water(calibration['temp100']) * calibration['humidity'] / 100

    return (calibration['pressure'] - water_vapour) * calibration['percentO2'] / 100


def lifetime_from_phase_angle(dphi, frequency):
    """Luminescence lifetime behind a measured phase angle.

    Parameters
    ----------
    dphi
        Phase angle in degrees.
    frequency
        Modulation frequency in Hz.

    Returns
    -------
    Lifetime in µs.
    """
    return np.tan(np.radians(dphi)) / (2 * np.pi * frequency) * MICROSECONDS_PER_SECOND


def quenching_product(lifetime, unquenched_lifetime, unquenched_fraction, quenching_ratio):
    """Solve the two-site model for the product `Ksv * pO2`.

    Written as a quadratic in that product, the model is

        m*tau*x**2 + (tau*(1 + m) - tau0*(1 - f + f*m))*x + (tau - tau0) = 0,

    of which the positive root is the physical one.

    Parameters
    ----------
    lifetime
        Measured lifetime in µs.
    unquenched_lifetime
        Lifetime at zero oxygen, at the same temperature, in µs.
    unquenched_fraction
        Sensor constant `f`, the fraction of the signal quenched with `Ksv`.
    quenching_ratio
        Sensor constant `m`, the relative quenching constant of the remaining fraction.

    Returns
    -------
    The dimensionless product of Stern-Volmer constant and oxygen partial pressure.
    """
    quadratic = quenching_ratio * lifetime
    linear = (lifetime * (1 + quenching_ratio)
              - unquenched_lifetime * (1 - unquenched_fraction + unquenched_fraction * quenching_ratio))
    constant = lifetime - unquenched_lifetime

    return (-linear + np.sqrt(linear ** 2 - 4 * quadratic * constant)) / (2 * quadratic)


def calibrate_sensor(calibration):
    """Reduce a Workbench calibration to the two sensor parameters at 20 °C.

    The zero point fixes the unquenched lifetime and the upper point then fixes the
    Stern-Volmer constant; both are normalised to the 20 °C reference temperature.

    Parameters
    ----------
    calibration
        Calibration dictionary as parsed from the logfile header.

    Returns
    -------
    tuple
        Unquenched lifetime at 20 °C in µs and Stern-Volmer constant at 20 °C in 1/hPa.

    Notes
    -----
    PyroScience's `oxycalc` scales `f` multiplicatively here but additively when
    evaluating a measurement (see `calculate_pO2_from_calibration`). The asymmetry only
    matters when the sensor constant `ft` is non-zero, and is reproduced deliberately.
    """
    zero_offset = calibration['temp0'] - REFERENCE_TEMPERATURE
    upper_offset = calibration['temp100'] - REFERENCE_TEMPERATURE

    zero_lifetime = lifetime_from_phase_angle(calibration['dphi0'], calibration['freq'])
    unquenched_lifetime_20 = zero_lifetime / (1 + zero_offset * calibration['tt'])

    unquenched_lifetime_upper = unquenched_lifetime_20 * (1 + upper_offset * calibration['tt'])
    upper_lifetime = lifetime_from_phase_angle(calibration['dphi100'], calibration['freq'])

    product = quenching_product(upper_lifetime,
                                unquenched_lifetime_upper,
                                calibration['f'] * (1 + upper_offset * calibration.get('ft', 0.0)),
                                calibration['m'] + upper_offset * calibration['mt'])
    stern_volmer_upper = product / calibration_partial_pressure(calibration)

    return unquenched_lifetime_20, stern_volmer_upper / (1 + upper_offset * calibration['kt'])


def calculate_pO2_from_calibration(dphi, temperature, calibration):
    """Calculate the oxygen partial pressure behind a measured phase angle.

    Parameters
    ----------
    dphi
        Measured phase angle in degrees.
    temperature
        Sensor temperature in °C, from the optical temperature compensation channel.
    calibration
        Calibration dictionary as parsed from the logfile header.

    Returns
    -------
    Oxygen partial pressure in hPa.
    """
    unquenched_lifetime_20, stern_volmer_20 = calibrate_sensor(calibration)
    temperature_offset = temperature - REFERENCE_TEMPERATURE

    unquenched_lifetime = unquenched_lifetime_20 * (1 + temperature_offset * calibration['tt'])
    stern_volmer = stern_volmer_20 * (1 + temperature_offset * calibration['kt'])

    product = quenching_product(lifetime_from_phase_angle(dphi, calibration['freq']),
                                unquenched_lifetime,
                                calibration['f'] + temperature_offset * calibration.get('ft', 0.0),
                                calibration['m'] + temperature_offset * calibration['mt'])

    return product / stern_volmer



def reproduce_workbench_oxygen(raw_data_dict: dict):
    """Recompute the oxygen concentration the way the Workbench itself did.

    Only useful as a check: it confirms that the calibration was read and the sensor model
    implemented correctly, by reproducing the logfile's own oxygen column from `dphi`. Use
    `processing_function` for the corrected, temperature-compensated result.

    Parameters
    ----------
    raw_data_dict
        Raw data as returned by `raw_data_reading_function`.

    Returns
    -------
    Dissolved oxygen in umol/L, matching the logfile's oxygen column.
    """
    calibration = raw_data_dict['calibration']

    partial_pressure = calculate_pO2_from_calibration(raw_data_dict['dphi'],
                                                      WORKBENCH_COMPENSATION_TEMPERATURE,
                                                      calibration)

    return partial_pressure_to_micromolar(partial_pressure,
                                          WORKBENCH_COMPENSATION_TEMPERATURE,
                                          calibration['salinity'])

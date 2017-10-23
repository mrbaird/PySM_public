"""
.. module:: common
   :platform: Unix
   :synopsis: convenience functions used in other modules.

.. moduleauthor: Ben Thorne <ben.thorne@physics.ox.ac.uk>
"""

from __future__ import print_function
import healpy as hp
import numpy as np
import scipy.constants as constants
from scipy.interpolate import CubicSpline
import scipy.integrate
import sys

def FloatOrArray(model):
    """Decorator to modify models to allow computation across an array of
    frequencies, and for a single float.

    Parameters
    ----------
    model: function
        Function we wish to  decorate.

    Returns
    -------
    function
        Wrapped function.

    """
    def decorator(nu, **kwargs):
        """Evaluate if nu is a float."""
        try:
            nu_float = float(nu)
            nu_float = np.array(nu)
            return model(nu_float, **kwargs)
        except TypeError:
            try:
                """If not float, check if nu is one dimensional"""
                nu_1darray = np.asarray(nu)
                if not (nu_1darray.ndim == 1):
                    print("Frequencies must be float or convertable to 1d array.")
                    sys.exit(1)
                    """If it is 1d array evaluate model function over all its elements."""
                return np.array([model(x, **kwargs) for x in nu_1darray])
            except ValueError:
                """Fail if not convertable to 1d array"""
                print("Frequencies must be either float or convertable to array.")
                sys.exit(1)
    return decorator


def interpolation(fpath, nside, pixel_indices=None):
    """Function to interpolate a set of maps in frequency.

    Parameters
    ----------
    fpath: str
        Path to file containing two columns: column 1 must be frequency and
        column 2 are paths to the file containing (T, Q, U) at that frequency.
    nside: int
        Nside at which to do the interpolation. Maps are read in and
        up/de-graded tothis resolution.
    pixel-indices: array_like(int, ndim=1) (optional, default=None)
        If not `None` only these indices are interpolated.

    Returns
    -------
    function(float)
        Function of frequency which itself returns a set of (T, Q, U) maps at
        that frequency.
    """
    (nus, maps) = read_interp_data(fpath, nside, pixel_indices=pixel_indices)
    # Compute interpolation along the 0th axis (frequency axis). Extrapolate
    # extends the returned function beyond the min/max of the nus array.
    spline = CubicSpline(nus, maps, axis=0, extrapolate=True)
    return spline


def read_interp_data(fpath, nside, pixel_indices=None):
    """Function to read info file `fpath`. This file must have the format
    (nus, paths).

    Parameters
    ----------
    fpath: str
        Path to info file.
    nside: int
        Nside at which to read in the maps.
    pixel_indices: array_like(int, ndim=1) (optional, default=None)
        If not None only these indices are returned for all maps.

    Returns
    -------
    tuple(array_like(float, ndim=1), array_like(float, ndim=2))
        Tuple containing array of frequencies in the first element and array
        containing the corresponding (T, Q, U) maps in the second.
    """
    # Read data using genfromtxt due to heterogeneous data types.
    data = np.genfromtxt('test.txt', unpack=True, delimiter=" ",
                            dtype=[('nus', float), ('paths', object)])
    nus, fpaths = zip(*data)
    # Read in the maps pointed to by fpaths and return.
    return (nus, np.array([read_map(fpath, nside, field=(0, 1, 2), pixel_indices=pixel_indices) for fpath in fpaths]))


def write_map(fname, output_map, nside=None, pixel_indices=None):
    """Convenience function wrapping healpy's write_map and handling of partial sky

    Parameters
    ----------
    fname: str
        Path to fits file.
    output_map: array_like(float)
        Map or maps to be written to disk.
    nside: int (optional, default=None)
        Nside of the pixel indices, necessary just if pixel_indices is defined.
    pixel_indices: array_like(int, ndim=1) (optional, default=None)
        Pixels in RING ordering where the output map is defined.
    """
    if pixel_indices is None:
        full_map = output_map
    else:
        assert not nside is None, "nside is required if you provide pixel_indices"
        full_map = build_full_map(pixel_indices, output_map, nside)

    hp.write_map(fname, full_map, overwrite=True)

def read_map(fname, nside, field = (0), pixel_indices=None, verbose = False):
    """Convenience function wrapping healpy's read_map and upgrade /
    downgrade in one function.

    :param fname: path to fits file.
    :type fname: str.
    :param nside: nside to which we up or down grade.
    :type nside: int.
    :param field: fields of fits file from which to read.
    :type field: tuple of ints.
    :param pixel_indices: read only a subset of pixels in RING ordering
    :type field: array of ints.
    :param verbose: run in verbose mode.
    :type verbose: bool.
    :returns: numpy.ndarray -- the maps that have been read.
    """
    output_map = hp.ud_grade(hp.read_map(fname, field=field, verbose=verbose), nside_out=nside)
    if pixel_indices is None:
        return output_map
    else:
        try: # multiple components
            return [each[pixel_indices] for each in output_map]
        except IndexError: # single component
            return output_map[pixel_indices]

def read_key(Class, keyword, dictionary):
    """Gives the input class an attribute with the name of the keyword and
    value of the corresponding dictionary item.

    :param Class: Class instance for which we are defining attributes.
    :type Class: object.
    :param keyword: keyword of the dictionary element to set to Class.__class__.__name__
    :type keyworkd: str.
    :param dictionary: dictionary from which we are taking the value corresponding to keyword.
    :type dictionary: dict.
    :returns: does not return, but modifies inputs.
    """
    try:
        setattr(Class, '_%s__%s'%(Class.__class__.__name__, keyword), dictionary[keyword])
    except KeyError:
        print("%s not set."%keyword)
    return

def convert_units(unit1, unit2, nu):
    """Function to do unit conversions between Rayleigh-Jeans units, CMB
    units, and flux units.

    :param unit1: unit from which we are converting.
    :type unit1: str.
    :param unit2: unit to which we are converting.
    :type unit2: str.
    :param nu: frequency at which to calculate unit conversion.
    :type nu: float, np.ndarray.
    :returns: unit conversion coefficient - float, numpy.ndarray.
    """
    if "K_CMB" in unit1:
        #first deal with the unit conversion
        if "Jysr" in unit2:
            conversion_factor = K_CMB2Jysr(nu)
        elif "K_RJ" in unit2:
            conversion_factor = K_CMB2Jysr(nu) / K_RJ2Jysr(nu)
        elif "K_CMB" in unit2:
            conversion_factor = np.ones_like(nu)
        else:
            print("Incorrect format or unit.")

    elif "K_RJ" in unit1:
        if "Jysr" in unit2:
            conversion_factor = K_RJ2Jysr(nu)
        elif "K_CMB" in unit2:
            conversion_factor = K_RJ2Jysr(nu) / K_CMB2Jysr(nu)
        elif "K_RJ" in unit2:
            conversion_factor = np.ones_like(nu)
        else:
            print("Incorrect format or unit.")

    elif "Jysr" in unit1:
        if "Jysr" in unit2:
            conversion_factor = np.ones_like(nu)
        elif "K_RJ" in unit2:
            conversion_factor = 1. / K_RJ2Jysr(nu)
        elif "K_CMB" in unit2:
            conversion_factor = 1. / K_CMB2Jysr(nu)
        else:
            print("Incorrect format or unit.")

    # Now deal with the magnitude
    if "n" in unit1[0]:
        prefac = 1.e-9
    elif "u" in unit1[0]:
        prefac = 1.e-6
    elif "m" in unit1[0]:
        prefac = 1.e-3
    elif "k" in unit1[0]:
        prefac = 1.e3
    elif "M" in unit1[0]:
        prefac = 1.e6
    elif "G" in unit1[0]:
        prefac = 1.e9
    elif "K" in unit1[0]:
        prefac = 1.
    elif "J" in unit1[0]:
        prefac = 1.
    else:
        print("Invalid format for unit1 in convert_units")
        sys.exit(1)

    if "n" in unit2[0]:
        postfac = 1.e9
    elif "u" in unit2[0]:
        postfac = 1.e6
    elif "m" in unit2[0]:
        postfac = 1.e3
    elif "k" in unit2[0]:
        postfac = 1.e-3
    elif "M" in unit2[0]:
        postfac = 1.e-6
    elif "G" in unit2[0]:
        postfac = 1.e-9
    elif "K" in unit2[0]:
        postfac = 1.
    elif "J" in unit2[0]:
        postfac = 1.
    else:
        print("Invalid format for unit2 in convert_units")
        sys.exit(1)

    return np.array(conversion_factor * prefac * postfac)

@FloatOrArray
def K_CMB2Jysr(nu):
    """Kelvin_CMB to Janskies per steradian. Nu is in GHz.

    :param nu: frequency in GHz at which to calculate unit conversion.
    :type nu: float, numpy.ndarray
    :return: unit conversion coefficient - float.

    """
    return dB(nu, 2.7255) * 1.e26

@FloatOrArray
def K_RJ2Jysr(nu):
    """Kelvin_RJ to Janskies per steradian. Nu is in GHz.

    :param nu: frequency in GHz at which to calculate unit conversion.
    :type nu: float, numpy.ndarray.
    :return: unit conversion coefficient - float.

    """
    return  2. * (nu * 1.e9 / constants.c) ** 2 * constants.k * 1.e26

def B(nu, T):
    """Planck function.

    :param nu: frequency in GHz at which to evaluate planck function.
    :type nu: float.
    :param T: temperature of black body.
    :type T: float.
    :return: float -- black body brightness.

    """
    x = constants.h * nu * 1.e9 / constants.k / T
    return 2. * constants.h * (nu * 1.e9) ** 3 / constants.c ** 2 / np.expm1(x)

def dB(nu, T):
    """Differential planck function.

    :param nu: frequency in GHz at which to evaluate differential planck function.
    :type nu: float.
    :param T: temperature of black body.
    :type T: float.
    :return: float -- differential black body function.

    """
    x = constants.h * nu * 1.e9 / constants.k / T
    return B(nu, T) / T * x * np.exp(x) / np.expm1(x)

def bandpass_convert_units(unit, channel):
    """Function to calculate the unit conversion factor after bandpass
    integration from Jysr to either RJ, CMB or MJysr.

    Notes
    -----
    We integrate the signal in units of MJysr:
    $$
    [I_{\rm MJy/sr}] = \int I_{\rm MJy/sr}(\nu)  w(\nu)  d\nu
    $$
    In order to convert to K_CMB we define A_CMB:
    $$
    [T_{\rm CMB}] = A_CMB [I_{\rm MJy/sr}]
    $$
    If we observe the CMB then:
    $$
    [T_{\rm CMB}] = A_{\rm CMB}  \int dB(\nu, 2.7255) * T_{\rm CMB} w(\nu) d\nu
    $$
    So:
    $$
    A_{\rm CMB} = 1 / \int dB(\nu, 2.7255) w(\nu) d\nu.
    $$
    In a similar way for Rayleigh-Jeans units:
    $$
    A_{\rm RJ} = 1 / \int 2  k \nu^2 / c^2 w(\nu) d\nu
    $$

    Parameters
    ----------
    unit1, unit2: str
        Units from (`unit1`) and to (`unit2`) which to convert (K_RJ, K_CMB, Jysr) with SI prefix
        (n, u, m, k, G).
    channel: tuple(array_like(float, ndim=1), array_like(float, ndim=1))
        tuple containing bandpass frequencies and weights:
        (frequencies, weights).

    Returns
    -------
    float
        Unit conversion factor.

    """

    (frequencies, weights) = channel

    # normalise the weights and check that they integrate to 1.
    weights /= scipy.integrate.simps(weights, frequencies)

    #First do conversion of RJ, CMB, MJy
    if "CMB" in unit:
        prefac = 1. / scipy.integrate.simps(weights * K_CMB2Jysr(frequencies), frequencies)
    elif "RJ" in unit:
        prefac = 1. / scipy.integrate.simps(weights * K_RJ2Jysr(frequencies), frequencies)
    elif "Jysr" in unit:
        prefac = 1.

    #next sort out magnitude
    if "n" in unit[0]:
        postfac = 1.e9
    elif "u" in unit[0]:
        postfac = 1.e6
    elif "m" in unit[0]:
        postfac = 1.e3
    elif "k" in unit[0]:
        postfac = 1.e-3
    elif "M" in unit[0]:
        postfac = 1.e-6
    elif "G" in unit[0]:
        postfac = 1.e-9
    elif "K" in unit[0]:
        postfac = 1.
    elif "J" in unit[0]:
        postfac = 1.
    else:
        print("Invalid format for unit in bandpass_convert_units")
        sys.exit(1)

    return prefac * postfac


def invert_safe(m):
    """Function to safely invert almost positive definite matrix.

    Parameters
    ----------
    m: array_like(float, ndim=2)
        Matrix to invert.

    Returns
    -------
    array_like(float, ndim=2)
        Inverted matrix.

    """
    mb = m.copy()
    w_ok = False
    while not w_ok :
        w, v = np.linalg.eigh(mb)
        wmin = np.min(w)
        if wmin > 0:
            w_ok = True
        else:
            mb += np.diag(2. * np.max([1E-14, -wmin]) * np.ones(len(mb)))
    winv = 1. / w
    return np.dot(v, np.dot(np.diag(winv), np.transpose(v)))

def check_lengths(*args):
    """Function to check that all lengths of the input lists or arrays are equal.
    Returns True if lengths are equal, False if they are not.

    :param args: arrays or lists to check the length of.
    :type args: list, numpy.ndarray
    :return: True if lengths are equal, else False -- bool

    """
    return (len(set([len(x) for x in args])) <= 1)

def tophat_bandpass(nu_c, delta_nu, samples = 50):
    """Calculate a tophat bandpass for a given central frequency and width.
    This will return a tuple containing (frequencies, weights).

    :param nu_c: central frequency of bandpass.
    :type nu_c: float.
    :param delta_nu: width of bandpass.
    :type delta_nu: float.
    :param samples: number samples in bandpass; the more samples the more accurate the result.
    :type samples: int.
    :return: tuple - (frequencies, weights)

    """
    freqs = np.linspace(nu_c - delta_nu / 2., nu_c + delta_nu / 2., samples)
    weights = np.ones_like(freqs) / (freqs.size * delta_nu / samples)
    print(np.sum(weights * delta_nu))
    return (freqs, weights)

def plot_maps(ins_conf, plot_odir):
    """Function to plot output maps for a given instrument configuration.

    :param ins_conf: configuration file used to initialise the :class:`pysm.pysm.Instrument` used to generate the maps.
    :type: dict
    :param plot_odir: output directory to write maps to.
    :type plot_odir: string
    """
    #get path to maps and define output plot path.
    odir = os.path.abspath(plot_odir)
    opath = os.path.join(odir, ins_conf.output_prefix+"_maps.pdf")

    #get number of plots / 3
    if ins_conf.Use_Bandpass:
        N = len(ins_conf.Channel_Names)
    else:
        N = len(ins_conf.Frequencies)

    #initialise figure
    fig = plt.figure(1, figsize = (8, N*3))
    def add_map(maps, i):
        hp.mollview(maps[0], sub = (N, 3, i+1), fig = 1)
        hp.mollview(maps[1], sub = (N, 3, i+1), fig = 1)
        hp.mollview(maps[2], sub = (N, 3, i+1), fig = 1)
        return

    #do the plotting.
    if not ins_conf.Use_Bandpass:
        for i, f in enumerate(ins_conf.Frequencies):
            m = hp.read_map(ins_conf.file_path(f = f, extra_info = "total"), field = (0, 1, 2))
            add_map(m, i)

    elif self.Use_Bandpass:
        for i in enumerate(ins_conf.Channel_Names):
            m = hp.read_map(ins_conf.file_path(channel_name = c, extra_info = "total"), field = (0, 1, 2))
            add_map(m, i)

    fig.savefig(opath, bbox_inches = 'tight', background = 'white')

    return fig

def build_full_map(pixel_indices, pixel_values, nside):
    output_shape = list(pixel_values.shape)
    output_shape[-1] = hp.nside2npix(nside)
    full_map = hp.UNSEEN * np.ones(output_shape, dtype=np.float64)
    full_map[..., pixel_indices] = pixel_values
    return full_map

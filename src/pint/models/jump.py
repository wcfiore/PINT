"""Phase jumps. """
# phase_jump.py
# Defines PhaseJump timing model class
import astropy.units as u
import numpy

from pint.models.parameter import maskParameter
from pint.models.timing_model import DelayComponent, MissingParameter, PhaseComponent
from astropy import log


class DelayJump(DelayComponent):
    """Phase jumps

    Note
    ----
    This component is disabled for now, since we don't have any method
    to identify the phase jumps and delay jumps.
    """

    register = False
    category = "delay_jump"

    def __init__(self):
        super(DelayJump, self).__init__()
        self.add_param(maskParameter(name="JUMP", units="second"))
        self.delay_funcs_component += [self.jump_delay]

    def setup(self):
        super(DelayJump, self).setup()
        self.jumps = []
        for mask_par in self.get_params_of_type("maskParameter"):
            if mask_par.startswith("JUMP"):
                self.jumps.append(mask_par)
        for j in self.jumps:
            self.register_deriv_funcs(self.d_delay_d_jump, j)

    def validate(self):
        super(DelayJump, self).validate()

    def jump_delay(self, toas, acc_delay=None):
        """This method returns the jump delays for each toas section collected by
        jump parameters. The delay value is determined by jump parameter value
        in the unit of seconds.
        """
        tbl = toas.table
        jdelay = numpy.zeros(len(tbl))
        for jump in self.jumps:
            jump_par = getattr(self, jump)
            mask = jump_par.select_toa_mask(toas)
            # NOTE: Currently parfile jump value has opposite sign with our
            # delay calculation.
            jdelay[mask] += -jump_par.value
        return jdelay * u.second

    def d_delay_d_jump(self, toas, jump_param, acc_delay=None):
        tbl = toas.table
        d_delay_d_j = numpy.zeros(len(tbl))
        jpar = getattr(self, jump_param)
        mask = jpar.select_toa_mask(toas)
        d_delay_d_j[mask] = -1.0
        return d_delay_d_j * u.second / jpar.units

    def print_par(self):
        result = ""
        for jump in self.jumps:
            jump_par = getattr(self, jump)
            result += jump_par.as_parfile_line()
        return result


class PhaseJump(PhaseComponent):
    """A class to implement phase jumps."""

    register = True
    category = "phase_jump"

    def __init__(self):
        super(PhaseJump, self).__init__()
        self.add_param(maskParameter(name="JUMP", units="second"))
        self.phase_funcs_component += [self.jump_phase]

    def setup(self):
        super(PhaseJump, self).setup()
        self.jumps = []
        for mask_par in self.get_params_of_type("maskParameter"):
            if mask_par.startswith("JUMP"):
                self.jumps.append(mask_par)
        for j in self.jumps:
            # prevents duplicates from being added to phase_deriv_funcs
            if j in self.deriv_funcs.keys():
                del self.deriv_funcs[j]
            self.register_deriv_funcs(self.d_phase_d_jump, j)

    def validate(self):
        super(PhaseJump, self).validate()

    def jump_phase(self, toas, delay):
        """This method returns the jump phase for each toas section collected by
        jump parameters. The phase value is determined by jump parameter times
        F0.
        """
        tbl = toas.table
        jphase = numpy.zeros(len(tbl)) * (self.JUMP1.units * self._parent.F0.units)
        for jump in self.jumps:
            jump_par = getattr(self, jump)
            mask = jump_par.select_toa_mask(toas)
            # NOTE: Currently parfile jump value has opposite sign with our
            # phase calculation.
            jphase[mask] += jump_par.quantity * self._parent.F0.quantity
        return jphase

    def d_phase_d_jump(self, toas, jump_param, delay):
        tbl = toas.table
        jpar = getattr(self, jump_param)
        d_phase_d_j = numpy.zeros(len(tbl))
        mask = jpar.select_toa_mask(toas)
        d_phase_d_j[mask] = self._parent.F0.value
        return (d_phase_d_j * self._parent.F0.units).to(1 / u.second)

    def print_par(self):
        result = ""
        for jump in self.jumps:
            jump_par = getattr(self, jump)
            result += jump_par.as_parfile_line()
        return result

    def get_number_of_jumps(self):
        """Returns the number of jumps contained in this PhaseJump object."""
        return len(self.jumps)

    def get_jump_param_objects(self):
        """
        Returns a list of the maskParameter objects representing the jumps
        in this PhaseJump object.
        """
        jump_obs = [getattr(self, jump) for jump in self.jumps]
        return jump_obs

    def jump_params_to_flags(self, toas):
        """Take jumps created from .par file and add appropriate flags to toa table.

        This function was made specifically with pintk in mind for a way to properly
        load jump flags at the same time a .par file with jumps is loaded (like how
        jump_flags_to_params loads jumps from .tim files).

        Parameters
        ----------
        toas: TOAs object
            The TOAs which contain the TOA table to be modified
        """
        # for every jump, set appropriate flag for TOAs it jumps
        for jump_par in self.get_jump_param_objects():
            # find TOAs jump applies to
            mask = jump_par.select_toa_mask(toas)
            # apply to dictionaries
            self.add_jump_flags(jump_par, toas.table["flags"][mask], in_gui=False)

    def add_jump_flags(self, jump, selected_toas_table, in_gui):
        """Add flags to inputted TOA table."""
        if in_gui:
            # search for TOAs already jumped - pintk does not allow jumps added through GUI to overlap with existing jumps
            for dict in selected_toas_table:
                if "jump" in dict.keys():
                    log.warning(
                        "The selected toa(s) overlap an existing jump. Remove all interfering jumps before attempting to jump these toas."
                    )
                    return
            for dict in selected_toas_table:
                dict["jump"] = [jump.index]
                dict["gui_jump"] = [jump.index]
        else:
            for dict in selected_toas_table:
                if "jump" in dict.keys():
                    # check if jump flag already added - don't add flag twice
                    if jump.index in dict["jump"]:
                        continue
                    dict["jump"].append(jump.index)  # otherwise, add jump flag
                else:
                    dict["jump"] = [jump.index]

    # def remove_jump_flags(self, toas):
    #    """Remove flags to designated TOAs in TOA table."""

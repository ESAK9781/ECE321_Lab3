

import math
import lab_specific_code.specs as spec
from lab_specific_code.util import *
import random
from libs.optimizer import *
from libs.circuit_sol import *




def createCSAmpModel():
    mod = Circuit_Sol()
    mod.add_cap("1")
    mod.add_cap("by")

    mod.add_res("G1")
    mod.add_res("G2")
    mod.add_res("S1")
    mod.add_res("S2")
    mod.add_res("D")

    mod.add_num("VDD")

    return mod

def analyzeCSAmpModel(mod : Circuit_Sol):
    an = {} # out analysis

    RL = spec.CS_RL()

    RFG = spec.R_FG()
    Kn = spec.Kn()
    Vt = spec.Vt()


    VA = spec.VA()



    C1 = mod.get_c("1")
    Cby = mod.get_c("by")

    RG1 = mod.get_r("G1")
    RG2 = mod.get_r("G2")
    RS1 = mod.get_r("S1")
    RS2 = mod.get_r("S2")
    RD = mod.get_r("D")

    VDD = mod.get_n("VDD")


    VG = VDD * (RG2 / (RG1 + RG2))

    
    RS_DC = RS1 + RS2 # in series for DC, capacitor becomes open circuit
    a = 0.5 * Kn * RS_DC
    b = 1
    c = -(VG - Vt)

    inside_sqrt_term = b * b - 4 * a * c
    if (inside_sqrt_term < 0): # bad bad bad
        return None
    
    VOV = (-b + math.sqrt(inside_sqrt_term)) / (2 * a) # discard negative root
    if VOV <= 0:
        return None

    ID = 0.5 * Kn * VOV * VOV # reasonable first guess
    VS = ID * RS_DC
    VD = VDD - (ID * RD)
    VDS = VD - VS
    VGS = VG - VS

    for i in range(5): # iterate for increased accuracy
        ID = 0.5 * Kn * VOV * VOV * (1 + VDS / VA)
        VS = ID * RS_DC
        VD = VDD - (ID * RD)
        VDS = VD - VS
        VGS = VG - VS


    down_marg = VDS - VOV - 1.6
    up_marg = ID * parallel([RD, RL]) - 1.6

    # ######## Small Circuit Model ##############

    # transconductance
    gm = (2 * ID) / VOV

    # input resistance
    Ri = parallel([RG1, RG2])

    # open circuit gain
    Avo = (-RD) / ((1 / gm) + RS1)

    # output resistance
    Ro = RD

    # loaded gain
    in_divider = Ri / (Ri + RFG)

    Av = Avo * in_divider * (RL / (RL + Ro))



    VS_INTERMEDIATE = (RS2 / (RS1 + RS2)) * VS
    PD = mod.get_resistor("D").check_power(VDD - VD)
    PG1 = mod.get_resistor("G1").check_power(VDD - VG)
    PG2 = mod.get_resistor("G2").check_power(VG)
    PS1 = mod.get_resistor("S1").check_power(VS - VS_INTERMEDIATE)
    PS2 = mod.get_resistor("S2").check_power(VS_INTERMEDIATE)

    # transistor power not checked, because it is probably right




    # DOCUMENTATION: Distortion estimate formulas given by claude, I do not understand them.

    vin_peak = 1.6 / abs(Av)
    vgs_peak = vin_peak / (1 + gm * RS1)
    HD2 = vgs_peak / (4 * VOV)


    an = {
        "Vov": VOV,
        "ID": ID,
        "VG": VG,
        "VS": VS,
        "VD": VD,
        "VDS": VDS,
        "VGS": VGS,
        "gm": gm,
        "Ri": Ri,
        "Avo": Avo,
        "Ro": Ro,
        "Av": Av,
        "PD": PD,
        "PG1": PG1,
        "PG2": PG2,
        "PS1": PS1,
        "PS2": PS2,
        "downward_margin": down_marg,
        "upward_margin": up_marg,
        "HD2": HD2,
        "Vt": Vt
    }
    return an


def CSAmpModelScoreBreakdown(mod : Circuit_Sol):
    an = analyzeCSAmpModel(mod)
    if an is None:
        return {"invalid_configuration": (-1000000000, 1)}
    
    score = {}



    score["ID in range"] = (score_range(an["ID"], 0.000005, spec.CS_MAX_ID), 1)

    score["RI in range"] = (score_range(an["Ri"], spec.CS_MIN_RI, spec.CS_MAX_RI), 1)

    score["RO in range"]  = (score_under(an["Ro"], spec.CS_RO_MAX), 1)

    score["Av in range"] = (score_range(an["Av"], spec.CS_MIN_AV, spec.CS_MAX_AV), 1)





    sat_score = score_over(an["VGS"], an["Vt"]) * score_over(an["VDS"], an["Vov"])
    if (sat_score > 1):
        sat_score = 0
    sat_score = max(0, sat_score)

    score["In saturation"] = (sat_score, 1)


    
    
    score["Saturation margin"] = (score_over(an["downward_margin"], spec.CS_MARGIN) * score_over(an["upward_margin"], spec.CS_MARGIN), 1)

    


    score["RG1 Power"] = (score_under(an["PG1"], 0.75 * spec.RESISTOR_RATING) * 0.25, 0.25)
    score["RG2 Power"] = (score_under(an["PG2"], 0.75 * spec.RESISTOR_RATING) * 0.25, 0.25)
    score["RS1 Power"] = (score_under(an["PS1"], 0.75 * spec.RESISTOR_RATING) * 0.25, 0.25)
    score["RS2 Power"] = (score_under(an["PS2"], 0.75 * spec.RESISTOR_RATING) * 0.25, 0.25)
    score["RD Power"] = (score_under(an["PD"], 0.75 * spec.RESISTOR_RATING) * 0.25, 0.25)





    score["Low Distortion"] = (score_under(an["HD2"], 0.01), 1)



    meets_req = ((score["ID in range"][0] >= 0.9) and (score["RI in range"][0] >= 0.9)
                          and (score["RO in range"][0] >= 0.9) and (score["Av in range"][0] >= 0.9) 
                          and (sat_score >= 0.9))

    if (meets_req):
        score["Meets req"] = (1, 1)
    else:
        score["Meets req"] = (0.3, 1)



    return score

def scoreCSAmpModel(mod : Circuit_Sol):
    mod.num_vars["VDD"] = min(max(mod.num_vars["VDD"], spec.VDD_MIN), spec.VDD_MAX) # clamping

    reps = 1
    total_score = 0
    if (spec.USE_MONTE_CARLO):
        reps = spec.MONTE_CARLO_REPS


    for i in range(reps):
        score = 0
        max_score = 0


        bdown = CSAmpModelScoreBreakdown(mod)

        for category in bdown.keys():
            score += bdown[category][0]
            max_score += bdown[category][1]


        
        multiplier = 1
        if ("Meets req" in bdown.keys()):
            score -= bdown["Meets req"][0]
            max_score -= bdown["Meets req"][1]
            multiplier = bdown["Meets req"][0]

        
        total_score += (score / max_score) * multiplier

    return total_score / reps



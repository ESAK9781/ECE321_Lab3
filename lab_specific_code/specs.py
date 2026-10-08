

import random



USE_MONTE_CARLO = False
COMP_DEV_PERC_STDEV = 2 / 100
TRANS_DEV_PERC_STDEV = 5 / 100
MONTE_CARLO_REPS = 100




# SPECS

VDD_MIN = 10
VDD_MAX = 20
C_MIN = 0.00001
C_MAX = 0.0001
RESISTOR_RATING = 0.25
MAX_RESISTORS = 2



# VALUES

RESISTORS = [1, 10, 27, 33, 47, 51, 56, 68, 82, 91, 1000000, 2000000, 5100000, 6800000, 10000000, 100, 1000, 10000, 100000, 110, 1100, 11000, 110000, 120, 1200, 12000, 120000, 130, 1300, 13000, 130000, 150, 1500, 15000, 150000, 160, 1600, 16000, 160000, 180, 1800, 18000, 180000, 200, 2000, 20000, 200000, 220, 2200, 22000, 220000, 240, 2400, 24000, 240000, 270, 2700, 27000, 270000, 300, 3000, 30000, 300000, 330, 3300, 33000, 330000, 360, 3600, 36000, 360000, 390, 3900, 39000, 390000, 430, 4300, 43000, 430000, 470, 4700, 47000, 470000, 510, 5100, 51000, 510000, 560, 5600, 56000, 560000, 620, 6200, 62000, 620000, 680, 6800, 68000, 680000, 750, 7500, 75000, 750000, 820, 8200, 82000, 820000, 910, 9100, 91000, 910000]
CAPACITORS = [0.000010, 0.000022, 0.000033, 0.000047, 0.000100]
# Kn = 0.08
# Vt = 2
# VA = 100
# R_FG = 50


def Kn(exact=False):
    val = 0.08
    if (not USE_MONTE_CARLO) or exact:
        return val
    return val + (random.gauss(0, TRANS_DEV_PERC_STDEV) * val)

def Vt(exact=False):
    val = 2
    if (not USE_MONTE_CARLO) or exact:
        return val
    return val + (random.gauss(0, TRANS_DEV_PERC_STDEV) * val)

def VA(exact=False):
    val = 100
    if (not USE_MONTE_CARLO) or exact:
        return val
    return val + (random.gauss(0, COMP_DEV_PERC_STDEV) * val)

def R_FG(exact=False):
    val = 50
    if (not USE_MONTE_CARLO) or exact:
        return val
    return val + (random.gauss(0, COMP_DEV_PERC_STDEV) * val)




####################### CS_AMP #######################

# SPECS
CS_MAX_ID = 0.005
CS_MIN_RI = 100000
CS_MAX_RI = 150000
CS_RO_MAX = 5100
CS_MIN_AV = -30
CS_MAX_AV = -15
CS_MARGIN = 0.75




# VALUES

# CS_RL = 100000

def CS_RL(exact=False):
    val = 100000
    if (not USE_MONTE_CARLO) or exact:
        return val
    return val + (random.gauss(0, COMP_DEV_PERC_STDEV) * val)








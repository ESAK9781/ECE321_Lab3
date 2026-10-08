

import lab_specific_code.specs as spec
import random


ALLRES = []

def parallel(resistors):
    tot = 0
    for r in resistors:
        tot += (r ** -1)
    return (tot ** -1)

def series(resistors):
    tot = 0
    for r in resistors:
        tot += r
    return tot


class Resistor:
    def __init__(self):
        self.resistors = []
        self.in_parallel = False

    def eval(self, exact=False):
        out = 0
        if not self.is_valid():
            print("INVALID RESISTOR")
            exit(-1)
        if self.in_parallel:
            out = parallel(self.resistors)
        else:
            out = series(self.resistors)

        if (not spec.USE_MONTE_CARLO) or exact:
            return out

        return out + (random.gauss(0, spec.COMP_DEV_PERC_STDEV) * out)

    def is_valid(self):
        if not len(self.resistors):
            return False

        if len(self.resistors) > spec.MAX_RESISTORS:
            return False

        return True

    # based on a given voltage across, find the highest power lost over any of the individual resistors
    def check_power(self, voltage):
        if len(self.resistors) == 1: # single
            return (voltage ** 2) / self.eval()

        if (self.in_parallel): # parallel
            r = min(self.resistors)
            return (voltage ** 2) / r

        # series
        i = voltage / self.eval()
        r = max(self.resistors)
        return (i ** 2) * r





def gen_all_resistors():
    global ALLRES

    if len(ALLRES):
        return ALLRES

    if spec.MAX_RESISTORS != 2:
        print("ERROR: gen all resistors not defined for MAX_RESISTORS != 2")
        exit(-1)

    res = []

    for r in spec.RESISTORS:
        cr = Resistor()
        cr.resistors = [r]
        res.append(cr)

    for i in range(len(spec.RESISTORS)):
        for j in range(i, len(spec.RESISTORS)):
            cr1 = Resistor()
            cr1.resistors = [spec.RESISTORS[i], spec.RESISTORS[j]]
            res.append(cr1)

            cr2 = Resistor()
            cr2.resistors = [spec.RESISTORS[i], spec.RESISTORS[j]]
            cr2.in_parallel = True
            res.append(cr2)


    res.sort(key= lambda r : r.eval(True)) # deduplicate the resistors
    index = 0
    while (index < len(res) - 1):
        index += 1
        if (abs(res[index].eval(True) - res[index - 1].eval(True)) < 0.1): # remove very similar resistors
            if len(res[index].resistors) > len(res[index - 1].resistors):
                res.remove(res[index])
            else:
                res.remove(res[index - 1])
            index -= 1
    
    ALLRES = res
    return res





def score_range(val, min_val, max_val):
    if (val < max_val) and (val > min_val):
        margin = min(val - min_val, max_val - val) / ((max_val - min_val) / 2)
        return 0.9 + 0.1 * margin

    if (val < min_val):
        return 0.9 - (min_val - val) / (max_val - min_val)
    return 0.9 - (val - max_val)

def score_over(val, min_val):
    if (val < min_val):
        return 0.9 - ((min_val - val) / abs(min_val))

    return 0.9 + 0.1 * min(((val - min_val) / abs(min_val)), 1)

def score_under(val, max_val):
    return score_over(-val, -max_val)

def score_lerp(val, max, invert=False):
    out = (val / max)
    if invert:
        return 1 - out
    return out


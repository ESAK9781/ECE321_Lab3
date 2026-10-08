

from lab_specific_code.util import *
import lab_specific_code.specs as spec
from libs.optimizer import *
import random




class Circuit_Sol(OptimizeableSolution):
    def __init__(self):
        self.capacitors = {} # capacitor indices
        self.resistors = {} # resistor indices
        self.num_vars = {} # continuous numerical variables

    def add_res(self, r_name, val=None):
        if (val is not None):
            self.resistors[r_name] = val
        else:
            self.resistors[r_name] = 0

    def add_cap(self, c_name, val=None):
        if (val is not None):
            self.capacitors[c_name] = val
        else:
            self.capacitors[c_name] = 0

    def add_num(self, n_name, val=None):
        if (val is not None):
            self.num_vars[n_name] = val
        else:
            self.num_vars[n_name] = 0

    def get_r(self, r_name):
        return gen_all_resistors()[self.resistors[r_name]].eval()

    def get_resistor(self, r_name):
        return gen_all_resistors()[self.resistors[r_name]]

    def get_c(self, c_name):
        return spec.CAPACITORS[self.capacitors[c_name]]

    def get_n(self, n_name):
        return self.num_vars[n_name]

    def clone(self):
        clone_sol = Circuit_Sol()
        for rn in self.resistors.keys():
            clone_sol.add_res(rn, self.resistors[rn])
        for cn in self.capacitors.keys():
            clone_sol.add_cap(cn, self.capacitors[cn])
        for nn in self.num_vars.keys():
            clone_sol.add_num(nn, self.num_vars[nn])

        return clone_sol


    def getRandomSolution(self):
        rs = self.clone()
        for rname in self.resistors.keys():
            rs.resistors[rname] = random.randint(0, len(gen_all_resistors()) - 1)
        for cname in self.capacitors.keys():
            rs.capacitors[cname] = random.randint(0, len(spec.CAPACITORS) - 1)
        for nname in self.num_vars.keys():
            # a little specific to Vdd, but I think that is all we will use this for
            rs.num_vars[nname] = random.randint(10, 20) 
        return rs
    
    def fudgeSelf(self, fudge_factor):
        for rn in self.resistors.keys():
            delta = round(random.gauss(0, max(fudge_factor * len(gen_all_resistors()), 1)))
            new_ind = self.resistors[rn] + delta
            new_ind = max(min(new_ind, len(gen_all_resistors()) - 1), 0)
            self.resistors[rn] = new_ind

        for cn in self.capacitors.keys():
            delta = round(random.gauss(0, max(fudge_factor * len(spec.CAPACITORS), 1)))
            new_ind = self.capacitors[cn] + delta
            new_ind = max(min(new_ind, len(spec.CAPACITORS) - 1), 0)
            self.capacitors[cn] = new_ind

        for nn in self.num_vars.keys():
            delta = random.gauss(0, fudge_factor * self.get_n(nn))
            self.num_vars[nn] += delta

        



    
    # create a new solution that is the old sulution randomly fudged a bit
    def fudgeSolution(self, fudge_factor):
        sol = self.clone()
        sol.fudgeSelf(fudge_factor)
        return sol
    
    # create new solutions based on two parents
    def makeBabies(self, other_parent, fudge_factor, count, include_parents=True):
        kids = []

        presets = 0
        if (include_parents):
            presets = 2
            kids.append(self.clone())
            kids.append(other_parent.clone())


        for i in range(count - presets):
            baby = Circuit_Sol()
            for rn in self.resistors.keys():
                baby.add_res(rn, random.choice([self.resistors[rn], other_parent.resistors[rn]]))

            for cn in self.capacitors.keys():
                baby.add_cap(cn, random.choice([self.capacitors[cn], other_parent.capacitors[cn]]))

            for nn in self.num_vars.keys():
                perc = random.random()
                new_val = self.get_n(nn) * perc + other_parent.get_n(nn) * (1 - perc)
                baby.add_num(nn, new_val)

            baby.fudgeSelf(fudge_factor)

            kids.append(baby)

        return kids



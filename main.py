

import random
from lab_specific_code.CS_Amp import *
from libs.optimizer import *
from claude.claudes_code.reports import *


random.seed(42)
optimizer = EvolutionaryOptimizer(createCSAmpModel())

optimizer.max_learn_rate = 0.2
optimizer.anneal_rate = 0.1
optimizer.generation_size = 1000
cs_amp = optimizer.train(scoreCSAmpModel, 50, 10, True)

renderCSAmpReport(cs_amp, "./cs_amp_design.pdf")

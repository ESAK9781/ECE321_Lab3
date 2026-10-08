

import math


class OptimizeableSolution:
    def __init__(self):
        print("Cannot initialize abstract class.")
        
    def getRandomSolution(self):
        print("Function not implemented")
    
    def fudgeSelf(self, fudge_factor):
        print("Function not implemented")
    
    # create a new solution that is the old sulution randomly fudged a bit
    def fudgeSolution(self, fudge_factor):
        print("Function not implemented")
    
    # create new solutions based on two parents
    def makeBabies(self, other_parent, fudge_factor, count, include_parents=True):
        print("Function not implemented")
    


class EvolutionaryOptimizer:
    def __init__(self, seed_sol : OptimizeableSolution):
        self.seed = seed_sol
        self.max_learn_rate = 1
        self.generation_size = 100
        self.fudge_factor_calc = self.exp_fudge_factor
        self.anneal_rate = 0.5
    
    def lerp_fudge_factor(self, cur_epoch, last_epoch):
        perc = (last_epoch - cur_epoch) / last_epoch
        return perc * self.max_learn_rate
    
    def exp_fudge_factor(self, cur_epoch, last_epoch):
        return math.exp(-self.anneal_rate * (cur_epoch)) * self.max_learn_rate
    
    def train(self, score, epochs, print_interval=10, random_first_gen=True):
        print("Beginning training...")

        best_scores = []
        best = []
        if (not random_first_gen):
            best = [self.seed.fudgeSolution(0), self.seed.fudgeSolution(0)] # copy seed solution
        
        generation = []
        for c_ep in range(epochs):
            if ((c_ep == 0) and random_first_gen):
                for i in range(self.generation_size):
                    generation.append(self.seed.fudgeSolution(0).getRandomSolution())
            else:
                generation = best[0].makeBabies(best[1], self.fudge_factor_calc(c_ep, epochs), 
                                                self.generation_size, True)
            best = [generation[0], generation[1]]
            best_scores = [score(generation[0]), score(generation[1])]

            if (best_scores[1] > best_scores[0]): # swap to maintain order
                best[1], best[0] = best[0], best[1]
                best_scores[1], best_scores[0] = best_scores[0], best_scores[1]

            for i in range(2, len(generation)):
                new_score = score(generation[i])
                for j in range(len(best)):
                    if (best_scores[j] < new_score):
                        if (j == 0):
                            best[j + 1] = best[j]
                            best_scores[j + 1] = best_scores[j]
                        best[j] = generation[i]
                        best_scores[j] = new_score
                        break
                
            top_performance = max(best_scores[0], best_scores[1])
            if (c_ep % print_interval == 0):
                print("\tFinished epoch " + str(c_ep) + " out of " + str(epochs) 
                      + " : SCORE (" + str(top_performance) + ")")
        
        print("TRAINING COMPLETE: Best = " + str(max(best_scores[0], best_scores[1])))
        
        if (best_scores[0] > best_scores[1]):
            return best[0]
        return best[1]
            
        
        
        
        
    









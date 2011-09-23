"""Definition of model B-with-theta."""

import numpy as np
import scipy.optimize
from pyanno.util import random_categorical, log_beta_pdf, compute_counts


# map of `n` to list of all possible triplets of `n` elements
_triplet_combinations = {}
def _get_triplet_combinations(n):
    """Return array of all possible combinations of n elements in triplets.
    """
    if not _triplet_combinations.has_key(n):
        _triplet_combinations[n] = (
            np.array([i for i in np.ndindex(n,n,n)]) )
    return _triplet_combinations[n]


class ModelBt(object):
    """
    At the moment the model assumes 1) a total of 8 annontators, and 2) each
    item is annotated by 3 annotators.
    """

    def __init__(self, nclasses, nitems, gamma, theta,
                 use_priors=True, use_omegas=True):
        self.nclasses = nclasses
        self.nannotators = 8
        self.nitems = nitems
        # number of annotators rating each item in the loop design
        self.annotators_per_item = 3
        self.gamma = gamma
        self.theta = theta
        self.use_priors = use_priors
        self.use_omegas = use_omegas


    # TODO rename random_model to something more meaningful
    @staticmethod
    def random_model(nclasses, nitems,
                     gamma=None, theta=None,
                     use_priors=True, use_omegas=True):
        """Factory method returning a random model.

        Input:
        nclasses -- number of categories
        nitems -- number of items being annotated
        gamma -- probability of each annotation value
        theta -- the parameters of P( v_i | psi ) (one for each annotator)
        """

        if gamma is None:
            gamma = ModelBt._random_gamma(nclasses)

        if theta is None:
            nannotators = 8
            theta = ModelBt._random_theta(nannotators)

        model = ModelBt(nclasses, nitems, gamma, theta, use_priors, use_omegas)
        return model


    @staticmethod
    def _random_gamma(nclasses):
        beta = 2.*np.ones((nclasses,))
        return np.random.dirichlet(beta)


    @staticmethod
    def _random_theta(nannotators):
        return np.random.uniform(low=0.6, high=0.95,
                                 size=(nannotators,))


    def generate_labels(self):
        """Generate random labels from the model."""
        return random_categorical(self.gamma, self.nitems)


    # FIXME: different conventions on orientation of annotations here and in ModelB
    def generate_annotations(self, labels):
        """Generate random annotations given labels."""
        theta = self.theta
        nannotators = self.nannotators
        nitems_per_loop = self.nitems // nannotators

        annotations = np.empty((self.nitems, nannotators), dtype=int)
        for j in xrange(nannotators):
            for i in xrange(self.nitems):
                distr = self._theta_to_categorical(theta[j], labels[i])
                annotations[i,j]  = random_categorical(distr, 1)

        # mask annotation value according to loop design
        for l in xrange(nannotators):
            label_idx = np.arange(l+self.annotators_per_item, l+nannotators) % 8
            annotations[l*nitems_per_loop:(l+1)*nitems_per_loop, label_idx] = -1

        return annotations


    def _theta_to_categorical(self, theta, psi):
        """Returns P( v_i = psi | theta_i ) as a distribution."""
        distr = np.empty((self.nclasses,))
        distr.fill((1.-theta)/(self.nclasses-1.))
        distr[psi] = theta
        assert np.allclose(distr.sum(), 1.)
        return distr


    def mle(self, annotations):
        nclasses = self.nclasses

        counts = compute_counts(annotations, self.nclasses)
        params0 = self._random_initial_parameters(annotations)

        # wrap log likelihood function to give it to optimize.fmin
        _llhood_counts = self._log_likelihood_counts
        def _wrap_llhood(params):
            self.gamma, self.theta = self._vector_to_params(params)
            # minimize *negative* likelihood
            return - _llhood_counts(counts)

        # TODO: use gradient, constrained optimization
        params_best = scipy.optimize.fmin(_wrap_llhood, params0,
                                          xtol=1e-4, ftol=1e-4,
                                          disp=True, maxiter=1e+10,
                                          maxfun=1e+30)

        # parse arguments and update
        self.gamma, self.theta = self._vector_to_params(params_best)


    def _random_initial_parameters(self, annotations):
        if self.use_omegas:
            # estimate gamma from observed annotations
            gamma = np.bincount(annotations[annotations!=-1]) / (3.*self.nitems)
        else:
            gamma = ModelBt._random_gamma(self.nclasses)

        theta = ModelBt._random_theta(self.nannotators)
        return self._params_to_vector(gamma, theta)


    def _params_to_vector(self, gamma, theta):
        """Convert the tuple (gamma, theta) to a parameters vector.

        Used to interface with the optimization routines.
        """
        return np.r_[gamma[:-1], theta]


    def _vector_to_params(self, params):
        """Convert a parmeters vector to (gamma, theta) tuple.

        Used to interface with the optimization routines.
        """
        nclasses = self.nclasses
        gamma = np.zeros((nclasses,))
        gamma[:nclasses-1] = params[:nclasses-1]
        gamma[-1] = 1. - gamma[:nclasses-1].sum()
        theta = params[nclasses-1:]
        return gamma, theta


    def log_likelihood(self, annotations):
        """Compute the log likelihood of annotations given the model."""
        return self._log_likelihood_counts(compute_counts(annotations,
                                                          self.nclasses))


    def _log_likelihood_counts(self, counts):
        """Compute the log likelihood of annotations given the model.

        This method assumes the data is in counts format.
        """
        llhood = 0.
        # loop over the 8 combinations of annotators
        for i in range(8):
            # extract the theta parameters for this triplet
            triplet_indices = np.arange(i, i+3) % self.nannotators
            triplet_indices.sort()
            theta_triplet = self.theta[triplet_indices]

            # compute the likelihood for the triplet
            llhood += self._log_likelihood_triplet(counts[:,i],
                                                   theta_triplet)

        return llhood


    def _log_likelihood_triplet(self, counts_triplet, theta_triplet):
        """Compute the log likelihood of data for one triplet of annotators.

        Input:
        counts_triplet -- count data for one combination of annotators
        theta_triplet -- theta parameters of the current triplet
        """

        gamma = self.gamma

        # TODO: check if it's possible to replace these constraints with bounded optimization
        if (min(min(gamma), min(theta_triplet)) < 0.
            or max(max(gamma), max(theta_triplet)) > 1.):
            #return np.inf
            return -1e20

        if self.use_priors:
            # if requested, add prior over theta to log likelihood
            l = log_beta_pdf(theta_triplet, 2., 1.).sum()
        else:
            l = 0.

        # log \prod_n P(v_{ijk}^{n} | params)
        # = \sum_n log P(v_{ijk}^{n} | params)
        # = \sum_v_{ijk}  count(v_{ijk}) log P( v_{ijk} | params )
        #
        # where n is n-th annotation of triplet {ijk}]

        # compute P( v_{ijk} | params )
        pf = self._pattern_frequencies(theta_triplet)
        l += (counts_triplet * np.log(pf)).sum()

        return l


    def _pattern_frequencies(self, theta_triplet):
        """Compute vector of P(v_{ijk}|params) for each combination of v_{ijk}.

        The arguments gamma, theta, and v_ijk_combinations are called to
        avoid to look them up globally every time.
        """

        gamma = self.gamma
        nclasses = self.nclasses
        # list of all possible combinations of v_i, v_j, v_k elements
        v_ijk_combinations = _get_triplet_combinations(nclasses)

        # P( v_{ijk} | params ) = \sum_psi P( v_{ijk} | psi, params ) P( psi )

        pf = 0.
        not_theta = (1.-theta_triplet) / (nclasses-1.)
        p_v_ijk_given_psi = np.empty_like(v_ijk_combinations, dtype=float)
        for psi in range(nclasses):
            for j in range(3):
                p_v_ijk_given_psi[:,j] = np.where(v_ijk_combinations[:,j]==psi,
                                                  theta_triplet[j],
                                                  not_theta[j])
            pf += p_v_ijk_given_psi.prod(1) * gamma[psi]
        return pf

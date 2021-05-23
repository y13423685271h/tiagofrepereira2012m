#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Manuel Guenther <Manuel.Guenther@idiap.ch>

import bob
import numpy
import os
import math

class UBMGMMRegularTool:
  """Tool chain for computing Universal Background Models and Gaussian Mixture Models of the features"""

  
  def __init__(self, setup):
    """Initializes the local UBM-GMM tool chain with the given file selector object"""
    self.m_config = setup
    self.m_ubm = None
    
    self.use_unprojected_features_for_model_enrol = True

  #######################################################
  ################ UBM training #########################
  def __normalize_std_array__(self, array):
    """Applies a unit variance normalization to an array"""

    # Initializes variables
    n_samples = array.shape[0]
    length = array.shape[1]
    mean = numpy.ndarray((length,), 'float64')
    std = numpy.ndarray((length,), 'float64')

    mean.fill(0)
    std.fill(0)

    # Computes mean and variance
    for k in range(n_samples):
      x = array[k,:].astype('float64')
      mean += x
      std += (x ** 2)

    mean /= n_samples
    std /= n_samples
    std -= (mean ** 2)
    std = std ** 0.5 # sqrt(std)

    ar_std_list = []
    for k in range(n_samples):
      ar_std_list.append(array[k,:].astype('float64') / std)
    ar_std = numpy.vstack(ar_std_list)

    return (ar_std,std)


  def __multiply_vectors_by_factors__(self, matrix, vector):
    """Used to unnormalise some data"""
    for i in range(0, matrix.shape[0]):
      for j in range(0, matrix.shape[1]):
        matrix[i, j] *= vector[j]

  
  #######################################################
  ################ UBM training #########################

  def _train_projector_using_array(self, array, projector_file):

    print " .... Training with %d feature vectors" % array.shape[0]
    
    # Computes input size
    input_size = array.shape[1]

    # Normalizes the array if required
    print " .... Normalizing the array"

    if not self.m_config.norm_KMeans:
      normalized_array = array
    else:
      normalized_array, std_array = self.__normalize_std_array__(array)

    # Creates the machines (KMeans and GMM)
    print " .... Creating machines"
    kmeans = bob.machine.KMeansMachine(self.m_config.n_gaussians, input_size)
    self.m_ubm = bob.machine.GMMMachine(self.m_config.n_gaussians, input_size)

    # Creates the KMeansTrainer
    kmeans_trainer = bob.trainer.KMeansTrainer()
    kmeans_trainer.convergence_threshold = self.m_config.convergence_threshold
    kmeans_trainer.max_iterations = self.m_config.iterk

    # Trains using the KMeansTrainer
    print "  -> Training K-Means"
    kmeans_trainer.train(kmeans, normalized_array)

    [variances, weights] = kmeans.get_variances_and_weights_for_each_cluster(normalized_array)
    means = kmeans.means

    # Undoes the normalization
    print " .... Undoing normalization"
    if self.m_config.norm_KMeans:
      self.__multiply_vectors_by_factors__(means, std_array)
      self.__multiply_vectors_by_factors__(variances, std_array ** 2)

    # Initializes the GMM
    self.m_ubm.means = means
    self.m_ubm.variances = variances
    self.m_ubm.weights = weights
    self.m_ubm.set_variance_thresholds(self.m_config.variance_threshold)

    # Trains the GMM
    print "  -> Training GMM"
    trainer = bob.trainer.ML_GMMTrainer(self.m_config.update_means, self.m_config.update_variances, self.m_config.update_weights)
    trainer.convergence_threshold = self.m_config.convergence_threshold
    trainer.max_iterations = self.m_config.iterk
    trainer.train(self.m_ubm, array)

    # Saves the UBM to file
    print " .... Saving model to file '%s'" % projector_file
    self.m_ubm.save(bob.io.HDF5File(projector_file, "w"))
    
 
  def train_projector(self, train_files, projector_file):
    """Computes the Universal Background Model from the training ("world") data"""

    print "  -> Training UBM model with %d training files" % len(train_files)
    
    train_features = [bob.io.load(str(train_files[k])) for k in sorted(train_files.keys())]

    # Loads the data into an array
    array = numpy.vstack(train_features)

    self._train_projector_using_array(array, projector_file)    
    

  #######################################################
  ############## GMM training using UBM #################

  def load_projector(self, projector_file):
    """Reads the UBM model from file"""
    # read UBM
    self.m_ubm = bob.machine.GMMMachine(bob.io.HDF5File(projector_file))
    self.m_ubm.set_variance_thresholds(self.m_config.variance_threshold)
    # prepare MAP_GMM_Trainer
    if self.m_config.responsibilities_threshold > 0.:
      self.m_trainer = bob.trainer.MAP_GMMTrainer(self.m_config.relevance_factor, True, False, False, self.m_config.responsibilities_threshold)
    else:
      self.m_trainer = bob.trainer.MAP_GMMTrainer(self.m_config.relevance_factor, True, False, False)
    self.m_trainer.convergence_threshold = self.m_config.convergence_threshold
    self.m_trainer.max_iterations = self.m_config.iterg_enrol
    self.m_trainer.set_prior_gmm(self.m_ubm)

    # Initializes GMMStats object
    self.m_gmm_stats = bob.machine.GMMStats(self.m_ubm.dim_c, self.m_ubm.dim_d)


  def _enrol_using_array(self,array):
    print " -> Enrolling with %d feature vectors" % array.shape[0]
    gmm = bob.machine.GMMMachine(self.m_ubm)
    gmm.set_variance_thresholds(self.m_config.variance_threshold)
    self.m_trainer.train(gmm, array)
    return gmm


  def enrol(self, feature_arrays):
    """Enrolls a GMM using MAP adaptation, given a list of 2D numpy.ndarray's of feature vectors"""

    array = numpy.vstack([v for v in feature_arrays])
    # Use the array to train a GMM and return it
    return self._enrol_using_array(array)

    
  ######################################################
  ################ Feature comparison ##################
  def read_model(self, model_file):
    return bob.machine.GMMMachine(bob.io.HDF5File(model_file))

  #def read_probe(self, probe_file):
  #  """Read the type of features that we require, namely GMM_Stats"""
  #  return bob.machine.GMMStats(bob.io.HDF5File(probe_file))

  def score(self, model, probe):
    """Computes the score for the given model and the given probe using the scoring function from the config file.
       The score are Log-Likelihood. Therefore, the log of the likelihood ratio is obtained by computing the 
       following difference."""
    score = 0
    for i in range(probe.shape[0]):
      score += model.forward(probe[i,:]) - self.m_ubm.forward(probe[i,:])
    return score/probe.shape[0]


#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Manuel Guenther <Manuel.Guenther@idiap.ch>
# Elie Khoury <Elie.Khoury@idiap.ch>
# Fri Aug 30 11:48:25 CEST 2013
#
# Copyright (C) 2012-2013 Idiap Research Institute, Martigny, Switzerland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os, sys, math
import argparse
import imp
import copy

import gridtk
from .. import toolchain


class ToolChainExecutor:
  """This class is a helper class to provide functionality to execute
  tool chains. It manages the configuration files and the command line
  options, as well as the grid execution of the tasks."""

  def __init__(self, args):
    """Initializes the Tool chain executor"""
    # remember command line arguments
    self.m_args = args
    # load configuration files specified on command line
    self.m_database_config = imp.load_source('database', args.database)
    self.m_tool_config = imp.load_source('tool_chain', args.tool)
    self.m_preprocessor_config =  imp.load_source('preprocessor', args.preprocessor)
    self.m_feature_extractor_config = imp.load_source('feature_extractor', args.features)
    if args.grid:
      self.m_grid_config = imp.load_source('grid', args.grid)

    self.__generate_configuration__()

    # generate the tools that we will need
    self.m_preprocessor = self.m_preprocessor_config.preprocessor(self.m_preprocessor_config)
    self.m_feature_extractor = self.m_feature_extractor_config.feature_extractor(self.m_feature_extractor_config)
    self.m_tool = self.m_tool_config.tool(self.m_tool_config)

  def required_command_line_options(parser):
    """Initializes the minimum command line options that are
    required to run this experiment"""

    #######################################################################################
    ############## options that are required to be specified #######################
    config_group = parser.add_argument_group('\nConfiguration files that need to be specified on the command line')
    config_group.add_argument('-d', '--database', metavar = 'FILE', type = str, required = True,
        help = 'The database configuration file')
    config_group.add_argument('-t', '--tool-chain', type = str, dest = 'tool', required = True, metavar = 'FILE',
        help = 'The tool chain configuration file')
    config_group.add_argument('-p', '--preprocessing', metavar = 'FILE', type = str, dest = 'preprocessor', required = True,
        help = 'Configuration script for Voice Activity Detection')
    config_group.add_argument('-f', '--features', metavar = 'FILE', type = str, required = True,
        help = 'Configuration script for extracting the features')
    config_group.add_argument('-g', '--grid', metavar = 'FILE', type = str,
        help = 'Configuration file for the grid setup; if not specified, the commands are executed on the local machine')

    #######################################################################################
    ############## options to modify default directories or file names ####################
    dir_group = parser.add_argument_group('\nDirectories that can be changed according to your requirements')
    dir_group.add_argument('-T', '--temp-directory', metavar = 'DIR', type = str, dest = 'temp_dir',
        help = 'The directory for temporary files; if not specified, /idiap/temp/$USER/database-name/sub-dir (or /scratch/$USER/database-name/sub-dir, when executed locally) is used')
    dir_group.add_argument('-U', '--user-directory', metavar = 'DIR', type = str, dest = 'user_dir',
        help = 'The directory for temporary files; if not specified, /idiap/user/$USER/database-name/sub-dir is used')
    dir_group.add_argument('-b', '--sub-directory', metavar = 'DIR', type = str, dest = 'sub_dir', default = 'default',
        help = 'The sub-directory where the results of the current experiment should be stored.')
    dir_group.add_argument('-s', '--score-sub-directory', metavar = 'DIR', type = str, dest = 'score_sub_dir', default = 'scores',
        help = 'The sub-directory where to write the scores to.')

    file_group = parser.add_argument_group('\nName (maybe including a path relative to the --temp-dir) of files that will be generated. Note that not all files will be used by all tools')
    file_group.add_argument('--extractor-file', type = str, metavar = 'FILE', default = 'Extractor.hdf5',
        help = 'Name of the file to write the feature extractor into')
    file_group.add_argument('--projector-file', type = str, metavar = 'FILE', default = 'Projector.hdf5',
        help = 'Name of the file to write the feature projector into')
    file_group.add_argument('--enroler-file' , type = str, metavar = 'FILE', default = 'Enroler.hdf5',
        help = 'Name of the file to write the model enroler into')
    file_group.add_argument('-G', '--submit-db-file', type = str, metavar = 'FILE', default = 'submitted.sql3', dest = 'gridtk_db',
        help = 'The db file in which the submitted jobs will be written (only valid with the --grid option)')

    sub_dir_group = parser.add_argument_group('\nSubdirectories of certain parts of the toolchain. You can specify directories in case you want to reuse parts of the experiments (e.g. extracted features) in other experiments. Please note that these directories are relative to the --temp-dir')
    sub_dir_group.add_argument('--preprocessed-features-directory', type = str, metavar = 'DIR', default = 'preprocessed', dest = 'preprocessed_dir',
        help = 'Name of the directory of the VAD files')
    sub_dir_group.add_argument('--features-directory', type = str, metavar = 'DIR', default = 'features', dest = 'features_dir',
        help = 'Name of the directory of the features')
    sub_dir_group.add_argument('--projected-directory', type = str, metavar = 'DIR', default = 'projected_ubm', dest = 'projected_ubm_dir',
        help = 'Name of the directory where the projected data should be stored')


    other_group = parser.add_argument_group('\nFlags that change the behaviour of the experiment')
    other_group.add_argument('-r', '--dry-run', action='store_true', dest='dry_run',
        help = 'Only report the grid commands that will be executed, but do not execute them')

    #######################################################################################
    ################# options for skipping parts of the toolchain #########################
    skip_group = parser.add_argument_group('\nFlags that allow to skip certain parts of the experiments. This does only make sense when the generated files are already there (e.g. when reusing parts of other experiments)')
    skip_group.add_argument('--skip-preprocessing', '--nopre', action='store_true', dest='skip_preprocessing',
        help = 'Skip the VAD step')
    skip_group.add_argument('--skip-feature-extraction-training', '--nofet', action='store_true', dest='skip_feature_extraction_training',
        help = 'Skip the feature extraction training step')
    skip_group.add_argument('--skip-feature-extraction', '--nofe', action='store_true', dest='skip_feature_extraction',
        help = 'Skip the feature extraction step')
    skip_group.add_argument('--skip-projection-training', '--noprot', action='store_true', dest='skip_projection_training',
        help = 'Skip the feature extraction training')
    skip_group.add_argument('--skip-projection-ubm', '--noproubm', action='store_true', dest='skip_projection_ubm',
        help = 'Skip the feature UBM projection')
    skip_group.add_argument('--skip-enroler-training', '--noenrt', action='store_true', dest='skip_enroler_training',
        help = 'Skip the training of the model enrolment')
    skip_group.add_argument('--skip-model-enrolment', '--noenr', action='store_true', dest='skip_model_enrolment',
        help = 'Skip the model enrolment step')
    skip_group.add_argument('--skip-score-computation', '--nosc', action='store_true', dest='skip_score_computation',
        help = 'Skip the score computation step')
    skip_group.add_argument('--skip-concatenation', '--nocat', action='store_true', dest='skip_concatenation',
        help = 'Skip the score concatenation step')

    return (config_group, dir_group, file_group, sub_dir_group, other_group, skip_group)

  # make this methos static.
  required_command_line_options = staticmethod(required_command_line_options)


  def set_common_parameters(self, calling_file, parameters, fake_job_id = 0, temp_dir = None):
    """Sets the parameters that the grid jobs require to be called.
    Just hand over all parameters of the spkverify script, and this function will do the rest.
    Please call this function before submitting jobs to the grid
    using the submit_jobs_to_grid function"""
    
    # we want to have the executable with the name of this file, which is laying in the bin directory
    self.m_common_parameters = [p for p in parameters[0:] if not '--skip' in p and not '--no' in p and p not in ('-q', '--dry-run')]

    # job id used for the dry-run
    self.m_fake_job_id = fake_job_id
    
    # define the dir from which the current executable was called
    if os.path.exists(parameters[0]):
      self.m_bin_dir = os.path.dirname(os.path.realpath(parameters[0]))
    else:
      # This should happen only during nose testing under some weird conditions.
      # Since nose tests should not actually run anything in the grid, we can use a fake directory here.
      self.m_bin_dir = './bin'
    self.m_executable = os.path.join(self.m_bin_dir, os.path.basename(calling_file))
    self.m_jman = os.path.join(self.m_bin_dir, 'jman')
    # generate job manager and set the temp dir
    if self.m_grid_config.grid_type == 'local':
      self.m_job_manager = gridtk.local.JobManagerLocal(database = self.m_args.gridtk_db, wrapper_script = self.m_jman)
    elif self.m_grid_config.grid_type == 'sge':
      self.m_job_manager = gridtk.sge.JobManagerSGE(database = self.m_args.gridtk_db, wrapper_script = self.m_jman)
    else:
      raise ValueError("The JobManager type '%s' is not supported.")
    self.m_logs_directory = os.path.join(temp_dir if temp_dir else self.m_configuration.base_output_TEMP_dir, "grid_tk_logs")






    # To remove
    self.m_temp_dir = temp_dir if temp_dir else self.m_configuration.base_output_TEMP_dir


  def protocol_specific_configuration(self):
    """Overload this function to set up configurations that are
    sepcific for your verification protocol"""
    raise NotImplementedError

  def __generate_configuration__(self):
    """generates the configuration based on configuration files
    and command line arguments"""
    # copy database configuration
    self.m_configuration = self.m_database_config
    # add command line based arguments

    user_name = os.environ['USER']
    if self.m_args.user_dir:
      self.m_configuration.base_output_USER_dir = os.path.join(self.m_args.user_dir, self.m_args.sub_dir)
    else:
      self.m_configuration.base_output_USER_dir = os.path.join("/idiap/user", user_name, self.m_database_config.name, self.m_args.sub_dir)

    if self.m_args.temp_dir:
      self.m_configuration.base_output_TEMP_dir = os.path.join(self.m_args.temp_dir, self.m_args.sub_dir)
    else:
      if not self.m_args.grid:
        self.m_configuration.base_output_TEMP_dir = os.path.join("/scratch", user_name, self.m_database_config.name, self.m_args.sub_dir)
      else:
        self.m_configuration.base_output_TEMP_dir = os.path.join("/idiap/temp", user_name, self.m_database_config.name, self.m_args.sub_dir)

    self.m_configuration.extractor_file = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.extractor_file)
    self.m_configuration.projector_file = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.projector_file)
    self.m_configuration.enroler_file = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.enroler_file)
    self.m_configuration.preprocessed_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.preprocessed_dir)
    self.m_configuration.features_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.features_dir)
    self.m_configuration.projected_ubm_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.projected_ubm_dir)
    

    # call configurations for the specific protocol
    self.protocol_specific_configuration()


################################################################################################
########################## Functions concerning the grid setup #################################
################################################################################################


  def __generate_job_array__(self, list_to_split, number_of_files_per_job):
    """Generates an array for the list to be split and the number of files that one job should generate"""
    n_jobs = int(math.ceil(len(list_to_split) / float(number_of_files_per_job)))
    return (1,n_jobs,1)


  def indices(self, list_to_split, number_of_files_per_job):
    """This function returns the first and last index for the files for the current job ID.
       If no job id is set (e.g., because a sub-job is executed locally), it simply returns all indices"""
    # test if the 'SEG_TASK_ID' environment is set
    sge_task_id = os.getenv('SGE_TASK_ID')
    if sge_task_id == None:
      # task id is not set, so this function is not called from a grid job
      # hence, we process the whole list
      return (0,len(list_to_split))
    else:
      job_id = int(sge_task_id) - 1
      # compute number of files to be executed
      start = job_id * number_of_files_per_job
      end = min((job_id + 1) * number_of_files_per_job, len(list_to_split))
      return (start, end)


  def submit_grid_job(self, command, list_to_split = None, number_of_files_per_job = 1, dependencies=[], name = None, **kwargs):
    """Submits a job to the grid"""

    
    # create the command to be executed
    cmd = [
            self.m_executable,
            '--execute-sub-task',
          ]
          
    cmd += command.split()
    cmd += self.m_common_parameters
    
    # if no job name is specified, create one
    if name is None:
      name = command.split(' ')[0].replace('--','')
      log_sub_dir = command.replace(' ','__').replace('--','')
    else:
      log_sub_dir = name
    # generate log directory
    logdir = os.path.join(self.m_temp_dir, 'logs', log_sub_dir)

    # generate job array
    if list_to_split is not None:
      array = self.__generate_job_array__(list_to_split, number_of_files_per_job)
    else:
      array = None

    # submit the job to the job mamager
    if not self.m_args.dry_run:
      job_id = self.m_job_manager.submit(
          command_line = cmd, 
          dependencies=dependencies,
          log_dir = logdir,
          name=name, 
          array=array,
          **kwargs)
      print("submitted: %s" %job_id)
      return job_id
    else:
      self.m_fake_job_id += 1
      print('would have submitted job %s with id %d as' %(name, self.m_fake_job_id)),
      print(str(' '.join(use_cmd[2:])))
      print ("with dependencies %s" % str(dependencies))
      return self.m_fake_job_id



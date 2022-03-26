#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Laurent El Shafey <laurent.el-shafey@idiap.ch>
# Tue Jan  8 13:36:12 CET 2013
#
# Copyright (C) 2011-2013 Idiap Research Institute, Martigny, Switzerland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This script fuses scores from various systems,
from a score file in four or five column format.

Note: The score file has to contain the exact probe file names as the 3rd (4column) or 4th (5column) column.
"""



import bob, os, sys

def parse_command_line(command_line_options):
  """Parse the program options"""

  usage = 'usage: %s [arguments]' % os.path.basename(sys.argv[0])

  import argparse
  parser = argparse.ArgumentParser(usage=usage, description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  # This option is not normally shown to the user...
  parser.add_argument('--self-test', action = 'store_true', help = argparse.SUPPRESS)
  parser.add_argument('-s', '--score-development', nargs='*', required = True, help = 'The score file in 4 or 5 column format to train the fusion parameters.')
  parser.add_argument('-t', '--score-evaluation', nargs='*', required = True, help = 'The score file in 4 or 5 column format to calibrate.')
  parser.add_argument('-f', '--score-fused-development-file', required = True, help = 'The calibrated development score file in 4 or 5 column format to calibrate.')
  parser.add_argument('-g', '--score-fused-evaluation-file', required = True, help = 'The calibrated evaluation score file in 4 or 5 column format to calibrate.')
  parser.add_argument('-p', '--parser', default = '4column', choices = ('4column', '5column'), help = 'The type of the score file.')

  args = parser.parse_args(command_line_options)

  return args

def main(command_line_options = None):
  """Computes and plots the CMC curve."""
  args = parse_command_line(command_line_options)

  # read data
  n_systems = len(args.score_development)
  for i in range(n_systems):
    if not os.path.isfile(args.score_development[i]): raise IOError("The given score file does not exist")
  # pythonic way: create inline dictionary "{...}", index with desired value "[...]", execute function "(...)"
  data = []
  for i in range(n_systems):
    data.append({'4column' : bob.measure.load.split_four_column, '5column' : bob.measure.load.split_five_column}[args.parser](args.score_development[i]))
  import numpy
  data_neg = numpy.vstack([data[k][0] for k in range(n_systems)]).T.copy()
  data_pos = numpy.vstack([data[k][1] for k in range(n_systems)]).T.copy()
  trainer = bob.trainer.CGLogRegTrainer(0.5, 1e-10, 10000)
  machine = trainer.train(data_neg, data_pos)

  # fuse development scores
  data_dev = []
  for i in range(n_systems):
    data_dev.append({'4column' : bob.measure.load.four_column, '5column' : bob.measure.load.five_column}[args.parser](args.score_development[i]))
  ndata = len(data_dev[0])
  outf = open(args.score_fused_development_file, 'w')
  for k in range(ndata):
    scores = numpy.array([[v[k][-1] for v in data_dev]], dtype=numpy.float64)
    s_fused = machine.forward(scores)[0,0]  
    line = " ".join(data_dev[0][k][0:-1]) + " " + str(s_fused) + "\n"
    outf.write(line)

  # fuse evaluation scores
  data_eval = []
  for i in range(n_systems):
    data_eval.append({'4column' : bob.measure.load.four_column, '5column' : bob.measure.load.five_column}[args.parser](args.score_evaluation[i]))
  ndata = len(data_eval[0])
  outf = open(args.score_fused_evaluation_file, 'w')
  for k in range(ndata):
    scores = numpy.array([[v[k][-1] for v in data_eval]], dtype=numpy.float64)
    s_fused = machine.forward(scores)[0,0]
    line = " ".join(data_eval[0][k][0:-1]) + " " + str(s_fused) + "\n"
    outf.write(line)

  return 0

if __name__ == '__main__':
  main(sys.argv[1:])

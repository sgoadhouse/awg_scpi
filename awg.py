#!/usr/bin/env python3

# Copyright (c) 2018,2019,2020,2021,2022 Stephen Goadhouse <sgoadhouse@virginia.edu>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Neotion nor the names of its contributors may
#       be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL NEOTION BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#-------------------------------------------------------------------------------
#  Handle several remote functions of Siglent SDG series arbitrary waveform
#  generators (AWG)
#
# Using my new awg_scpi Class
#
# pyvisa 1.11.3 (or higher) (http://pyvisa.sourceforge.net/)
# pyvisa-py 0.5.1 (or higher) (https://pyvisa-py.readthedocs.io/en/latest/)
#
# NOTE: pyvisa-py replaces the need to install NI VISA libraries
# (which are crappily written and buggy!) Wohoo!
#
#-------------------------------------------------------------------------------

# For future Python3 compatibility:
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import random
import sys
import argparse

from statistics import mean, stdev
from datetime import datetime
from time import sleep

from awg_scpi import AWG

def handleFilename(fname, ext, unique=True, timestamp=True):

    # If extension exists in fname, strip it and add it back later
    # after handle versioning
    ext = '.' + ext                       # don't pass in extension with leading '.'
    if (fname.endswith(ext)):
        fname = fname[:-len(ext)]

    # Make sure filename has no path components, nor ends in a '/'
    if (fname.endswith('/')):
        fname = fname[:-1]
        
    pn = fname.split('/')
    fname = pn[-1]
        
    # Assemble full pathname so files go to ~/Downloads    if (len(pp) > 1):
    pn = os.environ['HOME'] + "/Downloads"
    fn = pn + "/" + fname

    if (timestamp):
        # add timestamp suffix
        fn = fn + '-' + datetime.now().strftime("%Y%0m%0d-%0H%0M%0S")

    suffix = ''
    if (unique):
        # If given filename exists, try to find a unique one
        num = 0
        while(os.path.isfile(fn + suffix + ext)):
            num += 1
            suffix = "-{}".format(num)

    fn += suffix + ext

    return fn

def parse(awg):

    parser = argparse.ArgumentParser(description='Access Arbitrary Waveform Generator via SCPI')

    mutex_grp = parser.add_mutually_exclusive_group(required=True)    
    mutex_grp.add_argument('--setup_save', '-s', metavar='outfile.jstp', help='save the current Basic Wave setup of the AWG into the named file')
    mutex_grp.add_argument('--setup_load', '-l', metavar='infile.jstp', help='load the current Basic Wave setup of the AWG from the named file')
    mutex_grp.add_argument('--counter',    '-f', action='store_true', help='Enable the Frequency Counter and output measured values until Ctrl-C')

    # Print help if no options are given on the command line
    if (len(sys.argv) <= 1):
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    
    return args

def main():

    # Set to the IP address of the Arbitrary Waveform Generator (AWG)
    pyvisa_awg = os.environ.get('AWG_IP', 'TCPIP0::172.16.2.13::INSTR')
    
    ## Connect to the AWG
    awg = AWG(pyvisa_awg)

    ## Help to use with other models. Likely will not need these three
    ## lines once get IDN strings from all known AWGs that I
    ## want to use
    awg.open()
    print('Potential SCPI Device: ' + awg.idn() + '\n')
    awg.close()
    
    ## Upgrade Object to best match based on IDN string
    awg = awg.getBestClass()
    
    ## Open this object and work with it
    awg.open()
    print('Using SCPI Device:     ' + awg.idn() + ' of series: ' + awg.series + '\n')

    # parse command line options with knowledge of instrument
    args = parse(awg)
    
    if (args.counter):

        # Enable the Frequency Counter which will change the AWG screen
        if not awg.isFreqCntrOn():
            awg.setFreqCntrOn()

        print("\nFrequency Counter is {}".format(awg.isFreqCntrOn() and "ON" or "OFF"))
        print("Ref Freq: {}Hz  Trig Lvl: {}V  Couple: {}  HFR: {}".format(
            awg.queryFreqCntrReference(), awg.queryFreqCntrTrigLevel(),
            awg.isFreqCntrCoupleDC() and "DC" or "AC", awg.isFreqCntrHfrON() and "ON" or "OFF"))
        print()

        print('\nNOTE: If returned value is >= {}, then it is to be considered N/A or INVALID\n'.format(awg.OverRange))
        print('     {: ^10} {: ^8} {: ^8} {: ^8} {: ^8} {: ^8}'.format('Frequency', 'Pos. Width', 'Neg. Width', 'Duty Cycle', 'Freq. Dev', 'Count'))
        
        data = []
        cnt = 0
        try:

            while (True):
                cnt += 1
                data.append(awg.measureFreqCntrAll())

                if (False):
                    print("Freq: {}Hz  PW: {}S  NW: {}S  Duty: {}%  Freq. Dev. {}ppm".format(
                        data[-1]['FRQ'],
                        data[-1]['PW'],
                        data[-1]['NW'],
                        data[-1]['DUTY'],
                        data[-1]['FRQDEV']))

                if (True):
                    print('     {:>10.6}Hz {:>8.4}s {:>8.4}s {:>8.4}% {:>8.4}ppm {:>12}'.format(
                        awg.polish(data[-1]['FRQ']),
                        awg.polish(data[-1]['PW']),
                        awg.polish(data[-1]['NW']),
                        # no units or polish needed below here
                        data[-1]['DUTY'],
                        data[-1]['FRQDEV'], 
                        cnt   
                        ))

                # The Counter data does not seem to update very fast (like 2-3 seconds), so sleep a little
                sleep(1.0)

        except KeyboardInterrupt:
            #@@@#print(data)

            print()
            print('Mean {:>10.6}Hz {:>8.4}s {:>8.4}s {:>8.4}% {:>8.4}ppm'.format(
                awg.polish(mean([x['FRQ'] for x in data])),
                awg.polish(mean([x['PW'] for x in data])),
                awg.polish(mean([x['NW'] for x in data])),
                # no units or polish needed below here
                mean([x['DUTY'] for x in data]),
                mean([x['FRQDEV'] for x in data])
            ))
            print('Min  {:>10.6}Hz {:>8.4}s {:>8.4}s {:>8.4}% {:>8.4}ppm'.format(
                awg.polish(min([x['FRQ'] for x in data])),
                awg.polish(min([x['PW'] for x in data])),
                awg.polish(min([x['NW'] for x in data])),
                # no units or polish needed below here
                min([x['DUTY'] for x in data]),
                min([x['FRQDEV'] for x in data])
            ))
            print('Max  {:>10.6}Hz {:>8.4}s {:>8.4}s {:>8.4}% {:>8.4}ppm'.format(
                awg.polish(max([x['FRQ'] for x in data])),
                awg.polish(max([x['PW'] for x in data])),
                awg.polish(max([x['NW'] for x in data])),
                # no units or polish needed below here
                max([x['DUTY'] for x in data]),
                max([x['FRQDEV'] for x in data])
            ))
            print('Sdev {:>10.6}Hz {:>8.4}s {:>8.4}s {:>8.4}% {:>8.4}ppm'.format(
                awg.polish(stdev([x['FRQ'] for x in data])),
                awg.polish(stdev([x['PW'] for x in data])),
                awg.polish(stdev([x['NW'] for x in data])),
                # no units or polish needed below here
                stdev([x['DUTY'] for x in data]),
                stdev([x['FRQDEV'] for x in data])
            ))
            print()
            
                
    if (args.setup_save):
        fn = handleFilename(args.setup_save, 'jstp')
        
        dataLen = awg.setupSave(fn)
        print("AWG Setup bytes saved: {} to '{}'".format(dataLen,fn) )

    if (args.setup_load):
        fn = handleFilename(args.setup_load, 'jstp', unique=False, timestamp=False)

        if(not os.path.isfile(fn)):
            print('INVALID filename "{}" - must be exact and exist!'.format(fn))
        else:
            dataLen = awg.setupLoad(fn)
            print("AWG Setup bytes loaded: {} from '{}'".format(dataLen,fn) )

    print('Done')
    awg.close()


if __name__ == '__main__':
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# Copyright (c) 2018,2019,2020,2021,2022 Stephen Goadhouse <sgoadhouse@virginia.edu>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

#-------------------------------------------------------------------------------
#  Control of Arbitrary Waveform Generators with PyVISA and SCPI command set. This started as
#  specific code for the Siglent SDG6022X AWG and
#  has been made more generic to be used with other Siglent AWGs.
#  The hope is that these commands in this package are generic enough to be
#  used with other brands but may need to make this an Siglent specific
#  package in the future if find that not to be true.
#-------------------------------------------------------------------------------

# For future Python3 compatibility:
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from time import sleep
import sys
import os

try:
    from .scpi import SCPI
except Exception:
    sys.path.append(os.getcwd())
    from scpi import SCPI

import json
from collections import OrderedDict
from quantiphy import Quantity
import pyvisa as visa

class AWG(SCPI):
    """Base class for controlling and accessing an Arbitrary Waveform Generator with PyVISA and SCPI commands"""

    def __init__(self, resource, maxChannel=1, wait=0,
                 cmds = None,
                 cmd_prefix = '',
                 read_strip = '\n',
                 read_termination = '',
                 write_termination = '\n',
                 encoding = 'ascii'):
        """Init the class with the instruments resource string

        resource   - resource string or VISA descriptor, like TCPIP0::172.16.2.13::INSTR
        maxChannel - number of channels
        wait       - float that gives the default number of seconds to wait after sending each command
        cmds       - a dictionary of cmds to overload the main cmd dictionary
        cmd_prefix - optional command prefix (ie. some instruments require a ':' prefix)
        read_strip        - optional read_strip parameter used to strip any returned termination characters
        read_termination  - optional read_termination parameter to pass to open_resource()
        write_termination - optional write_termination parameter to pass to open_resource()
        encoding          - optional encoding to use when writing and reading data
                            (see https://docs.python.org/3/library/codecs.html#standard-encodings)
        """

        # "Overload" _SCPICmdTbl[] in parent with these commands.
        #
        # This is local to the __init__() function because it is used
        # to update the master _SCPICmdTbl[] and is no longer needed
        # after __init__() executes.
        _AWGCmdTbl = {

            # From Siglent SDG series - first {} is channel name, second {} is the value
            'setWaveType':                   '{}:BSWV WVTP,{}',
            'setFrequency':                  '{}:BSWV FRQ,{}',
            'setPeriod':                     '{}:BSWV PERI,{}',
            'setAmplitude':                  '{}:BSWV AMP,{}',
            'setAmplitudeVrms':              '{}:BSWV AMPVRMS,{}',
            'setAmplitudedBm':               '{}:BSWV AMPDBM,{}',
            'setOffset':                     '{}:BSWV OFST,{}',
            'setRampSymmetry':               '{}:BSWV SYM,{}',
            'setDutyCycle':                  '{}:BSWV DUTY,{}',
            'setPhase':                      '{}:BSWV PHSE,{}',
            'setNoiseStdDev':                '{}:BSWV STDEV,{}',
            'setNoiseMean':                  '{}:BSWV MEAN,{}',
            'setPulseWidth':                 '{}:BSWV WIDTH,{}',
            'setPulseRise':                  '{}:BSWV RISE,{}',
            'setPulseFall':                  '{}:BSWV FALL,{}',
            'setPulseDelay':                 '{}:BSWV DLY,{}',
            'setHighLevel':                  '{}:BSWV HLEV,{}',
            'setLowLevel':                   '{}:BSWV LLEV,{}',
            'setNoiseBandwidth':             '{}:BSWV BANDWIDTH,{}',
            'setNoiseBandState':             '{}:BSWV BANDSTATE,{}',
            'setPRBSBitLength':              '{}:BSWV LENGTH,{:d}',
            'setPRBSEdge':                   '{}:BSWV EDGE,{}',
            'setPRBSDiffState':              '{}:BSWV DIFFSTATE,{}',
            'setPRBSBitRate':                '{}:BSWV BITRATE,{}',
            'setPRBSLogicLevel':             '{}:BSWV LOGICLEVEL,{}',

            #'setWaveParameters':             '{}:BSWV {}',
            #'queryWaveParameters':           '{}:BSWV?',

            'setOutputLoad':                 '{}:OUTP LOAD,{}',
            'setOutputPolarity':             '{}:OUTP PLRT,{}',
            'setSignalPolarity':             '{}:INVT {}',                
            
            # More standard SCPI command - here really as a test - siglent.py will override
            'setVoltageProtection':          'SOURce:VOLTage:PROTection:LEVel {}',
            'queryVoltageProtection':        'SOURce:VOLTage:PROTection:LEVel?',

            # Frequency Counter setup and measurements
            'setFreqCntrOn':                 'FCNT STATE,ON',
            'setFreqCntrOff':                'FCNT STATE,OFF',
            'setFreqCntrReference':          'FCNT REFQ,{1}',
            'setFreqCntrTrigLevel':          'FCNT TRG,{1}',
            'setFreqCntrCoupleAC':           'FCNT MODE,AC',
            'setFreqCntrCoupleDC':           'FCNT MODE,DC',
            'setFreqCntrHfrOn':              'FCNT HFR,ON',
            'setFreqCntrHfrOff':             'FCNT HFR,OFF',
            'measureFreqCntr':               'FCNT?',

            # Handle Arbitrary Waveforms
            'setArbWaveData':                '{}:WVDT {}',
            'setArbWaveByIndex':             '{}:ARWV INDEX,{}',
            'setArbWaveByName':              '{}:ARWV NAME,{}',
            'setArbModeDDS':                 '{}:SRATE MODE,DDS',
            'setArbMode':                    '{}:SRATE {}',
            'queryArbWaveData':              'WVDT? USER,{1}',
            
        }
        
        if cmds is not None:
            # update _AWGCmdTbl[] with commands from child
            _AWGCmdTbl.update(cmds)

        # NOTE: maxChannel is accessible in this package via parent as: self._max_chan
        super(AWG, self).__init__(resource, max_chan=maxChannel, wait=wait,
                                  cmds=_AWGCmdTbl,
                                  cmd_prefix=cmd_prefix,
                                  read_strip=read_strip,
                                  read_termination=read_termination,
                                  write_termination=write_termination,
                                  encoding=encoding
        )

        # Return list of valid analog channel strings.
        self._chanAnaValidList = [str(x) for x in range(1,self._max_chan+1)]

        # list of ALL valid channel strings.
        #
        # NOTE: Currently, only valid values are a numerical string for
        # the analog channels, POD1 for digital channels 0-7 or POD2 for
        # digital channels 8-15
        self._chanAllValidList = self._chanAnaValidList + [str(x) for x in ['POD1','POD2']]

        # Give the Series a name
        self._series = 'GENERIC'

        # By default do not check errors. Child classes can turn this on once they open()        
        self._defaultCheckErrors = False 

        # Set the list of valid Wave Type strings - these can be overriden by child objects as needed
        self._validWaveTypes = ["SINE"]

        # Set the list of valid logic level strings - these can be overriden by child objects as needed
        self._validLogicLevels = ["TTL", "CMOS"]
        
    @property
    def chanAnaValidList(self):
        return self._chanAnaValidList

    @property
    def chanAllValidList(self):
        return self._chanAllValidList

    @property
    def series(self):
        # Use this so can branch activities based on awg series name
        return self._series
    
    def getBestClass(self):
        """Open the connection and based on ID strings, create an object that
        is the most appropriate child class for this
        AWG. Returns the new object.

        """

        ## Make sure calling SCPI open which gets the ID String and parses it and then close
        superduper = super()
        superduper.open()
        superduper.close()

        # Default is to return myself as no child class that fits better than this
        newobj = self
        if (self._IDNmanu.upper().startswith('SIGLENT')):
            # An Siglent AWG
            try:
                from .siglent import Siglent
            except Exception:
                sys.path.append(os.getcwd())
                from siglent import Siglent
                    
            # Generic Siglent AWG
            newobj = Siglent(self._resource, wait=self._wait)

        return newobj
    
    def setOutputLoad(self, load, channel=None, wait=None, checkErrors=None):
        """Set the output load, 50 ohms or hi-impedance (HiZ), for the channel
        
           load           - a boolean that if True will set to 50 ohms, else HiZ
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        if (load):
            loadStr = '50'
        else:
            loadStr = 'HZ'
            
        self._setGenericParameter(loadStr, self._Cmd('setOutputLoad'), channel, wait, checkErrors)
        
    def setOutputInverted(self, invert, channel=None, wait=None, checkErrors=None):
        """Set the output inverted or not for the channel
        
           invert         - a boolean that if True will set output inverted, else normal
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        if (invert):
            invertStr = 'INVT'
        else:
            invertStr = 'NOR'
            
        self._setGenericParameter(invertStr, self._Cmd('setOutputPolarity'), channel, wait, checkErrors)
        
    def setSignalInverted(self, invert, channel=None, wait=None, checkErrors=None):
        """Set the signal inverted or not for the channel. This does the exact
           same action as setOutputInverted() but uses a different command.
        
           invert         - a boolean that if True will set signal inverted, else normal
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1

        """ 
            
        self._setGenericParameter(self._bool2onORoff(invert), self._Cmd('setSignalPolarity'), channel, wait, checkErrors)
        
    def setWaveType(self, wavetype, channel=None, wait=None, checkErrors=None):
        """Set the wave type for the channel
        
           wavetype  - desired wave type as a string
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        wavetype = wavetype.upper() # make sure parameter is uppercase for comparison
        if not wavetype in self._validWaveTypes:
            raise ValueError('Requested wave type "' + wavetype + '" is not valid!')
                             
        self._setGenericParameter(wavetype, self._Cmd('setWaveType'), channel, wait, checkErrors)

    def setFrequency(self, frequency, channel=None, wait=None, checkErrors=None):
        """Set the frequency for the channel
        
           frequency - desired frequency value as a floating point in Hz
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(frequency, self._Cmd('setFrequency'), channel, wait, checkErrors)

    def setPeriod(self, period, channel=None, wait=None, checkErrors=None):
        """Set the period for the channel
        
           period    - desired period as a floating point value in seconds
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(period, self._Cmd('setPeriod'), channel, wait, checkErrors)

    def setAmplitude(self, amplitude, channel=None, wait=None, checkErrors=None):
        """Set the voltage amplitude for the channel
        
           amplitude - desired voltage amplitude as a floating point value in Volts peak-to-peak
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(amplitude, self._Cmd('setAmplitude'), channel, wait, checkErrors)

    def setAmplitudeVrms(self, amplitude, channel=None, wait=None, checkErrors=None):
        """Set the voltage amplitude for the channel in units Vrm
        
           amplitude - desired voltage amplitude as a floating point value in Volts RMS
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(amplitude, self._Cmd('setAmplitudeVrms'), channel, wait, checkErrors)

    def setAmplitudedBm(self, amplitude, channel=None, wait=None, checkErrors=None):
        """Set the voltage amplitude for the channel in units dBm
        
           amplitude - desired voltage amplitude as a floating point value in dBm
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(amplitude, self._Cmd('setAmplitudedBm'), channel, wait, checkErrors)

    def setOffset(self, offset, channel=None, wait=None, checkErrors=None):
        """Set the voltage offset for the channel
        
           offset    - desired voltage offset as a floating point value in Volts
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(offset, self._Cmd('setOffset'), channel, wait, checkErrors)
        
    def setRampSymmetry(self, rampsymmetry, channel=None, wait=None, checkErrors=None):
        """Set the ramp symmetry for the channel - only valid for wave type RAMP
        
           rampsymmetry - desired ramp symmetry value as a floating point in % (0-100)
           wait         - number of seconds to wait after sending command
           channel      - number of the channel starting at 1
        """

        self._setGenericParameter(rampsymmetry, self._Cmd('setRampSymmetry'), channel, wait, checkErrors)

    def setDutyCycle(self, duty, channel=None, wait=None, checkErrors=None):
        """Set the duty cycle for the channel
        
           duty      - desired duty as a floating point in % (0-100)
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(duty, self._Cmd('setDutyCycle'), channel, wait, checkErrors)
        
    def setPhase(self, phase, channel=None, wait=None, checkErrors=None):
        """Set the phase for the channel
        
           phase     - desired phase as a floating point in degrees (0-360)
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(phase%360, self._Cmd('setPhase'), channel, wait, checkErrors)

    def setNoiseStdDev(self, noiseStdDev, channel=None, wait=None, checkErrors=None):
        """Set the noise standard deviation for the channel
        
           noiseStdDev    - desired voltage standard deviation for NOISE wave type as a floating point value in Volts
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        self._setGenericParameter(noiseStdDev, self._Cmd('setNoiseStdDev'), channel, wait, checkErrors)
        
    def setNoiseMean(self, noiseMean, channel=None, wait=None, checkErrors=None):
        """Set the noise mean for the channel
        
           noiseMean      - desired voltage mean for NOISE wave type as a floating point value in Volts
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        self._setGenericParameter(noiseMean, self._Cmd('setNoiseMean'), channel, wait, checkErrors)
        
    def setPulseWidth(self, pulseWidth, channel=None, wait=None, checkErrors=None):
        """Set the pulse width time for the channel
        
           pulseWidth - desired pulse width time for PULSE wave type as a floating point in seconds
           wait       - number of seconds to wait after sending command
           channel    - number of the channel starting at 1
        """

        self._setGenericParameter(pulseWidth, self._Cmd('setPulseWidth'), channel, wait, checkErrors)

    def setPulseRise(self, rise, channel=None, wait=None, checkErrors=None):
        """Set the rise time for the channel
        
           rise      - desired rise time for PULSE wave type as a floating point in seconds
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(rise, self._Cmd('setPulseRise'), channel, wait, checkErrors)

    def setPulseFall(self, fall, channel=None, wait=None, checkErrors=None):
        """Set the fall time for the channel
        
           fall      - desired fall time for PULSE wave type as a floating point in seconds
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(fall, self._Cmd('setPulseFall'), channel, wait, checkErrors)
        
    def setPulseDelay(self, delay, channel=None, wait=None, checkErrors=None):
        """Set the pulse delay time for the channel
        
           delay     - desired pulse delay time for PULSE wave type as a floating point in seconds
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(delay, self._Cmd('setPulseDelay'), channel, wait, checkErrors)

    def setHighLevel(self, highLevel, channel=None, wait=None, checkErrors=None):
        """Set the high voltage level for the channel
        
           highLevel      - desired voltage high level as a floating point value in Volts
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        self._setGenericParameter(highLevel, self._Cmd('setHighLevel'), channel, wait, checkErrors)
        
    def setLowLevel(self, lowLevel, channel=None, wait=None, checkErrors=None):
        """Set the low voltage level for the channel
        
           lowLevel       - desired voltage low level as a floating point value in Volts
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        self._setGenericParameter(lowLevel, self._Cmd('setLowLevel'), channel, wait, checkErrors)
        
    def setNoiseBandwidth(self, bandwidth, channel=None, wait=None, checkErrors=None):
        """Set the frequency bandwidth for NOISE wave type for the channel
        
           bandwidth      - desired frequency bandwidth as a floating point value in Hertz
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        self._setGenericParameter(bandwidth, self._Cmd('setNoiseBandwidth'), channel, wait, checkErrors)
        # turn ON bandwidth setting since user desires it to be different
        self._setGenericParameter("ON", self._Cmd('setNoiseBandState'), channel, wait, checkErrors)
        
    def setNoiseBandwidthOff(self, channel=None, wait=None, checkErrors=None):
        """Turn off the bandwidth setting for NOISE wave type for the channel
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        # turn OFF bandwidth setting
        self._setGenericParameter("OFF", self._Cmd('setNoiseBandState'), channel, wait, checkErrors)
        
    def setPRBSBitLength(self, bitlength, channel=None, wait=None, checkErrors=None):
        """Set the bit length for PRBS wave type for the channel
        
           bitlength      - desired bitlength as an integer value (3-32)
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        if (bitlength < 3) or (bitlength > 32):
            raise ValueError('PRBS bit length must be an integer 3-32 inclusive. Attempted to set to {}'.format(bitlength))
        
        self._setGenericParameter(int(bitlength), self._Cmd('setPRBSBitLength'), channel, wait, checkErrors)
        
    def setPRBSEdge(self, edge, channel=None, wait=None, checkErrors=None):
        """Set the rise/fall time for the channel
        
           edge      - desired rise/fall time for PRBS wave type as a floating point in seconds
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(edge, self._Cmd('setPRBSEdge'), channel, wait, checkErrors)

    def setPRBSDiffState(self, diff, channel=None, wait=None, checkErrors=None):
        """Set the differential state for the channel with PRBS wave type
        
           diff      - differential state for PRBS wave type as a boolean
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(self._bool2onORoff(diff), self._Cmd('setPRBSDiffState'), channel, wait, checkErrors)

    def setPRBSBitRate(self, bitrate, channel=None, wait=None, checkErrors=None):
        """Set the bit rate for PRBS wave type for the channel
        
           bitrate        - desired bit rate as bits per second
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        self._setGenericParameter(bitrate, self._Cmd('setPRBSBitRate'), channel, wait, checkErrors)
        
    def setPRBSLogicLevel(self, logicLevel, channel=None, wait=None, checkErrors=None):
        """Set the logic level for PRBS wave type for the channel
        
           logicLevel     - name of desired logic level
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        logicLevel = logicLevel.upper() # make sure parameter is uppercase for comparison
        if not logicLevel in self._validLogicLevels:
            raise ValueError('Requested logic level "' + logicLevel + '" is not valid!')
        
        self._setGenericParameter(logicLevel, self._Cmd('setPRBSLogicLevel'), channel, wait, checkErrors)

    def setVoltageProtection(self, ovp, delay=None, channel=None, wait=None):
        """Set the over-voltage protection value for the channel
        
           ovp     - desired over-voltage value as a floating point number
           delay   - desired voltage protection delay time in seconds [IGNORED HERE]
           wait    - number of seconds to wait after sending command
           channel - number of the channel starting at 1
        """

        self._setGenericParameter(ovp, self._Cmd('setVoltageProtection'), channel, wait)
                
    def queryVoltageProtection(self, channel=None):
        """query the over-voltage protection value for the channel
        
           channel - number of the channel starting at 1
        """

        return self._queryGenericParameter(self._Cmd('queryVoltageProtection'), channel)

    # =========================================================
    # Frequency Counter
    #
    # This is specific to the Siglent SDG series. Will likely need
    # to rearrange code if add another AWG.
    # =========================================================    
    def setFreqCntrOn(self, channel=None, wait=None, checkErrors=None):
        """Turn On/enable the frequency counter function.
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 
        
        self._setGenericParameter(0, self._Cmd('setFreqCntrOn'), channel, wait, checkErrors)

    def setFreqCntrOff(self, channel=None, wait=None, checkErrors=None):
        """Turn Off/Disable the frequency counter function.
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 
        
        self._setGenericParameter(0, self._Cmd('setFreqCntrOff'), channel, wait, checkErrors)

    def setFreqCntrReference(self, refFreq, channel=None, wait=None, checkErrors=None):
        """Set the reference frequency for the frequency counter to computer frequency deviation
        
           refFreq   - desired reference frequency value as a floating point in Hz
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(refFreq, self._Cmd('setFreqCntrReference'), channel, wait, checkErrors)

    def setFreqCntrTrigLevel(self, trigLevel, channel=None, wait=None, checkErrors=None):
        """Set the trigger voltage level for the frequency counter
        
           trigLevel - desired trigger voltage level as a floating point in Volts
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """

        self._setGenericParameter(trigLevel, self._Cmd('setFreqCntrTrigLevel'), channel, wait, checkErrors)
    
    def setFreqCntrCoupleDC(self, channel=None, wait=None, checkErrors=None):
        """Set input coupling mode of the frequency counter to DC
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 
        
        self._setGenericParameter(0, self._Cmd('setFreqCntrCoupleDC'), channel, wait, checkErrors)

    def setFreqCntrCoupleAC(self, channel=None, wait=None, checkErrors=None):
        """Set input coupling mode of the frequency counter to AC
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 
        
        self._setGenericParameter(0, self._Cmd('setFreqCntrCoupleAC'), channel, wait, checkErrors)

    def setFreqCntrHfrOn(self, channel=None, wait=None, checkErrors=None):
        """Enable the High Frequency Rejection (i.e. low pass filter) for the frequency counter function.
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 
        
        self._setGenericParameter(0, self._Cmd('setFreqCntrHfrOn'), channel, wait, checkErrors)

    def setFreqCntrHfrOff(self, channel=None, wait=None, checkErrors=None):
        """Disable the High Frequency Rejection (i.e. low pass filter) for the frequency counter function.
        
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 
        
        self._setGenericParameter(0, self._Cmd('setFreqCntrHfrOff'), channel, wait, checkErrors)

    def isFreqCntrOn(self, channel=None):
        """Return true if Frequency Counter is ON, else false
        
           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        # NOTE: Frequency Counter has no channel so this is ignored although default gets updated
        if channel is not None:
            self.channel = channel

        fcnt = self._queryFreqCntr(channel)
            
        return self._onORoff_1OR0_yesORno(fcnt['STATE'])
    
    def measureFreqCntrFrequency(self, channel=None):
        """query and return the measured frequency of the Counter input
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)

        # be sure to strip off the unit string before converting to float()
        return float(fcnt['FRQ'].upper().rstrip('HZ'))
        
    def measureFreqCntrPosWidth(self, channel=None):
        """query and return the measured positive width of the Counter input
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)
        
        # be sure to strip off the unit string before converting to float()
        return float(fcnt['PW'].upper().rstrip('S'))
        
    def measureFreqCntrNegWidth(self, channel=None):
        """query and return the measured negative width of the Counter input
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)
        
        # be sure to strip off the unit string before converting to float()
        return float(fcnt['NW'].upper().rstrip('S'))
        
    def measureFreqCntrDutyCycle(self, channel=None):
        """query and return the measured duty cycle of the Counter input
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)

        # do not expect a unit suffix
        return float(fcnt['DUTY'])
        
    def measureFreqCntrFrequencyDeviation(self, channel=None):
        """query and return the measured frequency deviation of the Counter input
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)
        
        # be sure to strip off the unit string before converting to float()
        return float(fcnt['FRQDEV'].upper().rstrip('PM'))
        
    def measureFreqCntrAll(self, channel=None):
        """query and return ALL measured values from Frequency Counter in a dictionary
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)
        param = ["FRQ", "PW", "NW", "DUTY", "FRQDEV"]
        unitStrip = ["HZ", "S", "S", "", "PM"]

        # zip param and unitStrip together so that iterator puts the
        # next param in x[0] and next unitStrip in x[1].
        # Therefore, param and unitStrip must be the same length
        vals = {}
        for x in zip(param,unitStrip):
            vals[x[0]] = float(fcnt[x[0]].upper().rstrip(x[1])) 
        
        return vals
        
    def queryFreqCntrReference(self, channel=None):
        """query and return the set reference frequency
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)
        
        # be sure to strip off the unit string before converting to float()
        return float(fcnt['REFQ'].upper().rstrip('HZ'))
        
    def queryFreqCntrTrigLevel(self, channel=None):
        """query and return the set trigger level
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)
        
        # be sure to strip off the unit string before converting to float()
        return float(fcnt['TRG'].upper().rstrip('V'))

    def isFreqCntrCoupleDC(self, channel=None):
        """query the coupling mode - return True if DC, else False (if AC)
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)

        resp = fcnt['MODE'].upper()
        return (resp == "DC")

    def isFreqCntrHfrON(self, channel=None):
        """query the high frequency rejection state (i.e. low pass filter)
        
           channel - number of the channel starting at 1
        """

        fcnt = self._queryFreqCntr(channel)

        return self._onORoff_1OR0_yesORno(fcnt['HFR'])

    ###############################################################################
    # Arbitrary Waveform Functions
    ###############################################################################

    def _setArbWaveBin(self, name, freq, amp, offset, bindata, phase=0, channel=None, wait=None, checkErrors=None):
        """Load a User Defined wave data to select for a channel

           name           - Name to use to store and reference this arbitrary waveform
           freq           - Frequency for this waveform (how fast the sequence restarts)
                            The step period for each data point is 1/(freq*(# of data pts))
           amp            - Amplitude (Vpp) for this waveform
           offset         - Offset voltage for this waveform
           phase          - Phase in degrees for this waveform (phase with relation to some internal clock - not completely sure)
           bindata        - Binary data as a Python byte array arranged as 16-bit, little endian words
        
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        What the output does between the data points depends on how
        the Sample Rate is configured using the SRATE command (in
        Siglent). If TARB, or TrueArb, and interpolation set to HOLD,
        then the output stays the same voltage level just before
        transitioning to the next data point. If TARB and Linear
        interpolation, then there is a linear interpolation between
        the points. This also happens if SRATE mode is DDS. Other TARB
        and Interpolation settings create slightly different outputs.

        """ 

        # Create OrderedDict of parameter and values
        params = OrderedDict()
        params['WVNM'] = name
        params['FREQ'] = freq
        params['AMPL'] = amp
        params['OFST'] = offset
        params['PHASE'] = phase
        params['WAVEDATA'] = bindata.decode(self._encoding)
                       
        self._setGenericParameters(params, self._Cmd('setArbWaveData'), channel, wait, checkErrors)

    def setArbWaveData(self, name, freq, amp, offset, data, phase=0, channel=None, wait=None, checkErrors=None):
        """Load a User Defined wave data to select for a channel

           name           - Name to use to store and reference this arbitrary waveform
           freq           - Frequency for this waveform (how fast the sequence restarts)
                            The step period for each data point is 1/(freq*(# of data pts))
           amp            - Amplitude (Vpp) for this waveform
           offset         - Offset voltage for this waveform
           phase          - Phase in degrees for this waveform (phase with relation to some internal clock - not completely sure)
           data           - An array of data for the waveform. The data is treated as 16-bit signed integer values.
                            If 0, the output is at the offset voltage.
                            If 0x7fff or 32767, the output is at the (offset + amp/2) voltage.
                            If 0x8000 or -32768, the output is at the (offset - amp/2) voltage.
                            All other values scale linearly from these touchpoints.
        
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        What the output does between the data points depends on how
        the Sample Rate is configured using the SRATE command (in
        Siglent). If TARB, or TrueArb, and interpolation set to HOLD,
        then the output stays the same voltage level just before
        transitioning to the next data point. If TARB and Linear
        interpolation, then there is a linear interpolation between
        the points. This also happens if SRATE mode is DDS. Other TARB
        and Interpolation settings create slightly different outputs.

        """ 

        # Create a byte string from integer data. Convert each entry
        # in data[] as a 16-bit, little endian 2-byte string which all
        # get concatenated together
        bindata = b''.join([x.to_bytes(2,'little') for x in data])

        self._setArbWaveBin(name, freq, amp, offset, bindata, phase, channel, wait, checkErrors)

    def setArbWaveDataFromFile(self, filename, name, freq, amp, offset, phase=0, channel=None, wait=None, checkErrors=None):
        """Load a User Defined wave data to select for a channel

           filename       - A filename with binary data to be loaded into a User-defined arbitrary wave form
           name           - Name to use to store and reference this arbitrary waveform
           freq           - Frequency for this waveform (how fast the sequence restarts)
                            The step period for each data point is 1/(freq*(# of data pts))
           amp            - Amplitude (Vpp) for this waveform
           offset         - Offset voltage for this waveform
           phase          - Phase in degrees for this waveform (phase with relation to some internal clock - not completely sure)
        
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        What the output does between the data points depends on how
        the Sample Rate is configured using the SRATE command (in
        Siglent). If TARB, or TrueArb, and interpolation set to HOLD,
        then the output stays the same voltage level just before
        transitioning to the next data point. If TARB and Linear
        interpolation, then there is a linear interpolation between
        the points. This also happens if SRATE mode is DDS. Other TARB
        and Interpolation settings create slightly different outputs.

        """ 

        with open(filename, "rb") as binary_file:
            bindata = binary_file.read()

        self._setArbWaveBin(name, freq, amp, offset, bindata, phase, channel, wait, checkErrors)
            
        # return the number of bytes written
        return len(bindata)
        

    def setArbWaveByIndex(self, waveIndex, channel=None, wait=None, checkErrors=None):
        """Select the Arbitrary Wave for the channel

           waveIndex      - A number from the published wave tables for the particular AWG - not checked for errors
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

           Select the Arbitrary Wave to use by Index. Follow this by setting the wave type to ARB
        """ 

        self._setGenericParameter(waveIndex, self._Cmd('setArbWaveByIndex'), channel, wait, checkErrors)
        self._setGenericParameter('ARB', self._Cmd('setWaveType'), channel, wait, checkErrors)

    def setArbWaveByName(self, waveName, channel=None, wait=None, checkErrors=None):
        """Select the Arbitrary Wave for the channel

           waveName       - A name from the published wave tables for the particular AWG - can also be the name of a user entered wave
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

           Select the Arbitrary Wave to use by Index. Follow this by setting the wave type to ARB
        """ 

        self._setGenericParameter(waveName, self._Cmd('setArbWaveByName'), channel, wait, checkErrors)
        self._setGenericParameter('ARB', self._Cmd('setWaveType'), channel, wait, checkErrors)

    def setArbModeDDS(self, channel=None, wait=None, checkErrors=None):
        """Set the Arbitrary Wave mode to DDS for the channel.
           This is a linear interpolation between samples and repeats the samples per frequency setting.
           This does not take sample rate or interpolation.
           Not completely sure of difference between this and TrueARB / Linear
           other than TrueARB / Linear allows for a Sample Rate.

           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        self._setGenericParameter(0, self._Cmd('setArbModeDDS'), channel, wait, checkErrors)

    def setArbModeLinear(self, sampleRate, channel=None, wait=None, checkErrors=None):
        """Set the Arbitrary Wave mode to TrueArb (TARB) and interpolation to linear for the channel.
           This is a linear interpolation between samples and outputs a new sample per sampleRate

           sampleRate     - Output is updated with a new sample per this rate in units Sa/S (samples per second)
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors
        """ 

        # Create OrderedDict of parameter and values
        params = OrderedDict()
        params['MODE'] = 'TARB'
        params['INTER'] = 'LINE'
        params['VALUE'] = sampleRate
                       
        self._setGenericParameters(params, self._Cmd('setArbMode'), channel, wait, checkErrors)

    def setArbModeHold(self, sampleRate, channel=None, wait=None, checkErrors=None):
        """Set the Arbitrary Wave mode to TrueArb (TARB) and interpolation to zero-order hold for the channel.
        
           Zero-order hold means to stay at the sample value until the
           next sample. There is a voltage ramping between samples
           which does not appear to have a way to be set.

           sampleRate     - Output is updated with a new sample per this rate in units Sa/S (samples per second)
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        # Create OrderedDict of parameter and values
        params = OrderedDict()
        params['MODE'] = 'TARB'
        params['INTER'] = 'HOLD'
        params['VALUE'] = sampleRate
                       
        self._setGenericParameters(params, self._Cmd('setArbMode'), channel, wait, checkErrors)

    def setArbModeSinc(self, sampleRate, channel=None, wait=None, checkErrors=None):
        """Set the Arbitrary Wave mode to TrueArb (TARB) and interpolation to sinc for the channel.
        
           Uses a Sinc function to interpolate between samples.
        
           sampleRate     - Output is updated with a new sample per this rate in units Sa/S (samples per second)
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        # Create OrderedDict of parameter and values
        params = OrderedDict()
        params['MODE'] = 'TARB'
        params['INTER'] = 'SINC'
        params['VALUE'] = sampleRate
                       
        self._setGenericParameters(params, self._Cmd('setArbMode'), channel, wait, checkErrors)

    def setArbModeSinc13(self, sampleRate, channel=None, wait=None, checkErrors=None):
        """Set the Arbitrary Wave mode to TrueArb (TARB) and interpolation to sinc13 for the channel.
        
           Uses a Sinc13 function to interpolate between samples.
        
           sampleRate     - Output is updated with a new sample per this rate in units Sa/S (samples per second)
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        # Create OrderedDict of parameter and values
        params = OrderedDict()
        params['MODE'] = 'TARB'
        params['INTER'] = 'SINC13'
        params['VALUE'] = sampleRate
                       
        self._setGenericParameters(params, self._Cmd('setArbMode'), channel, wait, checkErrors)

    def setArbModeSinc27(self, sampleRate, channel=None, wait=None, checkErrors=None):
        """Set the Arbitrary Wave mode to TrueArb (TARB) and interpolation to sinc27 for the channel.
        
           Uses a Sinc27 function to interpolate between samples.
        
           sampleRate     - Output is updated with a new sample per this rate in units Sa/S (samples per second)
           channel        - number of the channel starting at 1
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        # Create OrderedDict of parameter and values
        params = OrderedDict()
        params['MODE'] = 'TARB'
        params['INTER'] = 'SINC27'
        params['VALUE'] = sampleRate
                       
        self._setGenericParameters(params, self._Cmd('setArbMode'), channel, wait, checkErrors)

    def queryArbWaveNamesUser(self, channel=None, wait=None, checkErrors=None):
        """Query and return the list of wave data name for user defined waves

           channel        - number of the channel starting at 1 (ignored but included since in other calls)
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel

        cmd = 'STL'
        ret = self._instQuery('{}?{}'.format(cmd, ' USER'))
        words = ret.split(' ')  # split by words with spaces

        if(len(words) != 2 or words[0].strip() != cmd):
            raise RuntimeError('Unexpected return string for {}? command: "' + ret + '"'.format(cmd))

        params = words[1].split(',')

        if(params[0] != 'WVNM'):
            raise RuntimeError('Unexpected return string for {}? command: "' + ret + '"'.format(cmd))
        
        return params[1:]

    def _queryArbWaveBin(self, name, channel=None, wait=None, checkErrors=None):
        """Query a User Defined wave data and return data as a byte string 

           name           - Name to use to store and reference this arbitrary waveform (case sensitive)
        
           channel        - number of the channel starting at 1 (ignored but included since in other calls)
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
        
        str = self._Cmd('queryArbWaveData').format(self.channelStr(self.channel), name)

        try:
            ret = self._instQuery(str)
        except visa.VisaIOError as err:
            if (err.error_code == visa.constants.StatusCode.error_timeout):
                raise RuntimeError('VISA Timeout while querying wave data. Most likely, "{}" is not a valid wave name.\nUse queryArbWaveNamesUser() to find the valid user names.'.format(name))
            else:
                raise RuntimeError("Exited because of VISA IO Error: {}".format(err))


        p1 = 'WVNM, '
        filename = ret.find(p1) + len(p1)
        # Determine where the binary data begins in the return string
        data_pos = ret.find("WAVEDATA,") + len("WAVEDATA,")
        # Split the returned parameters up until the data using ' '
        # Unlike every other command, there are spaces after each ',' so need to deal with that.
        retParams = ret[0:data_pos]
        retList = retParams.split(' ')
        # remove trailing ','
        retList = [x.rstrip(',') for x in retList]
        if(retList[0] != 'WVDT' or retList[3] != 'WVNM' or retList[4] != name or retList[5] != 'LENGTH'):
            raise RuntimeError('Unexpected return string for WVDT? command: "' + retParams + '"')

        # get the byte length
        byteLen = int(retList[6].rstrip('B'))
        
        # get the byte data
        byteData = ret[data_pos:].encode(self._encoding)

        # Check byte length
        if(len(byteData) != byteLen):
            raise RuntimeError('Unexpected number of wave data bytes for WVDT? command. Exp. {}  Act. {}'.format(byteLen, len(byteData)))

        return byteData

    def queryArbWaveData(self, name, channel=None, wait=None, checkErrors=None):
        """Query a User Defined wave data 

           name           - Name to use to store and reference this arbitrary waveform (case sensitive)
        
           channel        - number of the channel starting at 1 (ignored but included since in other calls)
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

           Reads the wave data for wave named with 'name'. Returns as a list of 16-bit integers.
        
        """ 

        byteData = self._queryArbWaveBin(name, channel, wait, checkErrors)

        it = iter(byteData)
        wordData = [(y<<8)+x for x,y in zip(it,it)]

        return wordData
        
    def queryArbWaveDataToFile(self, filename, name, channel=None, wait=None, checkErrors=None):
        """Query a User Defined wave data and saves to a binary file.

           filename       - Name of the binary file to store the binary wave data
           name           - Name to use to store and reference this arbitrary waveform (case sensitive)
        
           channel        - number of the channel starting at 1 (ignored but included since in other calls)
           wait           - number of seconds to wait after sending command
           checkErrors    - If True, Check for SCPI Errors, else don't bother
                            if None, use self._defaultCheckErrors

        """ 

        byteData = self._queryArbWaveBin(name, channel, wait, checkErrors)

        with open(filename, "wb") as binary_file:
            binary_file.write(byteData)

        # return the number of bytes written
        return len(byteData)
        
    ###############################################################################    
    
    # =========================================================
    # Currently only specific to Siglent SDG series
    # =========================================================
    def setupSave(self, filename):
        """ Fetch the AWG setup and save to a JSON formatted file with given filename. """

        # Save the default channel since it will change as we step through channels
        defChan = self.channel

        setup = []
        for chan in range(1,self._max_chan+1):
            cmds = {}
            
            # Get the OUTP? query response
            outp = self._queryOutput(chan)
            # Create an iterator but skip the first parameter which is ON or OFF
            it = iter(outp[1:])
            # Convert the other parameters into a dictionary
            cmds['OUTP'] = dict(zip(it,it))

            # Get BSWV? query as a dictionary
            cmds['BSWV'] = self._queryWaveParameters(chan)

            if cmds['BSWV']['WVTP'] == 'ARB':
                # For Arbitrary Waves, also need which wave is selected and its sample rate/mode
                #
                # Get ARWV? query as a dictionary
                cmds['ARWV'] = self._queryArbWaveType(chan)
                # Get SRATE? query as a dictionary
                cmds['SRATE'] = self._queryArbWaveMode(chan)
                

            setup.append(cmds)

        # restore the default channel
        self.channel = defChan
            
        # open file to save within
        f = open(filename, "w")

        # write as a JSON formatted string
        json.dump(setup,f,sort_keys=True)

        sz = f.tell()
        
        # close the file
        f.close()

        # Return number of bytes saved to file
        return sz

    # =========================================================
    # Currently only specific to Siglent SDG series
    # =========================================================
    def setupLoad(self, filename, wait=None):
        """ Restore the AWG setup from the JSON formatted file with given filename. """

        # Load setup from file.
        f = open(filename, "r")

        setup = json.load(f)
        
        sz = f.tell()
        
        # close the file
        f.close()

        ## Reset the AWG and setup the OUTP and BSWV parameters from setup[]
        self.reset()               

        if (len(setup) > self._max_chan):
            raise RuntimeError('Attempting to load a setup with {} channels into a device with only {} channels'.format(len(setup),self._max_chan))
        
        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait
        
        # Save the default channel since it will change as we step through channels
        defChan = self.channel

        # make sure output is OFF on all channel before we go changing a bunch of parameters
        self.outputOffAll()

        # init diffstate.
        diffstate = False
        
        for idx,chanSetup in enumerate(setup):
            # chan is 1-based so need to convert from 0-based idx
            chan = idx+1

            # If diffstate is found to be enabled, skip any even
            # channels since they should be setup with the first one            
            if diffstate and chan%2 == 0:
                continue
            
            cmdList = list(chanSetup.keys())
            # make sure all upper case for comparisons
            cmdList = [x.upper() for x in cmdList]
            if 'OUTP' in cmdList:
                # Make sure that OUTP is the first cmd because if
                # output is 50 ohms or inverted, these should be set
                # before setting th BSWV parameters since they will
                # get interpreted differently.
                cmdList.insert(0, cmdList.pop(cmdList.index('OUTP')))
            elif 'OUTPUT' in cmdList:
                # command could be long form so check for OUTPUT
                cmdList.insert(0, cmdList.pop(cmdList.index('OUTPUT')))
            
            for cmd in cmdList:
                # Get list of keys
                params = list(chanSetup[cmd].keys())

                # make sure all upper case for comparisons
                params = [x.upper() for x in params]

                if cmd == 'ARWV' or cmd == 'ARBWAVE':
                    # If cmd is ARWV or its long form, need to check
                    # for a NAME parameter. If it is user defined file
                    # name, must strip off the .bin extension because
                    # although we are given the parameter with the
                    # extension, the ARB gets unhappy when we try to
                    # give it back with extension.
                    if 'NAME' in params:
                        chanSetup['ARWV']['NAME'] = chanSetup['ARWV']['NAME'].rstrip('.bin')
                        chanSetup['ARWV']['NAME'] = chanSetup['ARWV']['NAME'].rstrip('.BIN') # in case ext is uppercase
                        
                if cmd == 'BSWV' or cmd == 'BASIC_WAVE':
                    # If cmd is BSWV, must write DIFFSTATE, if it
                    # exists, third so that any output voltage
                    # parameters get put on both channels.
                    #
                    # NOTE: inserting at the front so that following
                    # commands can insert their parameters at the
                    # front and be before this one
                    if 'DIFFSTATE' in params:
                        params.insert(0, params.pop(params.index('DIFFSTATE')))
                        # save diffstate so will skip even channels if ON
                        diffstate = self._onORoff_1OR0_yesORno(chanSetup['BSWV']['DIFFSTATE'])

                    # If cmd is BSWV, must write FRQ frequency or PERI
                    # period second or else the other parameters like
                    # DLY may be invalid
                    #
                    # NOTE: inserting at the front so that following
                    # commands can insert their parameters at the
                    # front and be before this one                    
                    if 'PERI' in params:
                        params.insert(0, params.pop(params.index('PERI')))
                    if 'FRQ' in params:
                        params.insert(0, params.pop(params.index('FRQ')))
                        
                    # If cmd is BSWV, must write WVTP wave type first
                    # so that AWG will allow the parameters specific
                    # to that type.
                    try:
                        # Remove 'WVTP' so can move it to the front of the list
                        params.remove('WVTP')
                    except ValueError:
                        # remove() raises ValueError if 'WVTP' is not in params
                        raise RuntimeError('No WVTP parameter saved for BSWV command - inconceivable!')
                    # Put 'WVTP' at the front of the list
                    params.insert(0,'WVTP') 
                        
                    # It has been found that if there is both a FRQ and
                    # PERI parameters that there is a rounding error with
                    # the PERI value and the set frequency is off. So in
                    # this case, remove the PERI parameter.
                    if ('FRQ' in params) and ('PERI' in params):
                        params.remove('PERI')

                    # There are a lot of amplitude parameters that
                    # could cause rounding errors although have not
                    # seen it be a problem. Just in case, remove the
                    # extras and leave only AMP and OFST which are
                    # guessed to be fundamental. If find this to be a
                    # problem, then remove this clause or determine
                    # how to fix it.
                    if 'AMP' in params:
                        if 'AMPDBM' in params:
                            params.remove('AMPDBM')
                        if 'AMPVRMS' in params:
                            params.remove('AMPVRMS')

                        # If 'AMP' and 'OFST', do not need HLEV and LLEV
                        if ('OFST' in params) and ('HLEV' in params):
                            params.remove('HLEV')
                        if ('OFST' in params) and ('LLEV' in params):
                            params.remove('LLEV')
                            
                        
                # Write all cmd parameters.
                for param in params:
                    str = '{}:{} {},{}'.format(self.channelStr(chan),cmd,param,chanSetup[cmd][param])
                    print(str) #@@@#
                    self._instWrite(str)
                    sleep(wait)

        # restore the default channel
        self.channel = defChan

        # Since CH2 is setup last, if that is not the defChan, then
        # perform a virtual key press of the channel button to make
        # CH1 be on the screen
        #
        # OK - tried this but the virtual key presses take too long
        #if (self.channel == 1):
        #    self._instWrite('VKEY VALUE,KB_CHANNEL,STATE,1')
        
        # Return number of bytes saved to file
        return sz


    ## This is a dictionary of measurement labels with their units. It
    ## is blank here and it is expected that this get defined by child
    ## classes.
    _measureTbl = { }
    

    def polish(self, value, measure=None):
        """ Using the QuantiPhy package, return a value that is in appropriate Si units.

        If value is >= self.OverRange, then return the invalid string instead of a Quantity().

        If the measure string is None, then no units are used by the SI suffix is.

        """

        if (value >= self.OverRange):
            pol = '------'
        else:
            try:
                pol = Quantity(value, self._measureTbl[measure][0])
            except KeyError:
                # If measure is None or does not exist
                pol = Quantity(value)

        return pol


if __name__ == '__main__':
    ## NOTE: This example code currently only works on Arbitrary Waveform Generators
    ## fully defined by the child classes. Currently that is just
    ## Siglent AWGs.

    from time import sleep    
    import argparse
    parser = argparse.ArgumentParser(description='Access and control an AWG')
    parser.add_argument('chan', nargs='?', type=int, help='Channel to access/control (starts at 1)', default=1)
    args = parser.parse_args()

    from os import environ
    resource = environ.get('AWG_IP', 'TCPIP0::172.16.2.13::INSTR')
    instr = AWG(resource)

    ## Help to use with other models. Likely will not need these three
    ## lines once get IDN strings from all known AWG that I
    ## want to use
    instr.open()
    print('Potential SCPI Device: ' + instr.idn() + '\n')
    instr.close()
    
    ## Upgrade Object to best match based on IDN string
    instr = instr.getBestClass()
    
    ## Open this object and work with it
    instr.open()

    print('Using SCPI Device:     ' + instr.idn() + ' of series: ' + instr.series + '\n')

    #@@@@#print(instr._instQuery("SYSTem:ERRor? String", checkErrors=False))
    #@@@@#print(instr._instWrite("C1:MDWV GM"))
    
    # set the channel (can pass channel to each method or just set it
    # once and it becomes the default for all following calls)
    instr.channel = str(args.chan)

    # Enable output of channel, if it is not already enabled
    #if not instr.isOutputOn():
    #    instr.outputOn()

    #if instr.isOutputOn():
    #    instr.outputOff()

    #instr.outputOnAll()
    #sleep(2)
    #instr.outputOffAll()

    if instr.isOutputHiZ(instr.channel):
        print("Output High Impedance")
    else:
        print("Output 50 ohm load")
    
    instr.beeperOn()

    #@@@#print(instr._instQuery("C1:BSWV?"))
    #@@@#instr._inst.write("C1:BSWV AMP,2.4")
    #@@@#print(instr._instQuery("SYST:ERR?"))
    #@@@#print(instr._instQuery("SYST:ERR?"))

    #@@@#sleep(5)

    if (True):
        # return to default parameters
        instr.reset()               

        instr.setWaveType('SINE')
        instr.setFrequency(34.4590897823e3)
        instr.setVoltageProtection(3.3)
        instr.setOffset(1.6)
        #@@@#instr.setAmplitudeVrms(1.0)
        instr.setAmplitudedBm(0.8)
        instr.setPhase(0.45)

        print("Voltage Protection is set to maximum: {}".format(instr.queryVoltageProtection()))

        # turn on the channel
        instr.outputOn()

        sleep(2)
    
        # turn off the channel
        instr.outputOff()

    if (False) :
        # Test Frequency Counter functions
        #
        # First, provide a signal to count
        instr.setWaveType('SINE', 2)
        instr.setFrequency(40.0789e6)
        instr.setVoltageProtection(4.8) # input is max 5 Vpp
        instr.setOffset(0)
        instr.setAmplitude(2.4)
        instr.setOutputLoad(False)
        
        # turn on the channel
        instr.outputOn()
        
        instr.setFreqCntrOn()
        instr.setFreqCntrReference(40e6)
        instr.setFreqCntrTrigLevel(1.0)
        instr.setFreqCntrCoupleDC()
        instr.setFreqCntrHfrOff()

        print("\nFrequency Counter is {}".format(instr.isFreqCntrOn() and "ON" or "OFF"))
        print("Ref Freq: {}Hz  Trig Lvl: {}V  Couple: {}  HFR: {}".format(
            instr.queryFreqCntrReference(), instr.queryFreqCntrTrigLevel(),
            instr.isFreqCntrCoupleDC() and "DC" or "AC", instr.isFreqCntrHfrON() and "ON" or "OFF"))
        
        for t in range(1,10):
            print("Freq: {}Hz  PW: {}S  NW: {}S  Duty: {}%  Freq. Dev. {}ppm".format(
                instr.measureFreqCntrFrequency(),
                instr.measureFreqCntrPosWidth(),
                instr.measureFreqCntrNegWidth(),
                instr.measureFreqCntrDutyCycle(),
                instr.measureFreqCntrFrequencyDeviation()))
        
        sleep(5)

        instr.setFreqCntrTrigLevel(0)
        instr.setFreqCntrCoupleAC()
        instr.setFreqCntrHfrOn()

        print("\nFrequency Counter is {}".format(instr.isFreqCntrOn() and "ON" or "OFF"))
        print("Ref Freq: {}Hz  Trig Lvl: {}V  Couple: {}  HFR: {}".format(
            instr.queryFreqCntrReference(), instr.queryFreqCntrTrigLevel(),
            instr.isFreqCntrCoupleDC() and "DC" or "AC", instr.isFreqCntrHfrON() and "ON" or "OFF"))
        
        for t in range(1,10):
            print("Freq: {}Hz  PW: {}S  NW: {}S  Duty: {}%  Freq. Dev. {}ppm".format(
                instr.measureFreqCntrFrequency(),
                instr.measureFreqCntrPosWidth(),
                instr.measureFreqCntrNegWidth(),
                instr.measureFreqCntrDutyCycle(),
                instr.measureFreqCntrFrequencyDeviation()))
        
        sleep(5)

        instr.setFreqCntrOff()        
        print("\nFrequency Counter is {}".format(instr.isFreqCntrOn() and "ON" or "OFF"))
        
    if (False) :
        # return to default parameters
        instr.reset()               

        # Setup a different basic wave output
        instr.setWaveType('NOISE')
        instr.setNoiseMean(1.9)
        instr.setNoiseStdDev(0.2)
        instr.setNoiseBandwidth(22)
        
        # turn on the channel
        instr.outputOn()

        sleep(4)

        instr.setNoiseBandwidthOff()

        sleep(5)

        # turn off the channel
        instr.outputOff()
        

    if (False) :
        # return to default parameters
        instr.reset()               

        # Setup a different basic wave output
        instr.setWaveType('PRBS')
        instr.setHighLevel(3.3)
        instr.setLowLevel(0)        
        instr.setPRBSBitLength(12)
        instr.setPRBSEdge(50e-9)
        #@@@#instr.setPRBSDiffState(1)
        instr.setPRBSBitRate(2.2e3)
        instr.setPRBSLogicLevel("LVTTL_LVCMOS")
        
        # turn on the channel
        instr.outputOn()

        sleep(4)
        
        # turn off the channel
        instr.outputOff()

    if (False):
        # return to default parameters
        instr.reset()               
        instr.setVoltageProtection(3.2)

        # reset the default channel
        instr.channel = str(args.chan)
    
        # Setup a different basic wave output
        instr.setWaveType('PULSE')
        instr.setFrequency(1e3)
        instr.setOutputInverted(False)
        instr.setOutputLoad(False)
        #@@@#instr.setOffset(1.6)
        #@@@#instr.setAmplitude(3.2)
        instr.setHighLevel(3.1)
        instr.setLowLevel(0.2)
        instr.setPulseWidth(50e-9)
        instr.setPulseRise(2e-9)
        instr.setPulseFall(2e-9)
        instr.setOutputInverted(True)

        #@@@#print(instr._queryWaveParameters())
    
        # turn on the channel
        instr.outputOn()

        instr.setupSave("testSetup.json")
    
        sleep(5)

        # Setup a different basic wave output (NOTE: output is ON)
        instr.setWaveType('PRBS')
        instr.setHighLevel(2.2)
        instr.setLowLevel(0)        
        instr.setPRBSBitLength(3)
        
        sleep(2)

        print()
        # Now Load setup as a test (with Output still on (should go off)
        instr.setupLoad("testSetup.json", wait=0.0)

    if (False):
        # return to default parameters
        instr.reset()               

        # load data as user arb wav enamed "my_stair"
        data = [0, 0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000, 0x7000, 0x7fff]
        instr.setArbWaveData("my_stair", 1e6, 2, 1.0, data)
        # select this new user waveform
        instr.setArbWaveByName("my_stair")
        # Set Mode to zero-order hold and 1MSa/s so each sample last 1 us
        instr.setArbModeHold(1e6)

        instr.setupSave("testSetup_arb.json")
        
        # turn on the channel
        instr.outputOn()
        
        sleep(5)

        # Try Linear interpolation
        instr.setArbModeLinear(1.1e6)

        sleep(5)

        # Try Sinc interpolation
        instr.setArbModeSinc(1.2e6)

        sleep(5)
        
        # Try Sinc13 interpolation
        instr.setArbModeSinc13(1.3e6)

        sleep(5)
        
        # Try Sinc27 interpolation
        instr.setArbModeSinc27(1.4e6)

        sleep(5)
        
        # Try DDS Mode
        instr.setArbModeDDS()

        sleep(5)

        # turn off the channel
        instr.outputOff()
        
        # Setup a different basic wave output (NOTE: output is ON)
        instr.setWaveType('RAMP')
        instr.setFrequency(2e6)
        instr.setHighLevel(3.3)
        instr.setLowLevel(0.2)        
        instr.outputOn()
        
        sleep(3)

        # Now Load setup as a test (with Output still on (should go off)
        instr.setupLoad("testSetup_arb.json", wait=0.0)
        instr.outputOn()

        sleep(5)
        
        # turn off the channel
        instr.outputOff()
        

    if (True):
        # return to default parameters
        instr.reset()               

        print(instr.queryArbWaveNamesUser())
        
        waveData = instr.queryArbWaveData("my_stair")
        print([hex(x) for x in waveData])

        name = "my_stair"
        fn = "my_stair.bin"
        writeLen = instr.queryArbWaveDataToFile(fn,name)
        print("Wrote {} bytes of wave data by the name '{}' to '{}'".format(writeLen,name,fn))

        name = "my_stair2"
        fn = "my_stair.bin"
        readLen = instr.setArbWaveDataFromFile(fn,name,1e6,2.0,1.0)
        print("Read {} bytes of wave data from '{}' and sent as wave name '{}'".format(readLen,fn,name))
        
        
    sleep(5)
    
    # turn off the channel
    instr.outputOff()

    # return to LOCAL mode
    instr.setLocal()

    instr.close()

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

import sys
import os

try:
    from .scpi import SCPI
except Exception:
    sys.path.append(os.getcwd())
    from scpi import SCPI

from quantiphy import Quantity
import numpy as np
import csv

class AWG(SCPI):
    """Base class for controlling and accessing an Arbitrary Waveform Generator with PyVISA and SCPI commands"""

    # "Overload" _SCPICmdTbl[] in parent with these comands
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
        
    }
    
    def __init__(self, resource, maxChannel=1, wait=0,
                 cmds = None,
                 cmd_prefix = '',
                 read_strip = '\n',
                 read_termination = '',
                 write_termination = '\n'):
        """Init the class with the instruments resource string

        resource   - resource string or VISA descriptor, like TCPIP0::172.16.2.13::INSTR
        maxChannel - number of channels
        wait       - float that gives the default number of seconds to wait after sending each command
        cmds       - a dictionary of cmds to overload the main cmd dictionary
        cmd_prefix - optional command prefix (ie. some instruments require a ':' prefix)
        read_strip        - optional read_strip parameter used to strip any returned termination characters
        read_termination  - optional read_termination parameter to pass to open_resource()
        write_termination - optional write_termination parameter to pass to open_resource()
        """

        if cmds is not None:
            # update _AWGCmdTbl[] with commands from child
            self._AWGCmdTbl.update(cmds)
        
        # NOTE: maxChannel is accessible in this package via parent as: self._max_chan
        super(AWG, self).__init__(resource, max_chan=maxChannel, wait=wait,
                                  cmds=self._AWGCmdTbl,
                                  cmd_prefix=cmd_prefix,
                                  read_strip=read_strip,
                                  read_termination=read_termination,
                                  write_termination=write_termination
        )

        # No longer need _AWGCmdTbl[] so delete it
        del AWG._AWGCmdTbl
        
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
    
    # =========================================================
    # Based on the save oscilloscope setup example from the MSO-X 3000 Programming
    # Guide and modified to work within this class ...
    # =========================================================
    def setupSave(self, filename):
        """ Fetch the oscilloscope setup and save to a file with given filename. """

        oscopeSetup = self._instQueryIEEEBlock("SYSTem:SETup?")

        # Save setup to file.
        f = open(filename, "wb")
        f.write(oscopeSetup)
        f.close()

        #print('Oscilloscope Setup bytes saved: {} to "{}"'.format(len(oscopeSetup),filename))

        # Return number of bytes saved to file
        return len(oscopeSetup)

    # =========================================================
    # Based on the loading a previous setup example from the MSO-X 3000 Programming
    # Guide and modified to work within this class ...
    # =========================================================
    def setupLoad(self, filename):
        """ Restore the oscilloscope setup from file with given filename. """

        # Load setup from file.
        f = open(filename, "rb")
        oscopeSetup = f.read()
        f.close()

        #print('Oscilloscope Setup bytes loaded: {} from "{}"'.format(len(oscopeSetup),filename))

        self._instWriteIEEEBlock("SYSTem:SETup ", oscopeSetup)

        # Return number of bytes saved to file
        return len(oscopeSetup)


    def waveform(self, filename, channel=None, points=None):
        """Download waveform data of a selected channel into a csv file.

        NOTE: This is a LEGACY function to prevent breaking API but it
        is deprecated so use above waveform functions instead.

        NOTE: Now that newer oscilloscopes have very large data
        downloads, csv file format is not a good format for storing
        because the files are so large that the convenience of csv
        files has diminishing returns. They are too large for Excel to
        load and are only useful from a scripting system like Python
        or MATLAB or Root. See waveformSaveNPZ() for a better option.

        filename - base filename to store the data

        channel  - channel, as string, to be measured - set to None to use the default channel

        points   - number of points to capture - if None, captures all available points
                   for newer devices, the captured points are centered around the center of the display

        """

        # Acquire the data (also sets self.channel)
        (x, y, header, meta) = self.waveformData(channel, points)

        # Save to CSV file
        return self.waveformSaveCSV(filename, x, y, header)
    
    
    def waveformSaveCSV(self, filename, x, y, header=None, meta=None):
        """
        filename - base filename to store the data

        x        - time data to write in first column

        y        - vertical data: expected to be a list of columns to write and can be any number of columns

        header   - a list of header strings, one for each column of data - set to None for no header

        meta     - a list of meta data for waveform data - optional and not used by this function - only here to be like other waveformSave functions

        """

        nLength = len(x)

        print('Writing data to CSV file. Please wait...')
        
        # Save waveform data values to CSV file.
        # Determine iterator
        if (nLength == len(y)):
            # Simply single column of y data
            it = zip(x,y)
        else:
            # Multiple columns in y, so break them out
            it = zip(x,*y)
            
        # Open file for output. Only output x & y for simplicity. User
        # will have to copy paste the meta data printed to the
        # terminal
        myFile = open(filename, 'w')
        with myFile:
            writer = csv.writer(myFile, dialect='excel', quoting=csv.QUOTE_NONNUMERIC)
            if header is not None:
                writer.writerow(header)
                
            writer.writerows(it)
                    
        # return number of entries written
        return nLength

    
    def waveformSaveNPZ(self, filename, x, y, header=None, meta=None):
        """
        filename - base filename to store the data

        x        - time data to write in first column

        y        - vertical data: expected to be a list of columns to write and can be any number of columns

        header   - a list of header strings, one for each column of data - set to None for no header

        meta     - a list of meta data for waveform data

        A NPZ file is an uncompressed zip file of the arrays x, y and optionally header and meta if supplied. 
        To load and use the data from python:

        import numpy as np
        header=None
        meta=None
        with np.load(filename) as data:
            x = data['x']
            y = data['y']
            if 'header' in data.files:
                header = data['header']
            if 'meta' in data.files:
                meta = data['meta']

        """

        nLength = len(x)

        print('Writing data to Numpy NPZ file. Please wait...')

        arrays = {'x': x, 'y': y}
        if (header is not None):
            arrays['header']=header
        if (meta is not None):
            arrays['meta']=meta
        np.savez(filename, **arrays)
        
        # return number of entries written
        return nLength

    
    ## This is a dictionary of measurement labels with their units. It
    ## is blank here and it is expected that this get defined by child
    ## classes.
    _measureTbl = { }
    

    def polish(self, value, measure=None):
        """ Using the QuantiPhy package, return a value that is in apparopriate Si units.

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
        
    # return to default parameters
    instr.reset()               

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

    sleep(5)
    
    # turn off the channel
    instr.outputOff()

    # return to default parameters
    #@@@#instr.reset()               
    
    # return to LOCAL mode
    instr.setLocal()

    instr.close()

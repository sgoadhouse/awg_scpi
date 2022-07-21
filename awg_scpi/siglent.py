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
#  Siglent specific SCPI commands
#-------------------------------------------------------------------------------

# For future Python3 compatibility:
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import os

try:
    from .awg import AWG
except Exception:
    sys.path.append(os.getcwd())
    from awg import AWG
    
from time import sleep
from datetime import datetime
from sys import version_info
import numpy as np
import pyvisa as visa

class Siglent(AWG):
    """Child class of AWG for controlling and accessing a Siglent Arbitrary Waveform Generator with PyVISA and SCPI commands"""

    def __init__(self, resource, maxChannel=2, wait=0):
        """Init the class with the instruments resource string

        resource   - resource string or VISA descriptor, like TCPIP0::172.16.2.13::INSTR
        maxChannel - number of channels of this AWG
        wait       - float that gives the default number of seconds to wait after sending each command
        """

        # "Overload" _SCPICmdTbl[] in parent with these comands
        #
        # This is local to the __init__() function because it is used
        # to update the master _SCPICmdTbl[] and is no longer needed
        # after __init__() executes.
        _SiglentCmdTbl = {
            'beeperOn':                      'BUZZ ON',
            'beeperOff':                     'BUZZ OFF',

            # first {} is channel name, second {} is the value
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
            
            'setVoltageProtection':          '{}:BSWV MAX_OUTPUT_AMP,{}',
        }

        # NOTE: maxChannel is accessible in this package via parent as: self._max_chan
        # NOTE: timeout can be the default if not writing more than about 30 MB wave data files.
        super(Siglent, self).__init__(resource, maxChannel, wait,
                                      cmds=_SiglentCmdTbl,
                                      cmd_prefix='',
                                      read_strip='\n',
                                      read_termination='',
                                      write_termination='\n',
                                      encoding='ISO-8859-1', # allow 0xff to be sent in arbitrary waveform data
                                      chunk_size = 40*1024,   # from Siglent manual
                                      timeout = 10000         # in case writing the largest possible wave data
        )

        # Return list of valid analog channel strings. These are numbers.
        self._chanAnaValidList = [str(x) for x in range(1,self._max_chan+1)]

        # list of ALL valid channel strings.
        #
        # NOTE: Currently, only valid common values are a
        # CHAN+numerical string for the analog channels
        self._chanAllValidList = [self.channelStr(x) for x in range(1,self._max_chan+1)]

        # Give the Series a name
        self._series = 'SIGLENT'

        # Set the highest version number used to determine if SCPI
        # firmware on AWG expects the LEGACY commands. Any
        # version number returned by the IDN string above this number
        # will use the modern, non-legacy commands.
        #
        # As far as what is known now, there is not a set of legacy
        # commands, so set to 0.00
        self._versionLegacy = 0.00

        # If SIGLENT, these are the acceptable Wave Types
        self._validWaveTypes = ['SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS']

        # If SIGLENT, these are the acceptable logic level strings
        self._validLogicLevels = ["TTL_CMOS", "LVTTL_LVCMOS", "ECL", "LVPECL", "LVDS"]
        
        # This will store annotation text if that feature is used
        self._annotationText = ''
        self._annotationColor = 'ch1' # default to Channel 1 color

        # BUG work around for Siglent SDG6022X and probably other SDG
        # series AWGs. Defining here in case a child class is created
        # for a different member of the series but it requires a
        # different chunk value to work. I discovered the magic values
        # by experimentation. It is not documented that I could find.
        #
        # If it is discovered that this bug is fixed, set to None        
        self._write_chunk_size = 1024
        #@@@#self._write_chunk_size = None

    def _versionUpdated(self):
        """Overload this function in child classes so can update parameters once the version number is known."""

        # Setup command to get system error status
        if (self._version > self._versionLegacy):
            self._errorCmd = ("SYSTem:ERRor?", ("0,", 0, 2))
        else:
            self._errorCmd = ("SYSTem:ERRor?", ("+0,", 0, 3))

        # Now that the _errorCmd has been set, can check for errors
        self._defaultCheckErrors = True
                    
    ## Overloading this method so can handle an apparent bug in the
    ## Siglent SDG series (at least the 6022X). If a write message is
    ## longer than 1024 bytes, the AWG accepts the following bytes in
    ## the message but treats subsequent write operations as
    ## additional data to go along with the first write. So if the
    ## message is > 1024, break up the writes into chunks. The chunks
    ## must be 1025 bytes long. If only 1024 bytes are written, then
    ## the subsequent write is considered a new command.
    def _visa_write_raw(self, message):
        # remaining bytes to write - starts as full message
        remLen = len(message)

        #@@@#print('VISA Write of {} bytes: {}'.format(remLen,message))
        
        if (self._write_chunk_size is None):
            # send full message in a single write and jump over all of
            # the computational code to be a little faster
            indexes = [(0,remLen)]
        else:
            # Determine the indexes needed to write in chunks of size self._write_chunk_size+1
            start = 0
            end = 0
            indexes = []
            while(True):
                start = end                
                if (self._write_chunk_size >= remLen):
                    # Can complete the write so break out of loop - this is the last loop
                    end += remLen
                    remLen = 0
                    indexes.append((start,end))
                    break
                else:
                    ## Add 1 to self._write_chunk_size because to make
                    ## the SDG think each write_raw() operation is
                    ## part of the same command, must go beyond the
                    ## chunk_size
                    end += self._write_chunk_size + 1
                    remLen -= self._write_chunk_size + 1
                    indexes.append((start,end)) 

        count = 0
        for idx in indexes:
            #@@@#print("Sending message[{}:{}]".format(*idx))
            count += self._saved_visa_write_raw(message[idx[0]:idx[1]])

        return count

    ## Overloading this method so can handle an apparent bug in the
    ## Siglent SDG series (at least the 6022X). If a write message is
    ## longer than 1024 bytes, the AWG accepts the following bytes in
    ## the message but treats subsequent writes as additional data to
    ## go along with the first write. So if > 1024, send all but the
    ## last byte and then send the last byte in a subsequent write
    ## message.
    ##
    ## WARNING: This DOES work with a 1906 bytes message, but do not
    ## know if there is some larger internal size limit where this no
    ## longer works so using the above version that breaks up the
    ## message in self._write_chunk_size+1 chunks.
    def _visa_write_raw_OLD(self, message):
        # remaining bytes to write - starts as full message
        remLen = len(message)

        #@@@#print('VISA Write of {} bytes: {}'.format(remLen,message))

        if (len(message) > self._write_chunk_size):
            count = self._saved_visa_write_raw(message[:-1])
            count += self._saved_visa_write_raw(message[-1:])
        else:
            count = self._saved_visa_write_raw(message)
            
        return count
        

    def channelStr(self, channel):
        """return the channel string given the channel number. If pass in None, return None."""

        try:
            return 'C{}'.format(int(channel))
        except TypeError:
            # If channel is None, will get this exception so simply return it
            return channel
        except ValueError:
            return self._chanStr(channel)

    def setLocal(self):
        # No Local/Remote setting
        pass
    
    def setRemote(self):
        # No Local/Remote setting
        pass
    
    def setRemoteLock(self):
        # No Local/Remote setting
        pass

    def _queryOutput(self, channel=None):
        """Perform an output query on the channel and return a list of the returned parameters

           order of returned parameters: ON|OFF,LOAD,50|HZ,PLRT,NOR|INVT

           channel        - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
        
        str = '{}:OUTP'.format(self.channelStr(self.channel))
        ret = self._instQuery(str+'?')
        words = ret.split(' ')  # split by words with spaces

        if(len(words) != 2 or words[0].strip() != str):
            raise RuntimeError('Unexpected return string for OUTP? command: "' + ret + '"')

        ## OUTP? unlike other commands return OFF/ON first and then a
        ## string of Parameter,Values. So remove the first param so
        ## can turn the remaning into a dictionary of Parameter/Values
        param = words[1].strip().split(',')
        isOn = (param[0].upper() == 'ON')
        param.pop(0)
        if(len(param)%2 != 0):
            raise RuntimeError('Expected an even number of returned comma seperated words from {}? command:\n   "' + ret + '"'.format(cmd))

        it = iter(param)
        ret_dict = dict(zip(it, it))

        #@@@#print('ret: "' + ret + '" words: ', words, " param: ", param)

        # return the comma seperate list of parameters as a Python list
        # ORDER: ON|OFF,LOAD,50|HZ,PLRT,NOR|INVT
        return (isOn, ret_dict)

    def isOutputHiZ(self, channel=None):
        """Return true if the output of channel is set for high impedance, else false

           channel - number of the channel starting at 1
        """

        (isOn,outParam) = self._queryOutput(channel)
        
        return (outParam['LOAD'].upper() == "HZ")

    def isOutput50(self, channel=None):
        """Return true if the output of channel is set for 50 ohm load, else false

           channel - number of the channel starting at 1
        """

        (isOn,outParam) = self._queryOutput(channel)
        
        return (outParam['LOAD'] == "50")

    def isOutputInverted(self, channel=None):
        """Return true if the output of channel is inverted, else false

           channel - number of the channel starting at 1
        """

        (isOn,outParam) = self._queryOutput(channel)
        
        return (outParam['PLRT'].upper() == "INVT")

    def isOutputOn(self, channel=None):
        """Return true if the output of channel is ON, else false

           channel - number of the channel starting at 1
        """

        # The first parameter is ON for output on and OFF for output off
        return self._queryOutput(channel)[0]

    def outputOn(self, channel=None, wait=None):
        """Turn on the output for channel

           wait    - number of seconds to wait after sending command
           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel

        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait

        str = '{}:OUTP ON'.format(self.channelStr(self.channel))
        self._instWrite(str)
        sleep(wait)

    def outputOff(self, channel=None, wait=None):
        """Turn off the output for channel

           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel

        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait

        str = '{}:OUTP OFF'.format(self.channelStr(self.channel))
        self._instWrite(str)
        sleep(wait)

    def outputOnAll(self, wait=None):
        """Turn on the output for ALL channels

        """

        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait

        for chan in range(1,self._max_chan+1):
            str = '{}:OUTP ON'.format(self.channelStr(chan))
            self._instWrite(str)

        sleep(wait)

    def outputOffAll(self, wait=None):
        """Turn off the output for ALL channels

        """

        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait
        
        for chan in range(1,self._max_chan+1):
            str = '{}:OUTP OFF'.format(self.channelStr(chan))
            self._instWrite(str)

        sleep(wait)             # give some time for PS to respond

    # ===========================================================================
    # Query Arbitrary Wave Type and create a dictionary from the response
    # ===========================================================================        
    def _queryGenericParameters(self, cmd, channel=None):
        """Perform a generic query of a command which is expected to
           return the cmd name followed by a list of parameters. Return
           those parameters in a dictionary.

           cmd            - command string to use for setting the parameter
           channel        - number of the channel starting at 1

        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
        
        str = '{}:{}'.format(self.channelStr(self.channel), cmd)
        ret = self._instQuery(str+'?')
        words = ret.split(' ')  # split by words with spaces

        if(len(words) != 2 or words[0].strip() != str):
            raise RuntimeError('Unexpected return string for {}? command: "' + ret + '"'.format(cmd))

        # Convert the comma seperated list of parameters as a Python dictionary.
        # do NOT uppercase parameter values because with wave file names, case is significant.
        #@@@#param = words[1].strip().upper().split(',')
        param = words[1].strip().split(',')
        if(len(param)%2 != 0):
            raise RuntimeError('Expected an even number of returned comma seperated words from {}? command:\n   "' + ret + '"'.format(cmd))

        it = iter(param)
        ret_dict = dict(zip(it, it))

        #@@@#print('ret: "' + ret + '" words: ', words, " param: ", param, " ret_dict: ", ret_dict)
        
        return ret_dict

    # ===========================================================================
    # Query Basic Wave parameters and create a dictionary from the response
    # ===========================================================================        
    def _queryWaveParameters(self, channel=None):
        """Perform an basic wave query on the channel and return a dictionary of the returned parameters

           expected returned parameters: WVTP,SINE,FRQ,100HZ,PERI,0.01S,AMP,2V,OFST,0V,HLEV,1V,LLEV,-1V,PHSE,0

           channel        - number of the channel starting at 1
        """

        return self._queryGenericParameters('BSWV', channel)

    # ===========================================================================
    # Query Frequency Counter and return a dictionary from the response
    # ===========================================================================        
    def _queryFreqCntr(self, channel=None):
        """Perform a frequency counter query query on the channel and return a dictionary of the returned parameters

           expected returned parameters: STATE,FRQ,DUTY,REFQ,TRG,PW,NW,FRQDEV,MODE,HFR

           channel        - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel - however, SIGLENT Frequency Counter has no Channel so it is ignored
        if channel is not None:
            self.channel = channel
        
        str = 'FCNT'
        ret = self._instQuery(str+'?')
        words = ret.split(' ')  # split by words with spaces

        if(len(words) != 2 or words[0].strip() != str):
            raise RuntimeError('Unexpected return string for FCNT? command: "' + ret + '"')

        # Convert the comma seperated list of parameters as a Python dictionary.
        # do NOT uppercase parameter values because with wave file names, case is significant.
        #@@@#param = words[1].strip().upper().split(',')
        param = words[1].strip().split(',')
        if(len(param)%2 != 0):
            raise RuntimeError('Expected an even number of returned comma seperated words from FCNT? command:\n   "' + ret + '"')

        it = iter(param)
        ret_dict = dict(zip(it, it))

        #@@@#print('ret: "' + ret + '" words: ', words, " param: ", param, " ret_dict: ", ret_dict)
        
        return ret_dict

    # ===========================================================================
    # Query Arbitrary Wave Type and create a dictionary from the response
    # ===========================================================================        
    def _queryArbWaveType(self, channel=None):
        """Perform an arbitrary wave type query on the channel and return a dictionary of the returned parameters

           expected returned parameters: INDEX,2,NAME,StairUp

           channel        - number of the channel starting at 1
        """

        return self._queryGenericParameters('ARWV', channel)

    # ===========================================================================
    # Query Arbitrary Wave Type and create a dictionary from the response
    # ===========================================================================        
    def _queryArbWaveType(self, channel=None):
        """Perform an arbitrary wave type query on the channel and return a dictionary of the returned parameters

           expected returned parameters: INDEX,2,NAME,StairUp

           channel        - number of the channel starting at 1
        """

        return self._queryGenericParameters('ARWV', channel)

    # ===========================================================================
    # Query Arbitrary Wave Mode / Sample Rate and create a dictionary from the response
    # ===========================================================================        
    def _queryArbWaveMode(self, channel=None):
        """Perform an arbitrary wave mode query on the channel and return a dictionary of the returned parameters

           expected returned parameters: MODE,TARB,INTER,HOLD,VALUE,1000000

           channel        - number of the channel starting at 1
        """

        return self._queryGenericParameters('SRATE', channel)

    def queryOffset(self, channel=None, checkErrors=None):
        """Query the voltage offset for the channel
        
           channel   - number of the channel starting at 1
        """

        resp = self._queryWaveParameters(channel)

        # Return the value of OFST with unit, if it exists, removed and converted to a float
        return(float(resp["OFST"].replace("V","")))
    
    def _queryMaxOutputAmp(self, channel=None, checkErrors=None):
        """Query the maximum output voltage for the channel
        
           channel   - number of the channel starting at 1
        """

        resp = self._queryWaveParameters(channel)

        # Return the value of MAX_OUTPUT_AMP with unit, if it exists, removed and converted to a float
        return(float(resp["MAX_OUTPUT_AMP"].replace("V","")))
    
    # ===========================================================================
    # Help user with voltage output level when output is inverted - non-intuitive
    # ===========================================================================
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

        # now that have inverted the output, get the voltage offset and set it to -1* its current value.
        # Do this by querying the Offset and then passing to setOffset() which will handle the -1*
        offset = self.queryOffset(channel, checkErrors)
        self.setOffset(offset, channel, wait, checkErrors)
        
    def setSignalInverted(self, invert, channel=None, wait=None, checkErrors=None):
        """Set the signal inverted or not for the channel. This does the exact
           same action as setOutputInverted() but uses a different command.
        
           invert         - a boolean that if True will set signal inverted, else normal
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1

        """ 
            
        self._setGenericParameter(self._bool2onORoff(invert), self._Cmd('setSignalPolarity'), channel, wait, checkErrors)

        # now that have inverted the output, get the voltage offset and set it to -1* its current value.
        # Do this by querying the Offset and then passing to setOffset() which will handle the -1*
        offset = self.queryOffset(channel, checkErrors)
        self.setOffset(offset, channel, wait, checkErrors)
        
        
    def setOffset(self, offset, channel=None, wait=None, checkErrors=None):
        """Set the voltage offset for the channel
        
           offset    - desired voltage offset as a floating point value in Volts
           wait      - number of seconds to wait after sending command
           channel   - number of the channel starting at 1
        """


        # First check if output is currently set to be inverted. If
        # so, need to set offset to -1*offset so that offset
        # will be the actual offset with inverted output
        if self.isOutputInverted(channel):
            self._setGenericParameter(-1*offset, self._Cmd('setOffset'), channel, wait, checkErrors)
        else:
            self._setGenericParameter(offset, self._Cmd('setOffset'), channel, wait, checkErrors)
        
    def setHighLevel(self, highLevel, channel=None, wait=None, checkErrors=None):
        """Set the high voltage level for the channel
        
           highLevel      - desired voltage high level as a floating point value in Volts
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        # First check if output is currently set to be inverted. If
        # so, need to set Low Level to -1*highLevel so that highlevel
        # will be the actual high level with inverted output
        if self.isOutputInverted(channel):
            self._setGenericParameter(-1*highLevel, self._Cmd('setLowLevel'), channel, wait, checkErrors)
        else:
            self._setGenericParameter(highLevel, self._Cmd('setHighLevel'), channel, wait, checkErrors)

    def setLowLevel(self, lowLevel, channel=None, wait=None, checkErrors=None):
        """Set the low voltage level for the channel
        
           lowLevel       - desired voltage low level as a floating point value in Volts
           wait           - number of seconds to wait after sending command
           channel        - number of the channel starting at 1
        """ 

        # First check if output is currently set to be inverted. If
        # so, need to set High Level to -1*lowLevel so that lowlevel
        # will be the actual low level with inverted output
        if self.isOutputInverted(channel):
            self._setGenericParameter(-1*lowLevel, self._Cmd('setHighLevel'), channel, wait, checkErrors)
        else:
            self._setGenericParameter(lowLevel, self._Cmd('setLowLevel'), channel, wait, checkErrors)

    # =====================================================================================================
    # To query parameters, must go through _queryWaveParameters() but need to know which string to look for
    # =====================================================================================================
    def queryVoltageProtection(self, channel=None):
        """query the over-voltage protection value for the channel
        
           channel - number of the channel starting at 1
        """

        return self._queryMaxOutputAmp(channel)

            
    # =========================================================
    # Check for instrument errors:
    # =========================================================
    def checkInstErrors(self, commandStr):

        cmd = self._errorCmd[0]
        noerr = self._errorCmd[1]

        errors = False
        # No need to read more times that the size of the Error Queue
        for reads in range(0,self.ErrorQueue):
            try:
                # checkErrors=False prevents infinite recursion!
                #@@@#print('Q: {}'.format(cmd))
                error_string = self._instQuery(cmd, checkErrors=False)
            except visa.errors.VisaIOError as err:    
                print("Unexpected VisaIOError during checkInstErrors(): {}".format(err))
                errors = True # if unexpected response, then set as Error
                break
                    
            error_string = error_string.strip()  # remove trailing and leading whitespace
            if error_string: # If there is an error string value.
                if error_string.find(*noerr) == -1:
                    # Not "No error".
                    #
                    # However, for some unknown reason, the BSWV
                    # command, FCNT, OUTP, ARWV, SRATE & WVDT? commands ALWAYS returns -108
                    # error code so if see that, ignore
                    #
                    # FCNT has no channel name before it but the others do
                    if error_string.find("-108,", 0, 5) != -1:
                        cmdWords = commandStr.split(' ')
                        cmdParts = cmdWords[0].strip().lower().split(':')
                        if ((len(cmdParts) == 1 and
                             (cmdParts[0] == 'fcnt'
                              or cmdParts[0] == 'freqcounter'
                              or cmdParts[0] == 'vkey'
                              or cmdParts[0] == 'virtualkey'
                              or cmdParts[0] == 'wvdt?')) or
                            (len(cmdParts) == 2 and
                             (cmdParts[1] == 'bswv'
                              or cmdParts[1] == 'basic_wave'
                              or cmdParts[1] == 'outp'
                              or cmdParts[1] == 'output'
                              or cmdParts[1] == 'arwv'
                              or cmdParts[1] == 'arbwave'
                              or cmdParts[1] == 'srate'
                              or cmdParts[1] == 'samplerate'
                              or cmdParts[1] == 'wvdt')) or
                            (len(cmdParts) > 2 and
                             # Fo rsome reason, SPACES exist between return parameters - very ODD
                             (cmdParts[1] == 'wvdt'))):
                            break
                        
                    print("ERROR({:02d}): {}, command: '{}'".format(reads, error_string, commandStr))
                    errors = True           # indicate there was an error
                else: # "No error"
                    break

            else: # :SYSTem:ERRor? should always return string.
                print("ERROR: :SYSTem:ERRor? returned nothing, command: '{}'".format(commandStr))
                errors = True # if unexpected response, then set as Error
                break

        return errors           # indicate if there was an error

        


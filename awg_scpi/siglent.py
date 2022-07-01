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
import struct
import pyvisa as visa

class Siglent(AWG):
    """Child class of AWG for controlling and accessing a Siglent Arbitrary Waveform Generator with PyVISA and SCPI commands"""

    # "Overload" _SCPICmdTbl[] in parent with these comands
    _SiglentCmdTbl = {
        'beeperOn':                      'BUZZ ON',
        'beeperOff':                     'BUZZ OFF',

        # first {} is channel name, second {} is the value
        'setWaveType':                   '{}:BSWV WVTP,{}',
        'setFrequency':                  '{}:BSWV FRQ,{}',
        'setPeriod':                     '{}:BSWV PERI,{}',
        'setAmplitude':                  '{}:BSWV AMP,{}',
        'setOffset':                     '{}:BSWV OFST,{}',
        'setPhase':                      '{}:BSWV PHSE,{}',
        'setDutyCycle':                  '{}:BSWV DUTY,{}',
        'setRise':                       '{}:BSWV RISE,{}',
        'setFall':                       '{}:BSWV FALL,{}',
        'setDelay':                      '{}:BSWV DLY,{}',
        'setWaveParameters':             '{}:BSWV {}',
        'queryWaveParameters':           '{}:BSWV?',

        'measureVoltage':                'MEASure:VOLTage:DC?',
        'setVoltageProtection':          'SOURce:VOLTage:PROTection:LEVel {}',
        'setVoltageProtectionDelay':     'SOURce:VOLTage:PROTection:DELay {}',
        'queryVoltageProtection':        'SOURce:VOLTage:PROTection:LEVel?',
        'voltageProtectionOn':           'SOURce:VOLTage:PROTection:STATe ON',
        'voltageProtectionOff':          'SOURce:VOLTage:PROTection:STATe OFF',
        'isVoltageProtectionTripped':    'SOURce:VOLTage:PROTection:TRIPped?',
        'voltageProtectionClear':        'SOURce:VOLTage:PROTection:CLEar',
    }
    
    def __init__(self, resource, maxChannel=2, wait=0):
        """Init the class with the instruments resource string

        resource   - resource string or VISA descriptor, like TCPIP0::172.16.2.13::INSTR
        maxChannel - number of channels of this AWG
        wait       - float that gives the default number of seconds to wait after sending each command
        """
        # NOTE: maxChannel is accessible in this package via parent as: self._max_chan
        super(Siglent, self).__init__(resource, maxChannel, wait,
                                      cmds=self._SiglentCmdTbl,
                                      cmd_prefix='',
                                      read_strip='\n',
                                      read_termination='',
                                      write_termination='\n'
        )

        # No longer need _AWGCmdTbl[] so delete it
        del Siglent._SiglentCmdTbl

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
        
        # This will store annotation text if that feature is used
        self._annotationText = ''
        self._annotationColor = 'ch1' # default to Channel 1 color

    def _versionUpdated(self):
        """Overload this function in child classes so can update parameters once the version number is known."""

        # Setup command to get system error status
        if (self._version > self._versionLegacy):
            self._errorCmd = ("SYSTem:ERRor?", ("0,", 0, 2))
        else:
            self._errorCmd = ("SYSTem:ERRor?", ("+0,", 0, 3))

        # Now that the _errorCmd has been set, can check for errors
        self._defaultCheckErrors = True
                    

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
    
    def isOutputOn(self, channel=None):
        """Return true if the output of channel is ON, else false

           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel

        str = '{}:OUTP'.format(self.channelStr(self.channel))
        ret = self._instQuery(str+'?')
        words = ret.split(' ')  # split by words with spaces

        if(words[0].strip() != str):
            raise RuntimeError('Unexpected return string for OUTP? command: "' + ret + '"')

        param = words[1].strip().split(',')

        #@@@#print('ret: "' + ret + '" words: ', words, " param: ", param)
        
        return self._onORoff(param[0])

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
                    # command ALWAYS returns -108 error code so if see
                    # that, ignore
                    if error_string.find("-108,", 0, 5) != -1:
                        cmdWords = commandStr.split(' ')
                        cmdParts = cmdWords[0].strip().lower().split(':')
                        if (len(cmdParts) == 2 and (cmdParts[1] == 'bswv' or cmdParts[1] == 'basic_wave')):
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

        
    # =========================================================
    # Based on the Waveform data download example from the Keysight
    # Infiniium MXR/EXR-Series Oscilloscope Programmer's Guide and
    # modified to work within this class ...
    # =========================================================
    def _waveformDataNew(self, channel, points=None):
        """ Download the Waveform Data of a particular Channel and return it. """

        DEBUG = True
        
        # Download waveform data.
        # --------------------------------------------------------

        # Create array for meta data
        meta = []
        
        # Set the waveform source.
        self._instWrite("WAVeform:SOURce {}".format(self.channelStr(channel)))
        wav_source = self._instQuery("WAVeform:SOURce?")

        # Get the waveform view.
        wav_view = self._instQuery("WAVeform:VIEW?")
        
        # Choose the format of the data returned.
        if (channel.startswith('HIST')):
            # Histogram so request BINary forma
            self._instWrite("WAVeform:FORMat BINary")
        elif(channel == 'POD1' or channel == 'POD2'):
            # For POD1 and POD2, they really are only BYTE values
            # although WORD will work but the MSB will always be
            # 0. Setting this to BYTE here makes later code work out
            # by setting bits to 8 and npTyp to np.int8.
            self._instWrite("WAVeform:FORMat BYTE")
        else:
            # For analog data, WORD is the best and has the highest
            # accuracy (even better than FLOat). WORD works for most
            # of the other channel types as well.
            self._instWrite("WAVeform:FORMat WORD")
        
        # Make sure byte order is set to be compatible with endian-ness of system
        if (sys.byteorder == 'big'):
            bo = 'MSBFirst'
        else:
            bo = 'LSBFirst'
            
        self._instWrite("WAVeform:BYTeorder " + bo)

        #@@@#print('Waveform Format: ' + self._instQuery('WAV:FORM?'))
        
        # Display the waveform settings from preamble:
        wav_form_dict = {
            0 : "ASCii",
            1 : "BYTE",
            2 : "WORD",
            3 : "LONG",
            4 : "LONGLONG",
            5 : "FLOat",
        }
        acq_type_dict = {
            1 : "RAW",
            2 : "AVERage",
            3 : "VHIStogram",
            4 : "HHIStogram",
            6 : "INTerpolate",
            9 : "DIGITAL",
            10 : "PDETect",
        }
        acq_mode_dict = {
            0 : "RTIMe",
            1 : "ETIMe",
            2 : "SEGMented",
            3 : "PDETect",
        }
        coupling_dict = {
            0 : "AC",
            1 : "DC",
            2 : "DCFIFTY",
            3 : "LFREJECT",
        }
        units_dict = {
            0 : "UNKNOWN",
            1 : "VOLT",
            2 : "SECOND",
            3 : "CONSTANT",
            4 : "AMP",
            5 : "DECIBEL",
            6 : "HERTZ",
            7 : "WATT",
        }

        units_abbrev_dict = {
            0 : "?",
            1 : "V",
            2 : "s",
            3 : "CONST.",
            4 : "A",
            5 : "dB",
            6 : "Hz",
            7 : "W",
        }

        units_axis_dict = {
            0 : "UNKNOWN",
            1 : "Voltage",
            2 : "Time",
            3 : "CONSTANT",
            4 : "Current",
            5 : "Decibels",
            6 : "Frequency",
            7 : "Power",
        }
        
        preamble_string = self._instQuery("WAVeform:PREamble?")
        (wav_form, acq_type, wfmpts, avgcnt, x_increment, x_origin,
         x_reference, y_increment, y_origin, y_reference, coupling,
         x_display_range, x_display_origin, y_display_range,
         y_display_origin, date, time, frame_model, acq_mode,
         completion, x_units, y_units, max_bw_limit, min_bw_limit
        ) = preamble_string.split(",")

        meta.append(("Date","{}".format(date)))
        meta.append(("Time","{}".format(time)))
        meta.append(("Frame model #","{}".format(frame_model)))
        meta.append(("Waveform source","{}".format(wav_source)))
        meta.append(("Waveform view","{}".format(wav_view)))
        meta.append(("Waveform format","{}".format(wav_form_dict[int(wav_form)])))
        meta.append(("Acquire mode","{}".format(acq_mode_dict[int(acq_mode)])))
        meta.append(("Acquire type","{}".format(acq_type_dict[int(acq_type)])))
        meta.append(("Coupling","{}".format(coupling_dict[int(coupling)])))
        meta.append(("Waveform points available","{}".format(wfmpts)))
        meta.append(("Waveform average count","{}".format(avgcnt)))
        meta.append(("Waveform X increment","{}".format(x_increment)))
        meta.append(("Waveform X origin","{}".format(x_origin)))
        meta.append(("Waveform X reference","{}".format(x_reference))) # Always 0.
        meta.append(("Waveform Y increment","{}".format(y_increment)))
        meta.append(("Waveform Y origin","{}".format(y_origin)))
        meta.append(("Waveform Y reference","{}".format(y_reference))) # Always 0.
        meta.append(("Waveform X display range","{}".format(x_display_range)))
        meta.append(("Waveform X display origin","{}".format(x_display_origin)))
        meta.append(("Waveform Y display range","{}".format(y_display_range)))
        meta.append(("Waveform Y display origin","{}".format(y_display_origin)))
        meta.append(("Waveform X units","{}".format(units_dict[int(x_units)])))
        meta.append(("Waveform Y units","{}".format(units_dict[int(y_units)])))
        meta.append(("Max BW limit","{}".format(max_bw_limit)))
        meta.append(("Min BW limit","{}".format(min_bw_limit)))
        meta.append(("Completion pct","{}".format(completion)))
        
        # Convert some of the preamble to numeric values for later calculations.
        #
        # NOTE: These are already gathered from PREamble above but s
        #
        acq_type    = int(acq_type)
        wav_form    = int(wav_form)
        x_units     = int(x_units)
        y_units     = int(y_units)
        x_increment = float(x_increment)
        x_origin    = float(x_origin)
        x_reference = int(float(x_reference))
        y_increment = float(y_increment)
        y_origin    = float(y_origin)
        y_reference = int(float(y_reference))
        x_display_range  = float(x_display_range)
        x_display_origin = float(x_display_origin)

        # Get the waveform data.
        pts = ''
        start = 0
        if (points is not None):
            if (channel.startswith('HIST')):
                print('   WARNING: Requesting Histogram data with Points. Ignore Points and returning all\n')
            else:
                # If want subset of points, grab them from the center of display
                midpt = int((((x_display_range / 2) + x_display_origin) - x_origin) / x_increment)
                start = midpt - (points // 2)
                pts = ' {},{}'.format(start,points)
                print('   As requested only downloading center {} points starting at {}\n'.format(points, ((x_reference + start) * x_increment) + x_origin))
            
        self._instWrite("WAVeform:STReaming OFF")
        sData = self._instQueryIEEEBlock("WAVeform:DATA?"+pts)

        meta.append(("Waveform bytes downloaded","{}".format(len(sData))))
        
        if (DEBUG):
            # Wait until after data transfer to output meta data so
            # that the preamble data is captured as close to the data
            # as possible.
            for mm in meta:
                print("{:>27}: {}".format(mm[0],mm[1]))
            print()

        # Set parameters based on returned Waveform Format
        #
        # NOTE: Ignoring ASCII format
        if (wav_form == 1):
            # BYTE
            bits = 8
            npTyp = np.int8
            unpackStr = "@%db" % (len(sData)//(bits//8))
        elif (wav_form == 2):
            # WORD
            bits = 16
            npTyp = np.int16
            unpackStr = "@%dh" % (len(sData)//(bits//8))
        elif (wav_form == 3):
            # LONG (unclear but believe this to be 32 bits)
            bits = 32
            npTyp = np.int32
            unpackStr = "@%dl" % (len(sData)//(bits//8))
        elif (wav_form == 4):
            # LONGLONG
            bits = 64
            npTyp = np.int64
            unpackStr = "@%dq" % (len(sData)//(bits//8))
        elif (wav_form == 5):
            # FLOAT (single-precision)
            bits = 32
            npTyp = np.float32
            unpackStr = "@%df" % (len(sData)//(bits//8))
        else:
            raise RuntimeError('Unknown Waveform Format: ' + wav_form_dict[wav_form])
        
        # Unpack signed byte data.
        if (version_info < (3,)):
            ## If PYTHON 2, sData will be a string and needs to be converted into a list of integers
            #
            # NOTE: not sure if this still works - besides PYTHON2 support is deprecated
            values = np.array([ord(x) for x in sData], dtype=np.int8)
        else:
            ## If PYTHON 3, 
            # Unpack signed data and store in proper type
            #
            # If the acquire type is HHIStogram or VHIStogram, the data is signed 64-bit integers
            #if (acq_type == 3 or acq_type == 4):
            #    unpackStr = "@%dq" % (len(sData)//8)
            #    unpackTyp = np.int64
            #else:
            #    unpackStr = "@%dh" % (len(sData)//2)
            #    unpackTyp = np.int16

            values = np.array(struct.unpack(unpackStr, sData), dtype=npTyp)
            
        nLength = len(values)
        meta.append(("Number of data values","{:d}".format(nLength)))

        # create an array of time (or voltage if histogram) values
        #
        # NOTE: Documentation currently say x_reference should
        # always be 0 but still including it in equation in case
        # that changes in the future
        x = ((np.arange(nLength) - x_reference + start) * x_increment) + x_origin

        # If the acquire type is DIGITAL, the y data
        # does not need to be converted to an analog value
        if (acq_type == 9):
            if (channel.startswith('BUS')):
                # If the channel name starts with BUS, then do not break into bits
                y = values      # no conversion needed
                header = ['Time (s)', 'BUS Values']

            elif (channel.startswith('POD')):
                # If the channel name starts with POD, then data needs
                # to be split into bits. Note that different
                # oscilloscope Series Class add PODx as valid channel
                # names if they support digital channels. This
                # prevents those without digital channels from ever
                # passing in a channel name that starts with 'POD' so
                # no need to also check here.

                # Put number of POD into 'pod'
                if (channel == 'PODALL'):
                    # Default to 1 so the math works out to get all 16 digital channels
                    pod = 1
                else:
                    # Grab number suffix to determine which bit to start with
                    pod = int(channel[-1])
                                
                # So y will be a 2D array where y[0] is time array of bit 0, y[1] for bit 1, etc.
                y = np.empty((bits, len(values)),npTyp)
                for ch in range(bits):
                    y[ch] = (values >> ch) & 1

                header = ['Time (s)'] + ['D{}'.format((pod-1) * bits + ch) for ch in range(bits)]
                    
        else:
            # create an array of vertical data (typ. Voltages)
            #
            if (wav_form == 5):
                # If Waveform Format is FLOAT, then conversion not needed
                y = values
            else:
                # NOTE: Documentation currently say y_reference should
                # always be 0 but still including it in equation in case
                # that changes in the future                    
                y = ((values - y_reference) * y_increment) + y_origin

            header = [f'{units_axis_dict[x_units]} ({units_abbrev_dict[x_units]})', f'{units_axis_dict[y_units]} ({units_abbrev_dict[y_units]})']

            
        # Return the data in numpy arrays along with the header & meta data
        return (x, y, header, meta)
        
    # =========================================================
    # Based on the Waveform data download example from the MSO-X 3000 Programming
    # Guide and modified to work within this class ...
    # =========================================================
    def _waveformDataLegacy(self, channel, points=None):
        """ Download the Waveform Data of a particular Channel and return it. """

        DEBUG = True
            
        # Download waveform data.
        # --------------------------------------------------------

        # Create array for meta data
        meta = []

        # Set the waveform source.
        self._instWrite("WAVeform:SOURce {}".format(self.channelStr(channel)))
        wav_source = self._instQuery("WAVeform:SOURce?")

        # Get the waveform view.
        wav_view = self._instQuery("WAVeform:VIEW?")
        
        # Choose the format of the data returned:
        self._instWrite("WAVeform:FORMat BYTE")

        # Set to Unsigned data which is compatible with PODx
        self._instWrite("WAVeform:UNSigned ON")

        # Set the waveform points mode.
        self._instWrite("WAVeform:POINts:MODE MAX")
        wav_points_mode = self._instQuery("WAVeform:POINts:MODE?")

        # Set the number of waveform points to fetch, if it was passed in.
        #
        # NOTE: With this Legacy software, this decimated the data so
        # that you would still get a display's worth but not every
        # single time bucket. This works differently for the newer
        # software where above points picks the number of points in
        # the center of the display to send but every consecutive time
        # bucket is sent.
        if (points is not None):
            self._instWrite("WAVeform:POINts {}".format(points))
        wav_points = int(self._instQuery("WAVeform:POINts?"))

        # Display the waveform settings from preamble:
        wav_form_dict = {
            0 : "BYTE",
            1 : "WORD",
            4 : "ASCii",
        }

        acq_type_dict = {
            0 : "NORMal",
            1 : "PEAK",
            2 : "AVERage",
            3 : "HRESolution",
        }

        (
            wav_form_f,
            acq_type_f,
            wfmpts_f,
            avgcnt_f,
            x_increment,
            x_origin,
            x_reference_f,
            y_increment,
            y_origin,
            y_reference_f
        ) = self._instQueryNumbers("WAVeform:PREamble?")

        ## convert the numbers that are meant to be integers
        (
            wav_form,
            acq_type,
            wfmpts,
            avgcnt,
            x_reference,
            y_reference
        ) = list(map(int,         (
            wav_form_f,
            acq_type_f,
            wfmpts_f,
            avgcnt_f,
            x_reference_f,
            y_reference_f
        )))


        meta.append(("Waveform source","{}".format(wav_source)))
        meta.append(("Waveform view","{}".format(wav_view)))
        meta.append(("Waveform format","{}".format(wav_form_dict[int(wav_form)])))
        meta.append(("Acquire type","{}".format(acq_type_dict[int(acq_type)])))
        meta.append(("Waveform points mode","{}".format(wav_points_mode)))
        meta.append(("Waveform points available","{}".format(wav_points)))
        meta.append(("Waveform points desired","{:d}".format((wfmpts))))
        meta.append(("Waveform average count","{:d}".format(avgcnt)))
        meta.append(("Waveform X increment","{:1.12f}".format(x_increment)))
        meta.append(("Waveform X origin","{:1.9f}".format(x_origin)))
        meta.append(("Waveform X reference","{:d}".format(x_reference))) # Always 0.
        meta.append(("Waveform Y increment","{:f}".format(y_increment)))
        meta.append(("Waveform Y origin","{:f}".format(y_origin)))
        meta.append(("Waveform Y reference","{:d}".format(y_reference))) # Always 128 with UNSIGNED
        
        # Convert some of the preamble to numeric values for later calculations.
        #
        # NOTE: These are already gathered from PREamble above but s
        #
        wav_form    = int(wav_form)
        x_increment = float(x_increment)
        x_origin    = float(x_origin)
        y_increment = float(y_increment)
        y_origin    = float(y_origin)

        # Get the waveform data.
        sData = self._instQueryIEEEBlock("WAVeform:DATA?")

        meta.append(("Waveform bytes downloaded","{}".format(len(sData))))
        
        if (DEBUG):
            # Wait until after data transfer to output meta data so
            # that the preamble data is captured as close to the data
            # as possible.
            for mm in meta:
                print("{:>27}: {}".format(mm[0],mm[1]))
            print()
        
        if (version_info < (3,)):
            ## If PYTHON 2, sData will be a string and needs to be converted into a list of integers
            #
            # NOTE: not sure if this still works - besides PYTHON2 support is deprecated
            values = np.array([ord(x) for x in sData], dtype=np.int8)
        else:
            ## If PYTHON 3, 
            # Unpack unsigned byte data and store in int16 so room to convert unsigned to signed
            values = np.array(struct.unpack("%dB" % len(sData), sData), dtype=np.int16)

        nLength = len(values)
        meta.append(("Number of data values","{:d}".format(nLength)))

        # create an array of time values
        x = ((np.arange(nLength) - x_reference) * x_increment) + x_origin

        if (channel.startswith('BUS')):
            # If the channel name starts with BUS, then data is not
            # analog and does not need to be converted
            y = values      # no conversion needed
            header = ['Time (s)', 'BUS Values']

        elif (channel.startswith('POD')):
            # If the channel name starts with POD, then data is
            # digital and needs to be split into bits
            if (wav_form == 1):
                # wav_form of 1 is WORD, so 16 bits
                bits = 16
                typ = np.int16
            else:
                # assume byte                
                bits = 8
                typ = np.int8

            # So y will be a 2D array where y[0] is time array of bit 0, y[1] for bit 1, etc.
            y = np.empty((bits, len(values)),typ)
            for ch in range(bits):
                y[ch] = (values >> ch) & 1

            # Put number of POD into 'pod'
            pod = int(channel[-1])
            header = ['Time (s)'] + ['D{}'.format((pod-1) * bits + ch) for ch in range(bits)]
                
        else:
            # create an array of vertical data (typ. Voltages)
            y = ((values - y_reference) * y_increment) + y_origin

            header = ['Time (s)', 'Voltage (V)']
        
        # Return the data in numpy arrays along with the header & meta data
        return (x, y, header, meta)

    def waveformData(self, channel=None, points=None):
        """ Download waveform data of a selected channel

        channel  - channel, as string, to be measured - set to None to use the default channel

        points   - number of points to capture - if None, captures all available points
                   for newer devices, the captured points are centered around the center of the display

        """
        
        # If a channel value is passed in, make it the
        # current channel
        if channel is not None and type(channel) is not list:
            self.channel = channel

        # Make sure channel is NOT a list
        if type(self.channel) is list or type(channel) is list:
            raise ValueError('Channel cannot be a list for WAVEFORM!')

        # Check channel value
        if (self.channel not in self.chanAllValidList):
            raise ValueError('INVALID Channel Value for WAVEFORM: {}  SKIPPING!'.format(self.channel))            

        
        if (self._version > self._versionLegacy):
            (x, y, header, meta) = self._waveformDataNew(self.channel, points)
        else:
            (x, y, header, meta) = self._waveformDataLegacy(self.channel, points)        

        return (x, y, header, meta)
        


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

#---------------------------------------------------------------------------------
#  Control of Arbitrary Waveform Generator (AWG) using
#  standard SCPI commands with PyVISA
#
# For more information on SCPI, see:
# https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments
# http://www.ivifoundation.org/docs/scpi-99.pdf
#-------------------------------------------------------------------------------

# For future Python3 compatibility:
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from time import sleep
from sys import version_info
from sys import exit
import pyvisa as visa

class SCPI(object):
    """Basic class for controlling and accessing an Arbitrary Waveform Generator with Standard SCPI Commands"""

    # Commands that can be "overloaded" by child classes if need a different syntax
    _SCPICmdTbl = {
        'setLocal':                      'SYSTem:LOCal',
        'setRemote':                     'SYSTem:REMote',
        'setRemoteLock':                 'SYSTem:RWLock ON',
        'beeperOn':                      'SYSTem:BEEPer:STATe ON',
        'beeperOff':                     'SYSTem:BEEPer:STATe OFF',
        'isOutput':                      'OUTPut:STATe?',
        'outputOn':                      'OUTPut:STATe ON',
        'outputOff':                     'OUTPut:STATe OFF',
    }

    # Official SCPI numeric value for Not A Number
    NaN = 9.91E37
    OverRange = NaN
    
    # Size of error queue
    ErrorQueue = 10
    
    def __init__(self, resource, max_chan=1, wait=0,
                 cmds = None,
                 cmd_prefix = '',
                 read_strip = '',
                 read_termination = '',
                 write_termination = '\n',
                 timeout = 5000,
                 encoding = 'ascii'):
        """Init the class with the instruments resource string

        resource   - resource string or VISA descriptor, like TCPIP0::172.16.2.13::INSTR
        max_chan   - number of channels
        wait       - float that gives the default number of seconds to wait after sending each command
        cmds       - a dictionary of cmds to overload the main cmd dictionary
        cmd_prefix - optional command prefix (ie. some instruments require a ':' prefix)
        read_strip        - optional read_strip parameter used to strip any returned termination characters
        read_termination  - optional read_termination parameter to pass to open_resource()
        write_termination - optional write_termination parameter to pass to open_resource()
        encoding          - optional encoding to use when writing and reading data
                            (see https://docs.python.org/3/library/codecs.html#standard-encodings)
        """
        self._resource = resource
        self._max_chan = max_chan                # number of channels
        self._wait = wait
        self._prefix = cmd_prefix
        self._curr_chan = 1                      # set the current channel to the first one
        self._read_strip = read_strip
        self._read_termination = read_termination
        self._write_termination = write_termination
        self._timeout = timeout
        self._encoding = encoding
        self._IDNmanu = ''      # store manufacturer from IDN here
        self._IDNmodel = ''     # store instrument model number from IDN here
        self._IDNserial = ''    # store instrument serial number from IDN here
        self._version = 0.0     # set software version to lowest value until it gets set
        self._versionLegacy = 0.0   # set software version which triggers Legacy code to lowest value until it gets set
        self._errorCmd = ("SYSTem:ERRor?", ("+0,", 0, 3)) # Command to get Errors and comparison of returned string that indicates no error
        self._defaultCheckErrors = False # By default do not check errors. Child classes can turn this on once they open()
        self._inst = None

        if cmds is not None:
            # update _SCPICmdTbl[] with commands from child
            SCPI._SCPICmdTbl.update(cmds)
        

    def open(self):
        """Open a connection to the VISA device with PYVISA-py python library"""
        self._rm = visa.ResourceManager('@py')
        self._inst = self._rm.open_resource(self._resource,
                                            read_termination=self._read_termination,
                                            write_termination=self._write_termination,
                                            encoding=self._encoding)
        self._inst.timeout = self._timeout

        # Keysight recommends using clear()
        #
        # NOTE: must use pyvisa-py >= 0.5.0 to get this implementation
        # NOTE: pyvisa-py does not support clear() for USB so catch error
        try:
            self._inst.clear()
        except visa.VisaIOError as err:
            if (err.error_code == visa.constants.StatusCode.error_nonsupported_operation):
                # If this resource does not support clear(), that is
                # okay and it can be ignored.
                pass
            else:
                # However, if this is a different error be sure to raise it.
                raise
                
        # Read ID to gather items like software version number so can
        # deviate operation based on changes to commands over history
        # (WHY did they make changes?)  MUST be done before below
        # clear() which sends first command.
        self._getID()

        # Also, send a *CLS system command to clear the command
        # handler (error queues and such)
        self.clear()

        
    def close(self):
        """Close the VISA connection"""
        self._inst.close()

    @property
    def channel(self):
        return self._curr_chan

    @channel.setter
    def channel(self, value):
        self._curr_chan = value

    def _instQuery(self, queryStr, checkErrors=None):
        if (checkErrors is None):
            # Default for checkErrors is pulled from self._defaultCheckErrors
            checkErrors = self._defaultCheckErrors

        if (queryStr[0] != '*'):
            queryStr = self._prefix + queryStr
        #print("QUERY:",queryStr)
        try:
            result = self._inst.query(queryStr)
        except visa.VisaIOError as err:
            # Got VISA exception so read and report any errors
            if checkErrors:
                self.checkInstErrors(queryStr)
            #@@@#print("Exited because of VISA IO Error: {}".format(err))
            #@@@#exit(1)
            # raise same error so code calling this can use try/except to catch things
            raise
            
        if checkErrors:
            self.checkInstErrors(queryStr)
        return result.rstrip(self._read_strip)

    def _instQueryNumber(self, queryStr, checkErrors=None):
        return float(self._instQuery(queryStr, checkErrors))

    def _instWrite(self, writeStr, checkErrors=None):
        if (checkErrors is None):
            # Default for checkErrors is pulled from self._defaultCheckErrors
            checkErrors = self._defaultCheckErrors

        if (writeStr[0] != '*'):
            writeStr = self._prefix + writeStr
        #@@@print("WRITE:",writeStr)
        try:
            result = self._inst.write(writeStr)
        except visa.VisaIOError as err:
            # Got VISA exception so read and report any errors
            if checkErrors:
                self.checkInstErrors(writeStr)
            #@@@#print("Exited because of VISA IO Error: {}".format(err))
            #@@@#exit(1)
            # raise same error so code calling this can use try/except to catch things
            raise

        if checkErrors:
            self.checkInstErrors(writeStr)
        return result

    def chStr(self, channel):
        """return the channel string given the channel number and using the format CHx"""

        return 'CH{}'.format(channel)

    def _chanStr(self, channel):
        """return the channel string given the channel number and using the format x"""

        return '{}'.format(channel)

    def channelStr(self, channel):
        """return the channel string given the channel number and using the format CHANnelx if x is numeric. If pass in None, return None."""

        try:
            return 'CHAN{}'.format(int(channel))
        except TypeError:
            # If channel is None, will get this exception so simply return it
            return channel
        except ValueError:
            return self._chanStr(channel)

    def _chanNumber(self, str):
        """Decode the response as a channel number and return it. Return 0 if string does not decode properly.
        """

        # Only check first character so do not need to deal with
        # trailing whitespace and such
        if str[:4] == 'CHAN':
            return int(str[4])
        else:
            return 0

    def _onORoff(self, str):
        """Check if string says it is ON or OFF and return True if ON
        and False if OFF
        """

        # Only check first two characters so do not need to deal with
        # trailing whitespace and such
        if str[:2] == 'ON':
            return True
        else:
            return False

    def _1OR0(self, str):
        """Check if string says it is 1 or 0 and return True if 1
        and False if 0
        """

        # Only check first character so do not need to deal with
        # trailing whitespace and such
        if str[:1] == '1':
            return True
        else:
            return False

    def _bool2onORoff(self, bool):
        """If bool is True, return ON string, else return OFF string. Use to
        convert boolean input to ON or OFF string output.
        """

        if (bool):
            return 'ON'
        else:
            return 'OFF'

    def _onORoff_1OR0_yesORno(self, str):
        """Check if string says it is ON or OFF and return True if ON
        and False if OFF OR check if '1' or '0' and return True for '1' 
        OR check if 'YES' or 'NO' and return True for 'YES'
        """

        # trip out whitespace
        str = str.strip()
        
        if str == 'ON':
            return True
        elif str == 'YES':
            return True
        elif str == '1':
            return True
        else:
            return False
        
    def _wait(self):
        """Wait until all preceeding commands complete"""
        #self._instWrite('*WAI')
        self._instWrite('*OPC')
        wait = True
        while(wait):
            ret = self._instQuery('*OPC?')
            if ret[0] == '1':
                wait = False

    # =========================================================
    # Taken from the MSO-X 3000 Programming Guide and modified to work
    # within this class ...
    #    
    # UPDATE: Apparently "SYSTem:ERRor?" has changed but the
    # documentation is unclear so will make it work as it works on
    # MXR058A with v11.10
    # =========================================================
    # Check for instrument errors:
    # =========================================================
    def checkInstErrors(self, commandStr):

        cmd = self._errorCmd[0]
        noerr = self._errorCmd[1]

        #@@@#print("cmd: {}  noerr: {}".format(cmd, noerr))
            
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
    # Based on do_query_ieee_block() from the MSO-X 3000 Programming
    # Guide and modified to work within this class ...
    # =========================================================
    def _instQueryIEEEBlock(self, queryStr, checkErrors=None):
        if (checkErrors is None):
            # Default for checkErrors is pulled from self._defaultCheckErrors
            checkErrors = self._defaultCheckErrors

        if (queryStr[0] != '*'):
            queryStr = self._prefix + queryStr
        #print("QUERYIEEEBlock:",queryStr)
        try:
            result = self._inst.query_binary_values(queryStr, datatype='s', container=bytes)
        except visa.VisaIOError as err:
            # Got VISA exception so read and report any errors
            if checkErrors:
                self.checkInstErrors(queryStr)
            print("Exited because of VISA IO Error: {}".format(err))
            exit(1)
            
        if checkErrors:
            self.checkInstErrors(queryStr)
        return result

    # =========================================================
    # Based on code from the MSO-X 3000 Programming
    # Guide and modified to work within this class ...
    # =========================================================
    def _instQueryNumbers(self, queryStr, checkErrors=None):
        if (checkErrors is None):
            # Default for checkErrors is pulled from self._defaultCheckErrors
            checkErrors = self._defaultCheckErrors

        if (queryStr[0] != '*'):
            queryStr = self._prefix + queryStr
        #print("QUERYNumbers:",queryStr)
        try:
            result = self._inst.query_ascii_values(queryStr, converter='f', separator=',')
        except visa.VisaIOError as err:
            # Got VISA exception so read and report any errors
            if checkErrors:
                self.checkInstErrors(queryStr)
            print("Exited because of VISA IO Error: {}".format(err))
            exit(1)
            
        if checkErrors:
            self.checkInstErrors(queryStr)
        return result

    # =========================================================
    # Based on do_command_ieee_block() from the MSO-X 3000 Programming
    # Guide and modified to work within this class ...
    # =========================================================
    def _instWriteIEEEBlock(self, writeStr, values, checkErrors=None):
        if (checkErrors is None):
            # Default for checkErrors is pulled from self._defaultCheckErrors
            checkErrors = self._defaultCheckErrors

        if (writeStr[0] != '*'):
            writeStr = self._prefix + writeStr
        #print("WRITE:",writeStr)

        if (version_info < (3,)):
            ## If PYTHON 2, must use datatype of 'c'
            datatype = 'c'
        else:
            ## If PYTHON 2, must use datatype of 'B' to get the same result
            datatype = 'B'

        try:
            result = self._inst.write_binary_values(writeStr, values, datatype=datatype)
        except visa.VisaIOError as err:
            # Got VISA exception so read and report any errors
            if checkErrors:
                self.checkInstErrors(writeStr)
            print("Exited because of VISA IO Error: {}".format(err))
            exit(1)

        if checkErrors:
            self.checkInstErrors(writeStr)
        return result

    def _instWriteIEEENumbers(self, writeStr, values, checkErrors=None):
        if (checkErrors is None):
            # Default for checkErrors is pulled from self._defaultCheckErrors
            checkErrors = self._defaultCheckErrors

        if (writeStr[0] != '*'):
            writeStr = self._prefix + writeStr
        #print("WRITE:",writeStr)

        try:
            result = self._inst.write_binary_values(writeStr, values, datatype='f')
        except visa.VisaIOError as err:
            # Got VISA exception so read and report any errors
            if checkErrors:
                self.checkInstErrors(writeStr)
            print("Exited because of VISA IO Error: {}".format(err))
            exit(1)

        if checkErrors:
            self.checkInstErrors(writeStr)
        return result

    def _versionUpdated(self):
        """Overload this function in child classes so can update parameters once the version number is known."""
        pass
    
    def _getID(self):
        """Query IDN data like Software Version to handle command history deviations. This is called from open()."""
        ## Skip Error check since handling of errors is version specific
        idn = self._instQuery('*IDN?', checkErrors=False).split(',')
        
        self._IDNmanu = idn[0]   # store manufacturer from IDN here
        self._IDNmodel = idn[1]  # store instrument model number from IDN here
        self._IDNserial = idn[2] # store instrument serial number from IDN here

        ver = idn[3].split('.')
        try:
            # put major and minor version into floating point format so can numerically compare
            self._version = float(ver[0]+'.'+ver[1])
        except:
            # In case version is not purely numeric
            ver[-1] = ver[-1].replace('\n', '')
            self._version = tuple(ver)
            self._versionLegacy = tuple()

        # Allow a child's funciton to run to update data based on its version number
        self._versionUpdated()        
        
    def _Cmd(self, key):
        """Lookup the needed command string from local dictionary."""
        # NOTE: do not assume if in _SCPICmdTbl that is is an official SCPI command
        if not key in SCPI._SCPICmdTbl:
            raise RuntimeError('Unknown Command: "' + key + '"')
        return SCPI._SCPICmdTbl[key]
        
    def idn(self):
        """Return response to *IDN? message"""
        return self._instQuery('*IDN?')

    def clear(self):
        """Sends a *CLS message to clear status and error queues"""
        return self._instWrite('*CLS')

    def reset(self):
        """Sends a *RST message to reset to defaults"""
        return self._instWrite('*RST')

    def setLocal(self):
        """Set the power supply to LOCAL mode where front panel keys work again
        """

        # Not sure if this is SCPI, but it appears to be supported
        # across different instruments
        self._instWrite(self._Cmd('setLocal'))
    
    def setRemote(self):
        """Set the power supply to REMOTE mode where it is controlled via VISA
        """

        # Not sure if this is SCPI, but it appears to be supported
        # across different instruments
        self._instWrite(self._Cmd('setRemote'))
    
    def setRemoteLock(self):
        """Set the power supply to REMOTE Lock mode where it is
           controlled via VISA & front panel is locked out
        """

        # Not sure if this is SCPI, but it appears to be supported
        # across different instruments
        self._instWrite(self._Cmd('setRemoteLock'))

    def beeperOn(self):
        """Enable the system beeper for the instrument"""
        self._instWrite(self._Cmd('beeperOn'))
        
    def beeperOff(self):
        """Disable the system beeper for the instrument"""
        self._instWrite(self._Cmd('beeperOff'))
        
    def isOutputOn(self, channel=None):
        """Return true if the output of channel is ON, else false
        
           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
            
        if (self._max_chan > 1 and channel is not None):
            # If multi-channel device and channel parameter is passed, select it
            self._instWrite(self._Cmd('chanSelect').format(self.channel))
            
        str = self._Cmd('isOutput')
        ret = self._instQuery(str)
        # @@@print("1:", ret)
        return self._onORoff_1OR0_yesORno(ret)
    
    def outputOn(self, channel=None, wait=None):
        """Turn on the output for channel
        
           wait    - number of seconds to wait after sending command
           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel

        if (self._max_chan > 1 and channel is not None):
            # If multi-channel device and channel parameter is passed, select it
            self._instWrite(self._Cmd('chanSelect').format(self.channel))
                        
        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait
            
        str = self._Cmd('outputOn')
        self._instWrite(str)
        sleep(wait)             # give some time for PS to respond
    
    def outputOff(self, channel=None, wait=None):
        """Turn off the output for channel
        
           channel - number of the channel starting at 1
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
                    
        if (self._max_chan > 1 and channel is not None):
            # If multi-channel device and channel parameter is passed, select it
            self._instWrite(self._Cmd('chanSelect').format(self.channel))
            
        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait
            
        str = self._Cmd('outputOff')
        self._instWrite(str)
        sleep(wait)             # give some time for PS to respond
    
    def outputOnAll(self, wait=None):
        """Turn on the output for ALL channels
        
        """

        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait

        for chan in range(1,self._max_chan+1):
            if (self._max_chan > 1):
                # If multi-channel device, select next channel
                self._instWrite(self._Cmd('chanSelect').format(self.channel))
            
            str = self._Cmd('outputOn')
            
        sleep(wait)             # give some time for PS to respond
    
    def outputOffAll(self, wait=None):
        """Turn off the output for ALL channels
        
        """

        # If a wait time is NOT passed in, set wait to the
        # default time
        if wait is None:
            wait = self._wait

        for chan in range(1,self._max_chan+1):
            if (self._max_chan > 1):
                # If multi-channel device, select next channel
                self._instWrite(self._Cmd('chanSelect').format(self.channel))
            
            str = self._Cmd('outputOff')
            
        sleep(wait)             # give some time for PS to respond
    
    def _setGenericParameter(self, value, cmd, channel=None, wait=None, checkErrors=None):
        """Generic function to handle setting of parameters
        
           value   - value to set
           cmd     - command string to use for setting the parameter
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
            
        str = cmd.format(self.channelStr(self.channel), value)
        #@@@#print(str)
        self._instWrite(str, checkErrors)
        sleep(wait)             # give some time for PS to respond

    def _setGenericParameters(self, values, cmd, channel=None, wait=None, checkErrors=None):
        """Generic function to handle setting of parameters
        
           values  - a dictionary where keys of the parameter names and
                     their values are the values to set. Best to use a
                     Python OrderedDict() so can control the order of the keys
           cmd     - command string to use for setting the parameter
           wait    - number of seconds to wait after sending command
           channel - number of the channel starting at 1
        """

        # Convert the dictionary to a comma seperated string of key,value pairs
        value = ','.join(["{},{}".format(key,values[key]) for key in values])

        # Now can call the single value function
        self._setGenericParameter(value, cmd, channel, wait, checkErrors)

    def _queryGenericParameter(self, cmd, channel=None, checkErrors=None):
        """Generic function to handle query of parameters
        
           cmd     - command string to use for the query
           channel - number of the channel starting at 1
           checkErrors - If True, Check for SCPI Errors, else don't bother
                         if None, use self._defaultCheckErrors
        """

        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
            
        str = cmd.format(self.channelStr(self.channel))
        #@@@#print(str)
        
        ret = self._instQuery(str, checkErrors)
        return float(ret)

    def _queryGenericFloat(self, cmd, channel=None, checkErrors=None):
        """Generic function to Perform a SCPI Query and return the value as a float
        
           cmd     - command string to use for the query
           channel - number of the channel starting at 1
           checkErrors - If True, Check for SCPI Errors, else don't bother
                         if None, use self._defaultCheckErrors
        """
        
        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
            
        str = cmd.format(self.channelStr(self.channel))
        #@@@#print(str)
            
        ret = self._instQuery(str, checkErrors)
        return float(ret)
    
    def _queryGenericBool(self, cmd, channel=None, checkErrors=None):
        """Generic function to Perform a SCPI Query and return the value as a boolean
           "ON", "1" or "YES" returns True
           "OFF", "0" or "NO" returns False
        
           cmd     - command string to use for the query
           channel - number of the channel starting at 1
           checkErrors - If True, Check for SCPI Errors, else don't bother
                         if None, use self._defaultCheckErrors
        """
        
        # If a channel number is passed in, make it the
        # current channel
        if channel is not None:
            self.channel = channel
            
        str = cmd.format(self.channelStr(self.channel))
        #@@@#print(str)
            
        ret = self._instQuery(str, checkErrors)
        return self._onORoff_1OR0_yesORno(ret)
    
    
        

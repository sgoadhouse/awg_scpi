# awg-scpi

# Description

Control of Arbitrary Waveform Generators (AWG) with SCPI Command Sets through python via PyVisa

This uses the brilliant PyVISA python package along with the PyVisa-PY
access mode which eliminates the need for the (very buggy, in my
experience) VISA library to be installed on your computer. However,
PyVISA-PY does require `libusb` which is needed for FTDI control and
other things.

The intent is to support as many AWGs as is
possible. However, I only have access to one 
so that is what has been coded and tested. If you are interested in
adding support for some other SCPI AWG,
then contact me for details in how to add those. 

# Installation

To install the awg-scpi package, clone this GIT repository and then
run the following command in the top level folder:

```
python setup.py install
```

Alternatively, can add a path to this package to the environment
variable PYTHONPATH or even add the path to it at the start of your
python script. Use your favorite web search engine to find out more
details. If you follow this route, you will need to also install all
of the dependant packages which are shown below under Requirements.

Even better, awg-scpi is on PyPi. So you can simply use the
following and the required dependancies should get installed for you:

```
pip install awg_scpi
```

## Requirements
* [argparse](https://docs.python.org/3/library/argparse.html) 
* [numpy 1.19.5](https://numpy.org/)
   * if installing on python 3.6 or 3.7, numpy 1.19.5 will be installed
   * if installing on python 3.8+, then the latest numpy will be installed
      * Up to numpy 1.22.3 has been verified
* [python](http://www.python.org/)
   * pyvisa no longer supports python 2.7+ so neither does this package - use older version of [MSOX3000](https://github.com/sgoadhouse/msox3000) if need python 2.7+
* [pyvisa 1.11.3](https://pyvisa.readthedocs.io/en/stable/)
* [pyvisa-py 0.5.2](https://pyvisa-py.readthedocs.io/en/latest/) 
* [quantiphy 2.3.0](http://quantiphy.readthedocs.io/en/stable/) 

In order to run the example script `awg.py`, you will also need to manually install:
* [matplotlib 3.3.4](https://matplotlib.org)
   * If cannot install `matplotlib` on your system, see the comments in `awg.py` on how to modify it to work without `matplotlib`. 

With the use of pyvisa-py, you should not have to install the National
Instruments VISA driver.

## Features

This code is not an exhaustive coverage of all available commands and
queries of AWGs. The features that do exist are mainly
ones that improve productivity like saving and loading configuration. 

Currently, this is a list of the features that are supported so far:

* Nothing YET

It is expected that new interfaces will be added over time to control
and automate the AWG. The key features that would be good to
add next are: ....

## Channels

Almost all functions require a target channel. Once a
channel is passed into a function, the object will remember it and
make it the default for all subsequence function calls that do not
supply a channel. The channel value is a string or can also be a list
of strings, in the case of setupAutoscale(). Currently, the valid
channel values are:

NOTE: NEED TO UPDATE THE FOLLOWING LIST
* '1' or CHAN1 for analog channel 1
* '2' or CHAN2 for analog channel 2

## Usage and Examples
The code is a basic class for controlling and accessing the
supported AWGs.

The examples are written to access the AWG over
ethernet/TCPIP. So the examples need to know the IP address of your
specific AWG. Also, PyVISA can support other access
mechanisms, like USB. So the examples must be edited to use the
resource string or VISA descriptor of your particular
device. Alternatively, you can set an environment variable, AWG\_IP
to the desired VISA resource string before running the code. If not using
ethernet to access your device, search online for the proper resource
string needed to access your device.

For more detailed examples, see:

```
awg.py -h
```

NOTE: THE EXAMPLE NEEDS UPDATING!
A basic example that installs a few measurements to the statistics
display, adds some annotations and signal labels and then saves a
hardcopy to a file.

```python
# Lookup environment variable AWG_IP and use it as the resource
# name or use the TCPIP0 string if the environment variable does
# not exist
from awg_scpi import AWG
from os import environ
resource = environ.get('AWG_IP', 'TCPIP0::172.16.2.13::INSTR')

# create your visa instrument
instr = AWG(resource)

# Upgrade Object to best match based on IDN string
instr = instr.getBestClass()

# Open connection to instrument
instr.open()

# set to channel 1
#
# NOTE: can pass channel to each method or just set it
# once and it becomes the default for all following calls. If pass the
# channel to a Class method call, it will become the default for
# following method calls.
instr.channel = '1'

# Enable output of channel, if it is not already enabled
if not instr.isOutputOn():
    instr.outputOn()

# Install measurements to display in statistics display and also
# return their current values here
print('Ch. {} Settings: {:6.4e} V  PW {:6.4e} s\n'.
          format(instr.channel, instr.measureVoltAverage(install=True),
                     instr.measurePosPulseWidth(install=True)))

# Add an annotation to the screen before hardcopy
instr.annotate("{} {} {}".format('Example of Annotation','for Channel',instr.channel), 'ch1')

# Change label of the channel to "MySig1"
instr.channelLabel('MySig1')

# Make sure the statistics display is showing for the hardcopy
instr.measureStatistics()

# STOP AWG (not required for hardcopy - only showing example of how to do it)
instr.modeStop()

# Save a hardcopy of the screen to file 'outfile.png'
instr.hardcopy('outfile.png')

# SINGLE mode (just an example)
instr.modeSingle()

# Change label back to the default
#
# NOTE: can use instr.channelLabelOff() but showing an example of sending a SCPI command directly
instr._instWrite('DISPlay:LABel OFF')

# RUN mode (since demo Stop and Single, restore Run mode)
instr.modeRun()

# Turn off the annotation
instr.annotateOff()
    
# turn off the channel
instr.outputOff()

# return to LOCAL mode
instr.setLocal()

instr.close()
```

## Taking it Further
This implements a small subset of available commands.

For information on what is possible for the Siglent SDG6022X and other SDG series arbitrary waveform generators, see the
[SDG Series Arbitrary Waveform Generator](https://siglentna.com/USA_website_2014/Documents/Program_Material/SDG_ProgrammingGuide_PG_E03B.pdf)

For what is possible with general instruments that adhere to the
IEEE 488 SCPI specification, see the
[SCPI 1999 Specification](http://www.ivifoundation.org/docs/scpi-99.pdf)
and the
[SCPI Wikipedia](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) entry.

## Contact
Please send bug reports or feedback to Stephen Goadhouse


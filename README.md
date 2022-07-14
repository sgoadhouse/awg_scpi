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

The bible for installing Python packages is:
https://packaging.python.org/en/latest/tutorials/installing-packages/
Ultimately, consult that page for how to install this package. If you
prefer to try commands that worked when this package was written, go
ahead and give the following a try.

To install the awg-scpi package, clone this GIT repository and then
run the following command in the top level folder:

```
python -m pip install .
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
* [python](http://www.python.org/)
   * pyvisa no longer supports python 2.7+ so neither does this package
* [pyvisa 1.11.3](https://pyvisa.readthedocs.io/en/stable/)
* [pyvisa-py 0.5.2](https://pyvisa-py.readthedocs.io/en/latest/) 
* [quantiphy 2.3.0](http://quantiphy.readthedocs.io/en/stable/) 

With the use of pyvisa-py, you should not have to install the National
Instruments VISA driver.

## Features

This code is not an exhaustive coverage of all available commands and
queries of AWGs. The features that do exist are mainly
ones that improve productivity like saving and loading configuration. 

Currently, this is a list of the features that are supported so far:

* _needs to be updated_

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

* '1' for analog channel 1
* '2' for analog channel 2

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

A basic example that sets up a basic wave and enables the output.

```python
from awg_scpi import AWG

from time import sleep    
import argparse
parser = argparse.ArgumentParser(description='Access and control an AWG')
parser.add_argument('chan', nargs='?', type=int, help='Channel to access/control (starts at 1)', default=1)
args = parser.parse_args()

from os import environ
resource = environ.get('AWG_IP', 'TCPIP0::172.16.2.13::INSTR')
instr = AWG(resource)

## Upgrade Object to best match based on IDN string
instr = instr.getBestClass()

## Open this object and work with it
instr.open()

print('Using SCPI Device:     ' + instr.idn() + ' of series: ' + instr.series + '\n')

# set the channel (can pass channel to each method or just set it
# once and it becomes the default for all following calls)
instr.channel = str(args.chan)

if instr.isOutputHiZ(instr.channel):
    print("Output High Impedance")
else:
    print("Output 50 ohm load")

instr.beeperOn()

# return to default parameters
instr.reset()               

instr.setWaveType('SINE')
instr.setFrequency(34.4590897823e3)
instr.setVoltageProtection(6.6)
instr.setAmplitude(3.2)
instr.setOffset(1.6)
instr.setPhase(0.45)

print("Voltage Protection is set to maximum: {}V Amplitude (assumes 0V offset)".format(instr.queryVoltageProtection()))

# turn on the channel
instr.outputOn()

# return to LOCAL mode
instr.setLocal()

instr.close()
```

## Taking it Further
This implements a small subset of available commands.

For information on what is possible for the Siglent SDG6022X and other SDG series arbitrary waveform generators, see the
[SDG Series Arbitrary Waveform Generator](https://siglentna.com//wp-content/uploads/dlm_uploads/2019/12/SDG_Programming-Guide_PG02-E04A.pdf)

For what is possible with general instruments that adhere to the
IEEE 488 SCPI specification, see the
[SCPI 1999 Specification](http://www.ivifoundation.org/docs/scpi-99.pdf)
and the
[SCPI Wikipedia](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) entry.

## Contact
Please send bug reports or feedback to Stephen Goadhouse


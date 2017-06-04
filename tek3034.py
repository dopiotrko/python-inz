#!/usr/bin/env python3
#
import time
import os
import sys
import serial
import visa
import threading 
from serial.tools.list_ports import comports


try:
    raw
except NameError:
    # pylint: disable=redefined-builtin,invalid-name
    raw = input   # in python3 it's "raw"
    unichr = chr

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Message(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.runflag=threading.Event()
        self.command=''

    def start(self,command):
        self.command=command
        threading.Thread.start(self)
        
    def run(self):
        print('   -processing '+self.command,end=' ',flush=True)
        self.runflag.set()
        i=0
        while self.runflag.is_set():
            time.sleep(0.01)
            i += 1
            if ( i%100 == 0 ):
                print( '.', end='', flush=True )
        print(' ')

    def pause(self):
        self.runflag.clear()

class Dialog(object):
    
    def __init__(self,  connection_instance, args ):
        self.connection = connection_instance
        self.args=args
        self.ID=''
        self.msg=None
        
    def eol(self):
        if self.args.eol=='LF':
            return '\n'
        elif self.args.eol=='CR':
            return '\r'
        elif self.args.eol=='CRLF':
            return '\r\n'
    
    def info(self):
        print('Port Settings:')
        print('    {}'.format(self.connection))
        print('Data Settings:')
        print('    Output File name:{}'.format(self.args.file))
        print('    Chanel:{}'.format(self.args.chanel))
        print('    Encoding:{}'.format(self.args.serial_port_encoding))
        print('    Eol character:{}'.format(self.args.eol))

    def ask(self, command):
        self.send(command)
        buffer=None
        if command.endswith('?'):
            self.msg=Message()
            self.msg.start(command)
            buffer=self.get()
            self.msg.pause()
            self.msg.join()
            if buffer is 'ERROR':
                exit(1)
            self.send('*WAI')
        self.send('*ESR?')
        if not self.get().startswith('0'):
            self.send('ALLEV?')
            print('Error nr: '+self.get())
            exit(1)
        return buffer

    def send(self, command):
        if self.args.visa is True:
            try:
                self.connection.write(command)
            except visa.VisaIOError:
                print('Communication time exceeded. Check Your connection.(use \'-p ?\' to show ports list )')
                exit(1)
        else:
            try:
                self.connection.write(str.encode(command+self.eol()))
            except connection.SerialTimeoutException:
                print('Communication time exceeded. Check Your connection.(use \'-p ?\' to show ports list )')
                exit(1)
        
            
    def get(self):
        if self.args.visa is True:
            try:
                buffer=self.connection.read()
            except visa.VisaIOError:
                print('No answer from the device. Check Your connection.(use \'-p ?\' to show ports list )')
                buffer=('ERROR')
#                exit(1)
        else:
            try:
                buffer=self.connection.readline()
            except self.connection.SerialTimeoutException:
                print('No answer from the device. Check Your connection.(use \'-p ?\' to show ports list )')
                buffer=('ERROR')
#                exit(1)
            else:
                buffer=str(buffer, self.args.serial_port_encoding)
        return buffer

    def start(self):
        self.info()
        self.send('*IDN?')
        print('Asking for device ID:')
        self.ID=self.get()
        if self.ID.find('TDS') != -1:
            print('   '+self.ID)
        else:
            print('No TDS devive connected. Incorrect Device? (use \'-p ?\' to show ports list )')
            sys.exit(1)
    
    def get_waveform(self):
        
        self.ask('*CLS')
        self.ask('DATA:ENCDG ASCII')
        self.ask('DATA:SOURCE '+self.args.chanel)
        self.ask('DATA:WIDTH 2')
        
        xzero=float(self.ask('WFMPRE:XZERO?'))
        yzero=float(self.ask('WFMPRE:YZERO?'))
        xincr=float(self.ask('WFMPRE:XINCR?'))
        ymult=float(self.ask('WFMPRE:YMULT?'))
        pt_off=float(self.ask('WFMPRE:PT_OFF?'))
        yoff=float(self.ask('WFMPRE:YOFF?'))
        Ystr=self.ask('CURVE?').split(',')
        xunit=self.ask('WFMPRE:XUNIT?')
        yunit=self.ask('WFMPRE:YUNIT?')
        Y=[float(y) for y in Ystr]
        ofile=open(self.args.file, 'w')
        print('#  '+xunit[:-1]+'         '+yunit[:-1] , file=ofile)
        for yy in range(len(Y)):
            print('{:8.5f}    {:8.5f}'.format(xzero + xincr * ( yy - pt_off ), yzero + ymult * ( Y[yy] -yoff ) ), file=ofile)
        print("----Waveform from chanel " + self.args.chanel +" downloaded, and writen to " +self.args.file+ " file")

class VISArm(object):
    def __init__(self):
        self.rm = visa.ResourceManager()


    def ask_for_ports(self):
        return self.rm.list_resources()

    
def ask_for_ports():
    """\
    Show a list of ports and ask the user for a choice. To make selection
    easier on systems with long device names, also allow the input of an
    index.
    """
    
    ports = []
    for n, (port, desc, hwid) in enumerate(sorted(comports()), 1):
#        print('--- {:2}: {:20} {}'.format(n, port, desc))
        ports.append(port)
    return ports
"""   while True:
        port = raw('--- assign port index or full name: ')
        try:
            index = int(port) - 1
            if not 0 <= index < len(ports):
                print('--- Invalid index!\n')
                continue
        except ValueError:
            pass
        else:
            port = ports[index]
            """
#return ports

def main(default_port='/dev/ttyS0', default_file='out.txt',default_chanel='CH1',  default_baudrate=9600, default_rts=None, default_dtr=None):
    """Command line tool, entry point"""

    if os.name is 'nt': 
        default_port= 'COM1'

    import argparse

    parser = argparse.ArgumentParser(
        description="Program for downloading graph from tektronix TDS Osciloskops.")

    group = parser.add_argument_group("data target")
    group.add_argument(
        "-f","--file", 
        nargs ="?", 
        help="name for the output file (default: %(default)s)", 
        default=default_file)

    group = parser.add_argument_group("data source")
    group.add_argument(
        "-c","--chanel", 
        choices=['CH1', 'CH2', 'CH3', 'CH4', 'MATH','MATH1', 'REF1', 'REF2', 'REF3', 'REF4'], 
        type=lambda c: c.upper(),
        nargs ="?", 
        help="number of oscilloscope chanel to download from (default: %(default)s)", 
        default=default_chanel)
    
    group = parser.add_argument_group("port settings")
    
    group.add_argument(
        "-p","--port",
        nargs='?',
        help="serial port name (default: %(default)s)('?' to show port list)",
        default=default_port)
    
    group.add_argument(
        "-b","--baudrate",
        nargs='?',
        type=int,
        help="set baud rate, default: %(default)s",
        default=default_baudrate)
    
    group.add_argument(
        "--rtscts",
        action="store_true",
        help="enable RTS/CTS flow control (default on)",
        default=True)

    group = parser.add_argument_group("data handling")

    group.add_argument(
        "--encoding",
        dest="serial_port_encoding",
        metavar="CODEC",
        help="set the encoding for the serial port (e.g. hexlify, Latin1, UTF-8), default: %(default)s",
        default='UTF-8')

    group.add_argument(
        "--eol",
        choices=['CR', 'LF', 'CRLF'],
        type=lambda c: c.upper(),
        help="end of line mode (default LF)",
        default='LF')
        
    group = parser.add_argument_group("run mode")
    
#    group.add_argument(
#        "-i","--inline",
#        action="store_true",
#        help="run program with settings set by program arguments (or default), write output to the file, and exit", 
#        default=False)

    group.add_argument(
        "-v","--visa",
        action="store_true",
        help="connect by VISA drivers", 
        default=False) 
    args = parser.parse_args()


    if args.visa == True:
        visa_reference = VISArm()
        ports = visa_reference.ask_for_ports()
    else:
        ports = ask_for_ports()

        
    if args.port is None or args.port == '?':
        print('\n--- Available ports:')
        for n in range(len(ports)):
            print('--- {:2} : {:20} '.format(n+1, ports[n]))
        print('Use: -p \'port index or full name\'')
        sys.exit(0)
    try:
        index = int(args.port) - 1
        if not 0 <= index < len(ports):
            print('--- Invalid index!\n')
            sys.exit(1)
    except ValueError:
        pass
    else:
        args.port = ports[index]

#    ta funkcja zostala napisana aby nie dopuscic do tego by VISA laczyla sie przez port COM - wywala blad. 
#    zamiast tego program laczy sie z COM przez pyserial  
    if args.visa is True:
        if args.port.upper().find('ASRL') != -1:
            args.visa = False
            args.port='COM'+args.port[4]
        if args.port.upper().find('COM') != -1:
            args.visa = False

    if args.visa is True:
        try:
            connection_instance = visa_reference.rm.open_resource(args.port)	
        except visa.VisaIOError as e:
            parser.error('could not open port {}: {}\n'.format(repr(args.port), e))
    else:
        try:
            connection_instance = serial.serial_for_url(
                args.port,
                args.baudrate,
                parity='N',
                rtscts=args.rtscts,
                xonxoff=False,
                timeout = 3, # czy tu ma byæ 3000?
                do_not_open=True,
		write_timeout=3)
            
            connection_instance.open()
        
        except serial.SerialException as e:
            parser.error('could not open port {}: {}\n'.format(repr(args.port), e))
            
        
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    dialog = Dialog(connection_instance, args )
    dialog.start()
    dialog.get_waveform()
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
if __name__ == '__main__':
    main()

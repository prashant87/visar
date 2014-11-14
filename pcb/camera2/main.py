from __future__ import division

import itertools
import math

from autoee import Net, Bus
from autoee import kicad, bom, easypart, landpattern, model, util, harnesses
from autoee.units import INCH, MM
from autoee.components import resistor, capacitor

from autoee_components.mounting_hole import mounting_hole
from autoee_components.on_semiconductor import NOIV1SE1300A_QDC
from autoee_components.molex import _71430, _1050281001
from autoee_components.sunex import CMT821
from autoee_components.stmicroelectronics.STM32F103TB import STM32F103TB
from autoee_components.texas_instruments.DS10BR150 import DS10BR150TSD
from autoee_components.xilinx.XC2C64A import XC2C64A_5QFG48C
from autoee_components.vishay_semiconductors.VSMY7850X01 import VSMY7850X01
from autoee_components.rohm_semiconductor import BUxxTD3WG

'''
TODO

buffers could use incoming 3.3v instead of regulated?

LED
    LED drivers

power
    decoupling caps everywhere
    connect regulators to microcontroller for sequencing

thermal
    ???

IMU/barometer
    need to insert

pins
    12 free after LVDS connected
        3 SPI
        4 CS
        1 LED
        4 left
'''

digilent_vhdci = _71430._71430_0101('''
    IO1_P GND IO2_P IO3_P GND IO4_P IO5_P GND IO6_P IO7_P GND IO8_P IO9_P GND CLK10_P VCC VU
    VU VCC CLK11_P GND IO12_P IO13_P GND IO14_P IO15_P GND IO16_P IO17_P GND IO18_P IO19_P GND IO20_P
    
    IO1_N GND IO2_N IO3_N GND IO4_N IO5_N GND IO6_N IO7_N GND IO8_N IO9_N GND CLK10_N VCC VU
    VU VCC CLK11_N GND IO12_N IO13_N GND IO14_N IO15_N GND IO16_N IO17_N GND IO18_N IO19_N GND IO20_N
'''.split(), 'SHIELD')

lepton = _1050281001._1050281001('''
    GND GPIO3 GPIO2 GPIO1 GPIO0 GND VDDC GND
    GND GND SPI_MOSI SPI_MISO SPI_CLK SPI_CS_L GND VDDIO
    NC GND VDD GND SCL SDA PWR_DWN_L RESET_L
    GND MASTER_CLK GND MIPI_CLK_N MIPI_CLK_P GND MIPI_DATA_N MIPI_DATA_P
'''.split())

def camera(prefix, gnd, vcc3_3, vcc1_8, spi_bus, clock_in, clock, douts, sync):
    cs_n = Net(prefix+'cs_n')
    
    douts = list(douts)
    assert len(douts) == 4
    
    ibias_master = Net(prefix+'IBIAS')
    yield resistor.resistor(47e3)(prefix+'R1', A=ibias_master, B=gnd) # gnd_33
    
    triggers = [Net(prefix+'trigger%i' % (i,)) for i in xrange(3)]
    monitors = [Net(prefix+'monitor%i' % (i,)) for i in xrange(2)]
    
    reset_n = Net(prefix+'reset_n')
    
    
    yield NOIV1SE1300A_QDC.NOIV1SE1300A_QDC(prefix+'U1',
        vdd_33=vcc3_3,
        gnd_33=gnd,
        vdd_pix=vcc3_3, # XXX filter separately?
        gnd_colpc=gnd,
        vdd_18=vcc1_8,
        gnd_18=gnd,
        
        mosi=spi_bus.MOSI,
        miso=spi_bus.MISO,
        sck=spi_bus.SCLK,
        ss_n=cs_n,
        
        clock_outn=clock.N,
        clock_outp=clock.P,
        doutn0=douts[0].N,
        doutp0=douts[0].P,
        doutn1=douts[1].N,
        doutp1=douts[1].P,
        doutn2=douts[2].N,
        doutp2=douts[2].P,
        doutn3=douts[3].N,
        doutp3=douts[3].P,
        syncn=sync.N,
        syncp=sync.P,
        
        lvds_clock_inn=clock_in.N,
        lvds_clock_inp=clock_in.P,
        
        clk_pll=gnd, # XXX maybe do put a 62 MHz clock here?
        
        ibias_master=ibias_master,
        
        trigger0=triggers[0],
        trigger1=triggers[1],
        trigger2=triggers[2],
        monitor0=monitors[0],
        monitor1=monitors[1],
        
        reset_n=reset_n,
    )
    yield CMT821.CMT821(prefix+'M1')
    yield resistor.resistor(100, error=0, tolerance=0.01)(prefix+'R2', A=clock_in.P, B=clock_in.N)

@util.listify
def main():
    for i in xrange(4):
        yield mounting_hole('M%i' % (i,))
    
    gnd = Net('gnd')
    
    vcc5in = Net('vcc5in')
    vcc3_3in = Net('vcc3_3in')
    
    vcc1_2 = Net('vcc1_2') # thermal (110mA*2)
    vcc1_8 = Net('vcc1_8') # CMOS (75mA*2), CPLD (17.77mA) - needs to be switched, in part
    vcc2_8 = Net('vcc2_8') # thermal (16mA*2)
    vcc3_0 = Net('vcc3_0') # CPLD, thermal (4mA*2), ARM, CMOS ((130+2.5mA)*2) - needs to be switched, in part
    
    for i, (n, v) in enumerate({vcc1_2: 1.2, vcc1_8: 1.8, vcc2_8: 2.8, vcc3_0: 3.0}.iteritems()):
        yield BUxxTD3WG.by_voltage[v]('REG%i' % (i,),
            VIN=vcc3_3in,
            GND=gnd,
            nSTBY=vcc3_3in,
            VOUT=n,
        )
    
    yield capacitor.capacitor(10e-6, voltage=5*2)('C1', A=vcc3_0, B=gnd)
    
    spi_bus = harnesses.SPIBus(MISO=Net('MISO'), MOSI=Net('MOSI'), SCLK=Net('SCLK'))
    i2c_bus = harnesses.I2CBus(SDA=Net('SDA'), SCL=Net('SCL'))
    
    shield = Net('shield')
    yield capacitor.capacitor(1e-9, voltage=250)('C2', A=shield, B=gnd)
    yield resistor.resistor(1e6)('R2', A=shield, B=gnd)
    
    pairs = {i: harnesses.LVDSPair.new('pair%i' % (i,)) for i in xrange(1, 20+1)}
    yield digilent_vhdci('P1',
        GND=gnd,
        SHIELD=shield,
        VU=vcc5in,
        VCC=vcc3_3in,
        CLK10_P=pairs[10].P, CLK10_N=pairs[10].N,
        CLK11_P=pairs[11].P, CLK11_N=pairs[11].N,
        **dict(
            [('IO%i_P' % (i,), pairs[i].P) for i in range(1, 9+1)+range(12, 20+1)] +
            [('IO%i_N' % (i,), pairs[i].N) for i in range(1, 9+1)+range(12, 20+1)])
    )
    
    bufout = {}
    for i in [2, 3, 4, -5, -6, -10, 11, 15, 16, -17, 18, 19]:
        swap = i < 0
        i = abs(i)
        bufout[i] = harnesses.LVDSPair.new('out%i' % (i,))
        a = bufout[i].swapped if swap else bufout[i]
        b = pairs[i].swapped if swap else pairs[i]
        yield capacitor.capacitor(100e-9)('B%iC' % (i,), A=vcc3_3in, B=gnd)
        yield DS10BR150TSD('B%i' % (i,),
            GND=gnd,
            INn=a.N,
            INp=a.P,
            VCC=vcc3_3in,
            OUTp=b.P,
            OUTn=b.N,
        )
    
    bufin = {}
    for i in [-1, 20]:
        swap = i < 0
        i = abs(i)
        bufin[i] = harnesses.LVDSPair.new('out%i' % (i,))
        a = pairs[i].swapped if swap else pairs[i]
        b = bufin[i].swapped if swap else bufin[i]
        yield capacitor.capacitor(100e-9)('B%iC' % (i,), A=vcc3_3in, B=gnd)
        yield DS10BR150TSD('B%i' % (i,),
            GND=gnd,
            INn=a.N,
            INp=a.P,
            VCC=vcc3_3in,
            OUTp=b.P,
            OUTn=b.N,
        )
    
    yield camera('C1',
        gnd=gnd,
        vcc1_8=vcc1_8,
        vcc3_3=vcc3_0,
        spi_bus=spi_bus,
        clock_in=bufin[1].swapped,
        douts=[bufout[6], bufout[5], bufout[4].swapped, bufout[3].swapped],
        sync=bufout[2].swapped,
        clock=bufout[10],
    )
    yield camera('C2',
        gnd=gnd,
        vcc1_8=vcc1_8,
        vcc3_3=vcc3_0,
        spi_bus=spi_bus,
        clock_in=bufin[20],
        douts=[bufout[15], bufout[16], bufout[17].swapped, bufout[18]],
        sync=bufout[19],
        clock=bufout[11],
    )
    
    lepton1_cs_n = Net('lepton1_cs_n')
    yield lepton('T1',
        GND=gnd,
        VDDC=vcc1_2,
        SPI_MOSI=spi_bus.MOSI,
        SPI_MISO=spi_bus.MISO,
        SPI_CLK=spi_bus.SCLK,
        SPI_CS_L=lepton1_cs_n,
        VDDIO=vcc3_0,
        VDD=vcc2_8,
        SCL=i2c_bus.SCL,
        SDA=i2c_bus.SDA,
        #PWR_DWN_L
        #RESET_L
        #MASTER_CLK
    )
    
    lepton2_cs_n = Net('lepton2_cs_n')
    yield lepton('T2',
        GND=gnd,
        VDDC=vcc1_2,
        SPI_MOSI=spi_bus.MOSI,
        SPI_MISO=spi_bus.MISO,
        SPI_CLK=spi_bus.SCLK,
        SPI_CS_L=lepton2_cs_n,
        VDDIO=vcc3_0,
        VDD=vcc2_8,
        SCL=i2c_bus.SCL,
        SDA=i2c_bus.SDA,
        #PWR_DWN_L
        #RESET_L
        #MASTER_CLK
    )
    
    jtag = harnesses.JTAG.new('mc_')
    
    yield STM32F103TB('U1',
        VSS=gnd,
        BOOT0=gnd,
        NRST=vcc3_0,
        VDD=vcc3_0,
        
        PA13=jtag.TMS,
        PA14=jtag.TCK,
        PA15=jtag.TDI,
        PB3=jtag.TDO,
        PB4=jtag.TRST,
    )
    
    cpld_jtag = harnesses.JTAG.new('cpld_')
    
    yield XC2C64A_5QFG48C('U2',
        GND=gnd,
        VCC=vcc1_8,
        
        VAUX=vcc3_0, # XXX
        TDI=cpld_jtag.TDI,
        TDO=cpld_jtag.TDO,
        TCK=cpld_jtag.TCK,
        TMS=cpld_jtag.TMS,
        
        VCCIO1=vcc3_0,
        #IO1_11 # GCKs
        #IO1_12
        #IO1_13
        
        VCCIO2=vcc3_0,
        IO2_2=pairs[7].N,
        IO2_1=pairs[7].P,
        IO2_48=pairs[8].N,
        IO2_47=pairs[8].P,
        IO2_46=pairs[9].P,
        IO2_45=pairs[9].N,
        IO2_44=pairs[12].N,
        IO2_43=pairs[12].P,
        IO2_39=pairs[13].P,
        IO2_38=pairs[13].N,
        IO2_37=pairs[14].P,
        IO2_36=pairs[14].N,
    )
    
    for i in xrange(4):
        yield VSMY7850X01('D%i' % (i,),
        )
    

desc = main()
kicad.generate(desc, 'kicad')
bom.generate(desc, 'bom')

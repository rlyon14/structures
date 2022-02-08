
from numpy import uint8, uint16, float64, int16, uint32, string_
import numpy as np
from structures import Struct, Packet, ldarray, lddim
from enum import Enum


dim = lddim(a=[1,2], b=['data1', 'data2', 'data3'])

data = ldarray(dim=dim)


ld = ldarray([[10, 11, 12], [13, 14, 15]], dim=dim, dtype=np.float64)


class example(Struct):
    a = np.array(["Item", 'Item'], dtype='S4')
    b = np.uint32(0xFFA)
    c = np.arange(0, 10)


ex = example()
print(ex)
data[0] = 5

data[{'freq_ghz':2}]

data.dim


def test(**kwargs):
    print(kwargs)
    print('t', kwargs.pop('idx', None))
    print(kwargs)
    
    
def round_to_float(value, multiple=1):
    """ Rounds value to nearest floating point multiple"""

    invmul = 1/multiple

    r1 = value/multiple
    w = r1//1
    w = np.where((r1%1) >= 0.5, w+1, w)
    
    mlog10 = np.log10(multiple)
    
    if mlog10 > 0:
        return w/invmul
    else:
        return np.around(w/invmul, int(np.abs(mlog10)))
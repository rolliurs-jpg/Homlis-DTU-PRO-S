import struct
import unittest
from unittest.mock import patch
from dtu_control import DtuControl

class FakeSocket:
 def __init__(self,data):self.data=data;self.sent=b''
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def settimeout(self,n):pass
 def sendall(self,b):self.sent=b
 def recv(self,n):
  b=self.data[:min(n,2)];self.data=self.data[len(b):];return b

class DtuTests(unittest.TestCase):
 def frame(self,data,unit=1):return struct.pack('>HHHB',17,0,len(data)+1,unit)+data
 def test_fragmented_read(self):
  sock=FakeSocket(self.frame(bytes([3,4])+struct.pack('>HH',90,100)))
  with patch('socket.create_connection',return_value=sock):
   self.assertEqual(DtuControl('host').transaction(3,0xD007,2),[90,100])
 def test_only_temporary_limit_write(self):
  sock=FakeSocket(self.frame(struct.pack('>BHH',6,0xD001,90)))
  with patch('socket.create_connection',return_value=sock):DtuControl('host').request_limit(90,{})
  self.assertEqual(sock.sent[-5:],struct.pack('>BHH',6,0xD001,90))
 def test_reject_bad_unit_and_exception_and_short_registers(self):
  for frame in [self.frame(bytes([3,2,0,100]),unit=2),self.frame(bytes([0x83,1])),self.frame(bytes([3,2,0,100]))]:
   with patch('socket.create_connection',return_value=FakeSocket(frame)):
    with self.assertRaises(ValueError):DtuControl('host').transaction(3,0xD007,2)
 def test_reject_bad_limits(self):
  for n in [True,1,101,20.5]:
   with self.assertRaises(ValueError):DtuControl('host').request_limit(n,{})
 def test_matching_ports_do_not_write(self):
  d=DtuControl('host')
  with patch.object(d,'transaction') as request:
   d.request_limit(100,dict(state='online',port_limits_pct=[100]*4));request.assert_not_called()

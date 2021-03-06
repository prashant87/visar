# communication module (client/server), get/send audio
import SocketServer
import socket
import pyaudio
import threading
import time

CHUNK = 16     # number of frames/packet
SAMPLE_RATE = 11025 # sending frequency, mic samples at 44100?
PORT = 9001 # application port number (likely to change)
  
# get sound gets audio from socket and plays over speakers   
def get_sound(stream, sock, bytes, kill_flag):
  sock.settimeout(2) # set a timeout
  try: data = sock.recv(bytes) # get initial packet
  except: data = '' # skip the loop if it failed
  while data != '':  # go while we're getting data
    stream.write(data) # write audio to speakers
    try: data = sock.recv(bytes) # read from socket
    except: break # stream closed
    if(kill_flag.is_set()): break  # thread is kill
  kill_flag.set() # client disconnected, set flag
  stream.stop_stream() # stop streaming
  stream.close() # cleanup
    
# send sound gets audio from mic and sends over socket   
def send_sound(stream, sock, bytes, kill_flag):
  data = stream.read(bytes) # get inital data
  while data != '': # go while we're getting data
    try: sock.send(data) # send the data over socket
    except: break # stream closed
    data = stream.read(bytes) # get audio from mic
    if(kill_flag.is_set()): break  # thread is kill
  kill_flag.set() # client disconnected, set flag
  stream.stop_stream() #cleanup
  stream.close()

# manage the connection status information
class Connection_Status:
  def __init__(self, local_name):
    self.connected = False
    self.remote_name = ''
    self.local_name = local_name
    self.direction = True # bidrectional=true, inputonly=false
  def connect(self, name, outputting=True):
    self.connected = True
    self.remote_name = name
    self.direction = outputting
  def disconnect(self):
    self.connected = False
    self.remote_name = ''
   
class Audio_Manager:
  def __init__(self, controller, kill_flag=None):
    if(controller): 
      self.connection = Connection_Status(controller.book.name)
      self.shutdown = controller.kill_flag
    else: 
      self.connection = Connection_Status('anonymous')
      self.shutdown = threading.Event()
    if(kill_flag): self.kill_flag = kill_flag
    else: self.kill_flag = threading.Event()
    self.p = pyaudio.PyAudio()
    # create and configure a server socket
    try:
      self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.server.bind(('',PORT))
      self.server.listen(0)
      self.server.settimeout(2) # 2sec timeout
    except: 
      print 'failed to connect'
      self.server = None
    

  def connect(self, hostname):
    if(self.connection.connected): print 'Error, already connected'
    else:
      if not self.server: # make sure server is running
        # create and configure a server socket
        try:
          self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.server.bind(('',PORT))
          self.server.listen(1)
          self.server.settimeout(2) # 2sec timeout
        except: 
          print 'failed to connect'
          self.server = None
      if self.server: # make sure connection was successful
        t = threading.Thread(target=self.start_client,args=(hostname,))
        t.start()

  def disconnect(self):
    self.kill_flag.set() # signal thread to die
    self.connection.disconnect() # update status

  def start_server(self):
    try: sock, addr = self.server.accept()
    except: return # retry loop on timeout (check for kills)
  
    # get data about communcation direction
    if(sock.recv(1) == 'S'): output = False
    else: output = True
    
    # get the client's name, then send ours
    name = ''
    data = sock.recv(1)
    while not '\n' == data:
      name += data # append char to username
      data = sock.recv(1)
    self.connection.connect(name, output) # update connection status
    for c in self.connection.local_name:
      sock.send(c) # send our name one char at a time
    sock.send('\n') # send newline to indicate end
    
    print 'connected to ' + name
    
    # get information about client audio format
    rate = ord(sock.recv(1)) << 8 # get the samle rate, byte 1
    rate = rate | ord(sock.recv(1)) # get byte 2 of sample rate
    channels = ord(sock.recv(1)) # get the number of channels
    width = ord(sock.recv(1)) # get the samle width
    
    # setup the playback stream/thread
    speaker_stream = self.p.open(format = pyaudio.paInt16,
              channels = channels,
              rate = rate,
              output = True)          
    bytes = CHUNK * channels * width              
    in_thread = threading.Thread(target=get_sound, args=(speaker_stream,sock,bytes,self.kill_flag))
    in_thread.start()
    
    # setup mic stream/thread
    if(output):
      mic_stream = self.p.open(format = pyaudio.paInt16,
                         channels = channels,
                         rate = rate,
                         input = True)
      out_thread = threading.Thread(target=send_sound, args=(mic_stream,sock,bytes,self.kill_flag))
      out_thread.start()
    
    while not (self.kill_flag.is_set() or self.shutdown.is_set()):
      time.sleep(0.1)
    
    self.kill_flag.set() # signal threads to die
    self.connection.disconnect() # signal the disconnect
    sock.close()
    print 'disconnected'
    
  # wrapper runs threads forever
  def start_server_loop(self):
    while not self.shutdown.is_set() and self.server: 
      self.start_server() # accept connections forever    
  
  # create server in seperate thread    
  def start_server_thread(self):
    t = threading.Thread(target=self.start_server_loop)
    t.start()
    
  # cleanup pyaudido (streams will timeout)
  def cleanup(self):
    time.sleep(2)
    self.p.terminate()  
    
  def start_client(self, hostname):
    # setup the connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # get a socket
    sock.connect((hostname,PORT)) # connect to host
    
    sock.send('B') # indicate biderictional communication
    
    # get the client's name, then send ours
    name = ''
    for c in self.connection.local_name:
      sock.send(c) # send our name one char at a time
    sock.send('\n') # send newline to indicate end
    data = sock.recv(1)
    while not '\n' == data:
      name += data # append char to username
      data = sock.recv(1)    
    self.connection.connect(name) # update connection status

    print 'connected to ' + name
    
    # configure the settings
    rate = SAMPLE_RATE # store the sample rate
    sock.send(chr(rate >> 8)) # send 1st byte of sample rate
    sock.send(chr(rate & 0xFF)) # send 2nd byte of sample rate
    sock.send(chr(1)) # send the number of channels (1=mono)
    sock.send(chr(1)) # send the samle width (16-bit is 1)

    # start sending data
    # setup the playback stream/thread
    speaker_stream = self.p.open(format = pyaudio.paInt16,
              channels = 1,
              rate = SAMPLE_RATE,
              output = True)          
    bytes = CHUNK * 1 * 1 # num frames * channels * width
    in_thread = threading.Thread(target=get_sound, args=(speaker_stream,sock,bytes,self.kill_flag))
    in_thread.start()
      
    # setup mic stream/thread
    mic_stream = self.p.open(format = pyaudio.paInt16,
                       channels = 1,
                       rate = SAMPLE_RATE,
                       input = True)
    out_thread = threading.Thread(target=send_sound, args=(mic_stream,sock,bytes,self.kill_flag))
    out_thread.start()
      
    while not (self.kill_flag.is_set() or self.shutdown.is_set()):
      time.sleep(0.1)
      
    self.kill_flag.set() # signal threads to die (redundant)
    sock.close() # close the socket
    self.connection.disconnect()
    print 'disconnected'
    
    
if __name__ == '__main__':
  server = raw_input("Start as Server or Client (S/C):") == 'S'
  manager = Audio_Manager(None, threading.Event())
  if(server): manager.start_server()
  else: manager.start_client(raw_input("Enter server address: "))
    
  

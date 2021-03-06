# Use prebuilt deocde library to play test file over socket
import socket
import decoder

FILENAME = 'test.mp3'
CHUNK = 1024
PORT = 19101

def send_sound():
  # setup the connection
  hostname = raw_input("Enter server address: ")
  f_in = decoder.open(FILENAME)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # get a socket
  sock.connect((hostname,PORT)) # connect to remote host
  sock.send('S') # indicate that we wish to send data only
  sock.send('\n') # send newline to indicate lack of name
  while not '\n' == sock.recv(1):
    a = 1

  rate = f_in.getframerate() # store the sample rate
  sock.send(chr(rate >> 8)) # send 1st byte of sample rate
  sock.send(chr(rate & 0xFF)) # send 2nd byte of sample rate
  sock.send(chr(f_in.getnchannels())) # send the number of channels
  sock.send(chr(f_in.getsampwidth())) # send the samle width

  # start sending data
  bytes = f_in.readframes(CHUNK)
  while bytes != '':
    sock.send(bytes)
    bytes = f_in.readframes(CHUNK)
  sock.close()
  f_in.close()
    
  
if __name__ == '__main__':
  send_sound()

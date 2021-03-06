# Makefile for the audio controller, requires pthread and alsa libraries

CC=gcc
CFLAGS=-c 
LIBS=-lasound -lpthread -lspeex -lopus
LINK_PSPHINX=`pkg-config --cflags --libs pocketsphinx sphinxbase`
COMP_PSPHINX=-DMODELDIR=\"`pkg-config --variable=modeldir pocketsphinx`\"

all: voice_control

test: audio_controller.o buffer.o comms.o sound.o encode.o test.o
	$(CC) test.o audio_controller.o buffer.o comms.o sound.o encode.o -o audio $(LIBS)

opus: audio_controller.o buffer.o comms.o sound.o encode_opus.o test.o
	$(CC) test.o audio_controller.o buffer.o comms.o sound.o encode_opus.o -o audio $(LIBS)

test.o: test.c
	$(CC) $(CFLAGS) test.c

voice_control: audio_controller.o buffer.o comms.o sound.o encode.o voice_control.o
	$(CC) voice_control.o audio_controller.o buffer.o comms.o sound.o encode.o -o audio $(LIBS) $(LINK_PSPHINX)

voice_control.o: voice_control.c
	$(CC) $(CFLAGS) voice_control.c $(COMP_PSPHINX) $(LINK_PSPHINX)

audio_controller.o: audio_controller.c
	$(CC) $(CFLAGS) audio_controller.c

buffer.o: buffer.c
	$(CC) $(CFLAGS) buffer.c

comms.o: comms.c
	$(CC) $(CFLAGS) comms.c

sound.o: sound.c
	$(CC) $(CFLAGS) sound.c

encode.o: encode.c
	$(CC) $(CFLAGS) encode.c
	
encode_opus.o: encode_opus.c
	$(CC) $(CFLAGS) encode_opus.c

clean: 
	rm *.o audio

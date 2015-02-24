/* 
 * File handles sound processing (start/stop/buffer structure)
 * TODO: callbacks, multiplexing, volume
 */

//library includes 
#include <alsa/asoundlib.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

//project includes
#include "audio_controller.h"
#include "buffer.h"
#include "sound.h"

//predefined constants (basically guesses)
#define MAX_BUFFER 20   //total ring buffer size
#define MIN_BUFFER 10   //buffered frames needed to initiate playback

//externally defined global variables
int speaker_kill_flag;
int mic_kill_flag;

//open a sound device with specified period, rate, channels(0=mono,1=stereo or MONO_SOUND/STEREO_SOUND) 
//  and direction(0=playback,1=capture), returns the buffer (also PLAYBACK_DIR/CAPTURE_DIR)
snd_pcm_t* start_snd_device(size_t period, unsigned int rate, int stereo, int direction){
  //Open PCM device for playback/capture, check for errors
  snd_pcm_t *pcm_handle; //handler struct
  int dir = (direction)? SND_PCM_STREAM_CAPTURE:SND_PCM_STREAM_PLAYBACK;
  int rc = snd_pcm_open(&pcm_handle, "default",dir, 0);
  if (rc < 0){ //make sure it landed
    fprintf(stderr,"unable to open pcm device: %s\n",snd_strerror(rc));
    return 0; //return null pointer
  }

  //Setup the hardware parameters
  snd_pcm_hw_params_t *params;  //create pointer
  snd_pcm_hw_params_alloca(&params); //allocate struct
  snd_pcm_hw_params_any(pcm_handle, params); //fill with defaults
  snd_pcm_hw_params_set_access(pcm_handle, params, SND_PCM_ACCESS_RW_INTERLEAVED); //interleaved mode
  snd_pcm_hw_params_set_format(pcm_handle, params, SND_PCM_FORMAT_S16_LE); //signed 16-bit LE
  snd_pcm_hw_params_set_channels(pcm_handle, params, (stereo+1)); //stereo mode
  unsigned int rate2 = rate; //copy rate (will be overwritten on mismatch)
  int err_dir = 0; //try to set rate exactly
  snd_pcm_hw_params_set_rate_near(pcm_handle, params, &rate2, &err_dir); //get closest match
  if(rate != rate2) printf("Rate mismatch, %d give, %d set\n",rate,rate2);
  size_t frames = period; //once again,copy value in case of mismatch
  snd_pcm_hw_params_set_period_size_near(pcm_handle, params, &period, &dir); //set the period
  if(period != frames) printf("Period size mismatch, %d given, %d set", (int)period, (int)frames);
 
  //Write the parameters to the driver
  rc = snd_pcm_hw_params(pcm_handle, params);
  if (rc < 0){ //make sure it landed
    fprintf(stderr, "unable to set hw parameters: %s\n", snd_strerror(rc));
    return 0; //return null
  }
  
  return pcm_handle;
}

//spawn a speaker thread
audiobuffer* create_speaker_thread(snd_pcm_t pcm_handle){
  //create a buffer struct (frame size is frames/period * channels * sample width)
  audiobuffer* buffer = create_buffer(frames, 2*(stereo+1), MAX_BUFFER); //16-bit channels
  
  //package the information for the thread
  spk_pcm_package* pkg = (spk_pcm_package*)malloc(sizeof(spk_pcm_package));
  pkg->pcm_handle = pcm_handle;
  pkg->buffer = buffer;
  pkg_out = (void*)pkg;

  //create thread and send it the package
  pthread_t thread; //thread handler
  rc = pthread_create(&thread, NULL, (direction)? mic_thread : speaker_thread, (void*)pkg);
  if (rc) printf("ERROR: Could not create device thread, rc=%d\n", rc); //print errors
  
  return buffer; //return the device's audio buffer
}

void create_speaker_thread(snd_pcm_t pcm_handle, size_t period, size_t frame_size){
  //allocate a microphone buffer (just one period)
  char* buffer = (char*)malloc(period*frame_size);
  
  //finish populating the sender info
  sender->buf = buffer;
  sender->len = frames*2*(stereo+1);
  
  //store in package
  mic_pcm_package* pkg = (mic_pcm_package*)malloc(sizeof(mic_pcm_package));
  pkg->pcm_handle = pcm_handle; //store the device handler
  pkg->buffer = period; //store the buffer pointer
  pkg->period = frame_size; //store the period size
  pkg->snd_handle = sender; //store the handler

  //create thread and send it the package
  pthread_t thread; //thread handler
  rc = pthread_create(&thread, NULL, (direction)? mic_thread : speaker_thread, (void*)pkg);
  if (rc) printf("ERROR: Could not create device thread, rc=%d\n", rc); //print errors
}

void *speaker_thread(void* ptr){
  audiobuffer* buf = ((spk_pcm_package*)ptr)->buffer; //cast pointer, get buffer struct
  snd_pcm_t* speaker_handle = ((spk_pcm_package*)ptr)->pcm_handle; //cast pointer, get device pointer
  free(ptr); //free message memory
  speaker_kill_flag = 0;  //reset the kill signal (smallish race condition, not concerned)
    
  char started = 0;  //track when to start reading data
  while(!global_kill && !speaker_kill_flag) { //loop until program stops us
    //wait until adequate buffer is achieved
    if((!started && BUFFER_SIZE(*buf) < (MIN_BUFFER)) || BUFFER_EMPTY(*buf)){
      started = 0;  //stop if already started
      printf("Speaker Waiting\n");
      usleep(PERIOD_UTIME/2); //wait to reduce CPU usage
      continue;     //don't start yet
    } else started = 1; //indicate that we've startd
    
    //write data to speaker buffer, check responses
    int rc = snd_pcm_writei(speaker_handle, GET_QUEUE_HEAD(*buf), buf->period);
    INC_QUEUE_HEAD(*buf);
    if (rc == -EPIPE){ //Catch underruns (not enough data)
      fprintf(stderr, "underrun occurred\n");
      snd_pcm_prepare(speaker_handle); //reset speaker
    } else if (rc < 0) fprintf(stderr, "error from writei: %s\n", snd_strerror(rc)); //other errors
    else if (rc != (int)buf->period) fprintf(stderr, "short write, write %d frames\n", rc);
    else fprintf(stderr, "audio written correctly\n");
  }

  //TODO: find way to combine multiple audio streams
  
  // notify kernel to empty/close the speakers
  snd_pcm_drain(speaker_handle);  //finish transferring the audio
  snd_pcm_close(speaker_handle);  //close the device
  //free_buffer(buf); //free the audiobuffer
  printf("Audio Controller: Speaker Thread shutdown\n");
  
  pthread_exit(NULL); //exit thread safetly
}

void *mic_thread(void* ptr){
  char* buf = ((mic_pcm_package*)ptr)->buffer; //cast pointer, get buffer struct
  size_t preiod  = ((mic_pcm_package*)ptr)->period;  //cast pointer, get period size
  sender_handle* snd_handle = ((mic_pcm_package*)ptr)->snd_handle; //cast pointer, get handler
  snd_pcm_t* mic_handle = ((mic_pcm_package*)ptr)->pcm_handle; //cast pointer, get device pointer
  free(ptr); //clean up memory
  mic_kill_flag = 0;  //reset the kill signal (smallish race condition, not concerned)
  
  while(!global_kill && !mic_kill_flag) { //loop until program stops us
    //write data to speaker buffer, check response codes
    int rc = snd_pcm_readi(mic_handle, buf, period);
    printf("Mic Data Read\n");
    if (rc == -EPIPE) { //catch overruns (too much data for buffer)
      fprintf(stderr, "overrun occurred\n");
      snd_pcm_prepare(mic_handle); //reset handler
    //other errors
    } else if (rc < 0) fprintf(stderr, "error from read: %s\n", snd_strerror(rc));
    else if (rc != (int)buf->period) fprintf(stderr, "short read, read %d frames\n", rc);
    else{
      //TODO: send multiple packets to places
      send_packet(snd_handle); //if it worked, send the packet
    }
  }

  // notify kernel to empty/close the speakers, free the buffer
  snd_pcm_drain(mic_handle);
  snd_pcm_close(mic_handle);
  destroy_sender(snd_handle); //cleans up the sender socket and buffer
  printf("Audio Controller: Microphone Thread shutdown\n");
  
  pthread_exit(NULL); //exit thread safetly
}

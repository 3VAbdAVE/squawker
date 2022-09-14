import contextlib
import wave
import numpy as np
import pyaudio

"""I'm not smart enough for this, I modified it from internet tutorials involving
driving LED lights. I just s/LED/Motor, played with the variables, and bob's your uncle.
"""

class Squawk:
    """The functions in this class play a wav file through the raspberry Pi's
    audio system, and perform some analysis of the wav data to determine when
    to run/stop the beak motor and operate the body motor based on the audio
    file's amplitude. This avoids needing to volume-normalize or otherwise 
    dick around with wav files.
    """
    def __init__(self, beak, body) -> None:
        # I don't think there's any reason to change CHUNK.
        # A bigger value *might* give an average that works better
        # with the sloppy gearing, but it doesn't seem to matter.
        self.CHUNK = 2048
        self.beak = beak
        self.body = body
        
        
# I really don't understand decorators
# I think this allows the pyaudio wave data to be "yielded"
# as a generator. I haven't the slightest clue how I'd know 
# to do this without stealing internet code.
    @contextlib.contextmanager
    def _audio_stream(self, wf):
        """Passes the wave data from the object to a pyaudio stream
        resulting in audio output

        Args:
            wf (wave): An open wave file

        Yields:
            pyaudio: The wave file data output as an audio stream
        """
        p = pyaudio.PyAudio()

        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True
                        )
        try:
            yield stream
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def _getwavefmt(self, wf):
        """PyAudio needs to know how the wav data is formatted in order 
        to play each chunk. It also allows numpy to process the data 
        for the amplitude calculation. It seems like this "width" is the
        key thing they need for wav data, but idk.

        Args:
            wf (wave): A PyAudio opened Wave object 

        Returns:
            int: Format width of the wave object.
        """
        pyaudio_format = pyaudio.get_format_from_width(wf.getsampwidth())
        print(f"format: {pyaudio_format}")
        if pyaudio_format == pyaudio.paInt16:
            return np.int16
        else:
            print("For the moment, only support 16 bit format")
            #Not entirely clear on what this means, but it doesn't work
            # if the width doesn't match the format.
            return np.int8
        
    def _squawk_io(self, np_data):
        """Analyzes the CHUNK of the wav file to determine
        the average amplitude of the audio. If above a 
        threshhold, activate the relevant motors.

        Args:
            np_data (wave data): one of the wav chunks

        Returns:
            float: the calculated average amplitude of the chunk
        """
        mean = np.mean(np.absolute(np_data))
        avg = float(mean) / 50
        #print(avg)
        if avg > 2:
            self.body.body_motor.throttle = 1
            if avg > 15:
                self.beak.open_beak()
            else:
                self.beak.close_beak()
        else:
            self.body.body_motor.throttle = 0
        return avg

    def run(self, filename):
        """Plays the wave file and sends it to the motor IO function.

        Args:
            filename (string): Path to the wave file
            chunk (int): Wave data chunk size
        """
        wf = wave.open(filename, 'rb')
        #wf: PyAudio Wave file
        chunk = self.CHUNK
        width = self._getwavefmt(wf)
        
        # Ok, so using the contextlib data yield allows the stream to be read
        # chunk by chunk and then does the appropriate file handling? 
        with self._audio_stream(wf) as stream:
            data = wf.readframes(chunk)
            arr = []
            stream.start_stream()
            while len(data) > 0:
                stream.write(data, chunk)
                arr.append(self._squawk_io(np.frombuffer(data, dtype=width)))
                data = wf.readframes(chunk)
            self.beak.close_beak()
            self.body.body_motor.throttle = 0
            nparr = np.array([arr])
            mn = np.mean(nparr)
            print(f"Mean converted amplitude is: {mn}.")

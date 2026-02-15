from pathlib import Path
from typing import Optional
import pretty_midi
from basic_pitch.inference import predict, Model
from basic_pitch import ICASSP_2022_MODEL_PATH
from music21 import converter, stream, pitch, interval
import os

class TranscriptionService:
    def __init__(self):
        # Load model once at startup
        self.model = Model(ICASSP_2022_MODEL_PATH)

    def transcribe_audio_to_midi(self, audio_path: Path, output_midi_path: Path) -> Optional[Path]:
        """
        Convert audio to MIDI using basic-pitch with violin optimizations.
        """
        try:
            model_output, midi_data, note_events = predict(
                str(audio_path),
                self.model,
                onset_threshold=0.3,
                frame_threshold=0.25,
                minimum_note_length=50.0,
                minimum_frequency=196.0,
                maximum_frequency=1760.0,
                multiple_pitch_bends=False
            )
            midi_data.write(str(output_midi_path))
            return output_midi_path
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None

    def convert_midi_to_musicxml(self, midi_path: Path, output_xml_path: Path) -> Optional[Path]:
        """
        Convert MIDI to MusicXML using music21 with quantization and violin transposition.
        """
        try:
            # 1. Parse with quantization
            s = converter.parse(
                str(midi_path),
                quantizePost=True,
                quarterLengthDivisors=(4, 3)
            )

            # 2. Cleanup notation
            s.makeBeams(inPlace=True)
            s.makeTies(inPlace=True)
            s.makeAccidentals(inPlace=True)

            # 3. Transpose to Violin range (G3-A7)
            # This method needs to be implemented or imported if it was intended to be separate
            # For now, let's keep it simple or assume it's part of the class logic
            # The previous file had _transpose_to_violin_range, let's restore/fix it.
            s = self._transpose_to_violin_range(s)

            # 4. Write to MusicXML
            s.write('musicxml', fp=str(output_xml_path))
            return output_xml_path
        except Exception as e:
            print(f"Error converting to MusicXML: {e}")
            return None

    def _transpose_to_violin_range(self, s: stream.Stream) -> stream.Stream:
        """
        Check pitch range and transpose if necessary.
        Violin Range: G3 (55) to A7 (100)
        """
        try:
            # Get all pitches
            pitches = [n.pitch.midi for n in s.recurse().notes if hasattr(n, 'pitch')]
            if not pitches:
                return s

            min_pitch = min(pitches)
            max_pitch = max(pitches)
            
            # Target range
            MIN_VIOLIN = 55
            MAX_VIOLIN = 100

            transpose_semitones = 0
            
            if min_pitch < MIN_VIOLIN:
                # Too low, shift up
                transpose_semitones = MIN_VIOLIN - min_pitch
            elif max_pitch > MAX_VIOLIN:
                # Too high, shift down
                transpose_semitones = MAX_VIOLIN - max_pitch
            
            if transpose_semitones != 0:
                print(f"Transposing by {transpose_semitones} semitones to fit Violin range.")
                return s.transpose(transpose_semitones)
            
            return s
        except Exception as e:
            print(f"Error during transposition: {e}")
            return s

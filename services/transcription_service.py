from pathlib import Path
from typing import Optional
import pretty_midi
from basic_pitch.inference import predict, Model
from basic_pitch import ICASSP_2022_MODEL_PATH
from music21 import converter, stream, pitch, interval, key, meter, note, chord
import os
import gc

class TranscriptionService:
    def __init__(self):
        # Load model once at startup
        self.model = Model(ICASSP_2022_MODEL_PATH)

    def transcribe_audio_to_midi(self, audio_path: Path, output_midi_path: Path) -> Optional[Path]:
        """
        Convert audio to MIDI using basic-pitch with violin optimizations.
        """
        try:
            # Force garbage collection before heavy operation
            gc.collect()
            
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
            
            # Explicitly delete large objects
            del model_output
            del midi_data
            del note_events
            gc.collect()
            
            return output_midi_path
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            gc.collect()
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

            # Fix for "cannot process a stream that is neither a Measure nor has no Measures"
            # Ensure we have a Score -> Part -> Measure hierarchy
            if not isinstance(s, stream.Score):
                new_score = stream.Score()
                if isinstance(s, stream.Part):
                    new_score.insert(0, s)
                else:
                    # It's a flat stream or something else, wrap in Part
                    p = stream.Part()
                    for element in s:
                        p.insert(element.offset, element)
                    new_score.insert(0, p)
                s = new_score

            # 2. Cleanup notation (makeNotation creates measures, beams, ties)
            # makeNotation works on Parts, so we iterate through parts
            for p in s.parts:
                p.makeNotation(inPlace=True)
                p.makeBeams(inPlace=True)
                p.makeTies(inPlace=True)
                p.makeAccidentals(inPlace=True)

            # 3. Transpose to Violin range (G3-A7)
            # Apply transposition to all parts
            for p in s.parts:
                self._transpose_part_to_violin_range(p)

            # ========== NEW: RIGOROUS CLEANUP PHASE ==========
            print("[CLEANUP] Starting rigorous sheet music cleanup...")
            
            # 1. FORCE 16TH NOTE GRID QUANTIZATION
            # Process all parts to snap notes to rhythmic grid
            try:
                s.quantize(
                    quarterLengthDivisors=[4],  # 16th notes (4 per quarter)
                    processOffsets=True,        # Quantize start times
                    processDurations=True,      # Quantize durations
                    inPlace=True
                )
                print("[CLEANUP] Quantized to 16th-note grid")
            except Exception as q_err:
                print(f"[CLEANUP] Quantization warning: {q_err}")
            
            # 2. REMOVE ARTIFACTS (very short notes)
            # Delete notes shorter than 16th note (0.25 quarter length)
            for p in s.parts:
                notes_to_remove = []
                for element in p.recurse().notesAndRests:
                    if element.duration.quarterLength < 0.25:
                        notes_to_remove.append(element)
                
                for n in notes_to_remove:
                    p.remove(n, recurse=True)
                print(f"[CLEANUP] Removed {len(notes_to_remove)} short artifact notes")

            # ========== NEW: AGGRESSIVE MONOPHONY & LEGATO ==========
            print("[CLEANUP] Enforcing strict monophony (Violin Mode)...")
            
            # 3. STRICT MONOPHONY (Keep Top Line Only)
            for p in s.parts:
                # Iterate measures to handle notes properly
                # We need to flat the stream to sort notes by offset globally for overlapping check
                # But manipulating flat stream is risky. Let's do it per measure or naive overlap check.
                # Safer approach: Iterate all notes, group by offset.
                
                all_notes = list(p.recurse().notes)
                if not all_notes:
                    continue
                    
                # Group by offset
                notes_by_offset = {}
                for n in all_notes:
                    off = n.offset
                    if off not in notes_by_offset:
                        notes_by_offset[off] = []
                    notes_by_offset[off].append(n)
                
                # For each offset, keep only the highest pitch
                for off in sorted(notes_by_offset.keys()):
                    notes_at_off = notes_by_offset[off]
                    if len(notes_at_off) > 1:
                        # Sort by pitch (highest first)
                        # Handle chords vs notes
                        def get_pitch(element):
                            if element.isChord:
                                return max(p.ps for p in element.pitches)
                            return element.pitch.ps
                            
                        notes_at_off.sort(key=get_pitch, reverse=True)
                        
                        # Keep highest, remove others
                        highest = notes_at_off[0]
                        for n in notes_at_off[1:]:
                            p.remove(n, recurse=True)
            
            # 4. LEGATO FORCE (Fill small gaps)
            # Extend notes to close gaps < 0.25
            for p in s.parts:
                notes = sorted(list(p.recurse().notes), key=lambda x: x.offset)
                for i in range(len(notes) - 1):
                    curr = notes[i]
                    next_n = notes[i+1]
                    curr_end = curr.offset + curr.duration.quarterLength
                    gap = next_n.offset - curr_end
                    
                    if 0 < gap < 0.25:
                        curr.duration.quarterLength += gap
            
            # 5. SIMPLIFY ENHARMONICS
            for n in s.recurse().notes:
                if n.isNote:
                    n.pitch.simplifyEnharmonic(inPlace=True)
            
            print("[CLEANUP] Monophony and Legato applied")
            # ========================================================
            
            # 3. AUTO-DETECT KEY SIGNATURE (Existing)
            try:
                detected_key = s.analyze('key')
                # Insert key signature at the beginning
                for p in s.parts:
                    p.insert(0, key.Key(detected_key.tonic.name, detected_key.mode))
                print(f"[CLEANUP] Detected key: {detected_key}")
            except Exception as e:
                print(f"[CLEANUP] Key detection failed: {e}, using default")
            
            # 4. AUTO-DETECT TIME SIGNATURE
            try:
                detected_time = s.analyze('time')
                # Insert time signature
                for p in s.parts:
                    p.insert(0, meter.TimeSignature(f"{detected_time.numerator}/{detected_time.denominator}"))
                print(f"[CLEANUP] Detected time signature: {detected_time}")
            except Exception as e:
                print(f"[CLEANUP] Time detection failed: {e}, using 4/4")
                for p in s.parts:
                    p.insert(0, meter.TimeSignature('4/4'))

            # 5. FINAL NOTATION CLEANUP
            for p in s.parts:
                p.makeBeams(inPlace=True)
                p.makeTies(inPlace=True)
                p.makeAccidentals(inPlace=True)
            
            print("[CLEANUP] Rigorous cleanup complete")
            # ================================================

            # 4. Write to MusicXML
            s.write('musicxml', fp=str(output_xml_path))
            return output_xml_path
        except Exception as e:
            print(f"Error converting to MusicXML: {e}")
            gc.collect()
            return None

    def _transpose_part_to_violin_range(self, s: stream.Stream) -> stream.Stream:
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

    # Deprecated method kept for compatibility if needed, but logic moved to _transpose_part_to_violin_range
    def _transpose_to_violin_range(self, s):
        return self._transpose_part_to_violin_range(s)

#!/usr/bin/env python3
"""
Fix anchor.mp4 keyframe spacing to prevent freeze
Re-encodes with keyframe every 0.5 seconds
"""

import subprocess
import os

def run_command(cmd):
    """Run shell command"""
    cmd_str = ' '.join(cmd)
    print(f"Running: {cmd_str}")
    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed: {result.stderr}")
    return result.stdout

def main():
    input_file = 'assets/anchor.mp4'
    output_file = 'assets/anchor_fixed.mp4'
    
    if not os.path.exists(input_file):
        print(f"❌ {input_file} not found!")
        return
    
    print(f"🔧 Fixing keyframe spacing in {input_file}...")
    print(f"   Adding keyframe every 0.5 seconds (no freeze!)\n")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'fast',
        '-g', '15',              # GOP size 15 (keyframe every 0.5s @ 30fps)
        '-keyint_min', '15',     # Minimum keyframe interval
        '-sc_threshold', '0',    # Disable scene detection
        '-c:a', 'copy',          # Copy audio (no re-encode needed)
        '-y',
        output_file
    ]
    
    run_command(cmd)
    
    # Replace original
    print(f"\n✅ Fixed! Replacing original file...")
    os.remove(input_file)
    os.rename(output_file, input_file)
    
    print(f"✅ {input_file} now has frequent keyframes!")
    print(f"   Videos will play instantly without freeze! 🎉\n")

if __name__ == '__main__':
    main()

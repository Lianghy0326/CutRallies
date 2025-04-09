import os
import subprocess
import pandas as pd
import argparse
from pathlib import Path
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import logging
import hashlib
import json


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("video_cutting.log")
    ]
)

logger = logging.getLogger(__name__)

def create_directory(directory):
    """ Create a directory if it doesn't exist."""
    os.makedirs(directory, exist_ok=True)
    
def get_video_hash(input_video, start_time, end_time):
    """Generate a hash for a video segment based on its path and cut times for video cutting."""
    hash_input = f"{input_video}_{start_time}_{end_time}"
    # hashlib.md5() returns  an Md5 hash object, and hexdigest() converts it to a 32-charactory hexadecimal string.
    return hashlib.md5(hash_input.encode()).hexdigest()

def laod_processed_videos(cache_file): # e.g. "processed_videos.json"
    """ Load the list of already processed videos from cache file"""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache file: {e}")
            return {}
    return {}


def save_processed_videos(processed_videos, cache_file):
    """ Save the list of processed videos to cache file"""
    try:
        with open(cache_file, 'w') as f:
            json.dump(processed_videos, f)
    except Exception as e:
        logger.error(f"Error saving cache file: {e}")
        
def cut_video(input_video, output_path, start_time, end_time):
    """ Cut a video segment using ffmpeg."""
    cmd = [
        'ffmpeg',
        '-loglevel', 'error',  # Reduce ffmpeg output verbosity
        '-i', input_video,
        '-ss', start_time,  # Start time
        '-to', end_time,    # End time
        '-c:v', 'libx264',  # Video codec
        '-preset', 'fast',  # Encoding speed/quality balance
        '-crf', '22',       # Quality (lower = better)
        '-c:a', 'aac',      # Audio codec
        '-b:a', '128k',     # Audio bitrate
        '-y',               # Overwrite output without asking
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f"Successfully cut video: {input_video} from {start_time} to {end_time}")
        return True, output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Error cutting video {input_video} from {start_time} to {end_time}: {e}")
        return False, output_path
    
def process_video_task(task):
    """Process a single video cutting task."""
    input_video, output_path, start_time, end_time, rally_num, view, task_hash = task
    
    # Check if the output file already exists and has a reasonable size
    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:  # 10KB min size
        logger.info(f"Skipping existing file: {output_path}")
        return True, output_path, task_hash
    
    logger.info(f"Processing Rally {rally_num}, View {view}: {start_time} to {end_time}")
    success, output_path = cut_video(input_video, output_path, start_time, end_time)
    return success, output_path, task_hash


def find_video_directories(base_dir):
    """Find all directories containing mp4 files and rally_labels.csv."""
    result = []
    for root, dirs, files in os.walk(base_dir):
        # Check if the directory contains mp4 files and a rally_labels.csv file
        if 'rally_labels.csv' in files and any(f.endswith('.mp4') for f in files):
            result.append(root)
    return result


def process_videos_parallel(video_dirs, output_dir, max_workers=None, cache_file="processed_videos.json"):
    """Process videos in parallel from multiple directories according to rally labels."""
    # Load the list of processed videos
    processed_videos = laod_processed_videos(cache_file)
    
    # Create a list of all tasks
    all_tasks = []
    
    # Process each video directory
    for video_dir in video_dirs:
        # Get directory name for video names
        dir_name = os.path.basename(video_dir)  
        video_name = f"{dir_name}"
        
        # Path to the csv file in this directory
        csv_file = os.path.join(video_dir, 'rally_labels.csv')
        
        if not os.path.exists(csv_file):
            logger.error(f"CSV file not found: {csv_file}")
            continue
        
        # Read the csv file 
        df = pd.read_csv(csv_file)
        
        video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
        video_files.sort(key=lambda x:int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else x )
        
        if not video_files:
            logger.error(f"No video files found in directory: {video_dir}")
            continue
        
        logger.info(f"Found {len(video_files)} video files in {video_dir}")
        logger.info(f"Found {len(df)} rallies in {csv_file}")
        
        # Prepare tasks for this directory
        for _, row in df.iterrows():
            rally_num = row['Rally Number']
            start_time = row['Start Time']
            end_time = row['End Time']
            
            # Frame number
            start_frame = row['Start Frame']
            end_frame = row['End Frame']
            
            for video_file in video_files:
                view = os.path.splitext(video_file)[0]
                
                input_video = os.path.join(video_dir, video_file)
                
                # Create output directory
                rally_dir = os.path.join(output_dir, f"rally{rally_num}", f"view{view}")
                create_directory(rally_dir)
                
                # Create output filename with frame numbers
                output_filename = f"{video_name}_{rally_num}_{start_frame}_{end_frame}_view{view}.mp4"
                output_path = os.path.join(rally_dir, output_filename)
                
                # Generate hash for this task
                task_hash = get_video_hash(input_video, start_time, end_time)
                
                # Skip if already processed successfully
                if task_hash in processed_videos:
                    logger.info(f"Skipping already processed task: {task_hash}")
                    continue
                
                # Add task to the list
                all_tasks.append((input_video, output_path, start_time, end_time, rally_num, view, task_hash))
        if not all_tasks:
            logger.info(f"No new videos to process.")
            return 0,9
        
        # Number of workers
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), len(all_tasks))
        
        # Execute tasks in parallel
        successful = 0
        failed = 0
        start_time = time.time()
        
        logger.info(f"Start parallel processing with {max_workers} workers for {len(all_tasks)} tasks.")
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(process_video_task, task): task for task in all_tasks}
            
            # Process each future as it completes
            for future in as_completed(future_to_task): # A function that yields futures as they complete (finish processing) *Yields in the order thay complete*
                try:
                    success, output_path, task_hash = future.result()
                    if success:
                        successful += 1
                        # Mark task as processed -> Each video has one task hash , put the task hash in the processed_videos dictionary and save as json file. (Inorder to check if the video is already processed)
                        processed_videos[task_hash] = output_path
                    else:
                        failed += 1
                        print(f"Warning: Failed to cut video for task: {task_hash}")
                        
                    # Log process
                    total_completed = successful + failed
                    progress = (total_completed / len(all_tasks)) * 100
                    elapsed = time.time() - start_time
                    estimated_total = elapsed / (total_completed if total_completed >0 else 1) * len(all_tasks)
                    remaining = estimated_total - elapsed
                    
                    logger.info(f"Progress: {progress:.1f}% ({total_completed}/{len(all_tasks)}) - " +
                           f"Success: {successful}, Failed: {failed} - " +
                           f"Time remaining: {remaining/60:.1f} minutes")
                except Exception as e:
                    logger.error(f"Error processing task: {e}")
                    failed += 1
                    
    # Final save of processed videos
    save_processed_videos(processed_videos, cache_file)
    
    # Summary 
    elapsed = time.time() - start_time
    logger.info(f"Processing completed in {elapsed/60:.2f} minutes")
    logger.info(f"Successfully processed: {successful}/{len(all_tasks)} videos")
    logger.info(f"Failed: {failed}/{len(all_tasks)} videos")
    
    return successful, failed       

def main():
    parser = argparse.ArgumentParser(description="Cut videos based on rally labels.")
    parser.add_argument("--base_dir", required=True, help="Base directory containing source video directories")
    parser.add_argument("--output_dir", required=True, help="Directory to save output videos")
    parser.add_argument("--workers", type=int, default=16, 
                        help="Maximum number of worker processes (default: number of CPU cores)")
    parser.add_argument("--cache_file", default="processed_videos.json",
                        help="File to store information about processed videos")
    
    args = parser.parse_args()
    
    # Find all directories with videos and rally_labels.csv
    video_dirs = find_video_directories(args.base_dir)
    
    if not video_dirs:
        logger.error("No video directories found.")
        return
    
    logger.info(f"Found {len(video_dirs)} video directories.")
    for vdir in video_dirs:
        logger.info(f"  - {vdir}")
        
    # Ensure output directory exists
    create_directory(args.output_dir)
    
    # Process videos in parallel
    process_videos_parallel(video_dirs, args.output_dir, args.workers, args.cache_file)
    
if __name__ == "__main__":
    main()
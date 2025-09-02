#!/bin/bash

# Check if the script received the correct number of arguments
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <new_folder_name>"
    exit 1
fi

# Create the new folder using the argument provided
NEW_FOLDER=$1
mkdir -p "$NEW_FOLDER"

# Move the directories to the new folder
mv ./data/cam0 "$NEW_FOLDER/"
mv ./data/cam1 "$NEW_FOLDER/"
mv ./data/imu "$NEW_FOLDER/"
mv ./data/cam0.csv "$NEW_FOLDER/"
mv ./data/cam1.csv "$NEW_FOLDER/"


# Recreate the ./data and ./data/cam/ directories
mkdir -p ./data/cam0
mkdir -p ./data/cam1
mkdir -p ./data/imu

echo "Directories moved and structure recreated successfully."

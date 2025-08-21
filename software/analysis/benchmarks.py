import os
import numpy as np
import pandas as pd
import copy
import tools
from collections import Counter

from evo.tools import file_interface

class XREVA:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.benchmark = "XREVA"
        self.scriptTemplate = "{}/Examples/Stereo-Inertial/stereo_inertial_customized {}/Vocabulary/ORBvoc.txt {}/Examples/Stereo-Inertial/stereo_inertial_customized.yaml {}/Datasets/{}/{}/ {}/Datasets/{}/{}/sensor/timestamp.txt"

        self.trajectories = [
            'S1_Side_Featurerich_75',      'S2_Inspect_Featureless_50',
            'S2_Inspect_Featureless_75',   'S2_Inspect_Featurerich_50',
            'S1_Inspect_Featureless_50',   'S2_Inspect_Featurerich_75',
            'S1_Inspect_Featureless_75',   'S2_Petrol_Featureless_50',
            'S1_Inspect_Featurerich_50',   'S2_Petrol_Featureless_75',
            'S1_Inspect_Featurerich_75',   'S2_Petrol_Featurerich_50',
            'S1_Petrol_Featureless_50',    'S2_Petrol_Featurerich_75',
            'S1_Petrol_Featureless_75',    'S2_Rotation_Featureless_50',
            'S1_Petrol_Featurerich_50',    'S2_Rotation_Featureless_75',
            'S1_Petrol_Featurerich_75',    'S2_Rotation_Featurerich_50',
            'S1_Rotation_Featureless_50',  'S2_Rotation_Featurerich_75',
            'S1_Rotation_Featureless_75',  'S2_Side_Featureless_50',
            'S1_Rotation_Featurerich_50',  'S2_Side_Featureless_75',
            'S1_Rotation_Featurerich_75',  'S2_Side_Featurerich_50',
            'S1_Side_Featureless_50',      'S2_Side_Featurerich_75',
            'S1_Side_Featureless_75',      'S1_Side_Featurerich_50'
        ]

        self.S1_trajectories = [item for item in self.trajectories if not item.startswith('S2_')]
        self.S2_trajectories = [item for item in self.trajectories if not item.startswith('S1_')]


        self.trails = ["data0"]

        # Get this matrix from the extrinsics calibration for Intel RealSense
        self.localTransformMatrix = np.array(
            [[ 1.   ,  0.   ,  0.   , -0.064],
            [ 0.   ,  1.   ,  0.   ,  0.044],
            [ 0.   ,  0.   ,  1.   ,  0.056],
            [ 0.   ,  0.   ,  0.   ,  1.   ]])
        
        self.scriptList = []

        self.traj_gt = None
        self.traj_est = None


    def find_todo_trajectories(self):
        todo_trajectories = []
        # Walk through the dataset directory
        for root, dirs, files in os.walk(self.root_dir):
            # Check if we are in a trial folder (set1 or set2)
            if os.path.basename(root) in ['set1', 'set2']:
                # Check if 'orb_combined.csv' is missing
                if 'orb_combined.csv' not in files:
                    todo_trajectories.append(os.path.dirname(root).split('/')[-1])
        
        if len(todo_trajectories) == 0:
            print("All trials have been processed.")
            return None
        else:
            counter = Counter(todo_trajectories)
            all_missing_trajs = []
            # Print the counts of each unique trajectory
            print("The following trial folders are missing 'orb_combined.csv':")
            for path, count in counter.items():
                print(f"{path}: {count} times")
                if count > 1:
                    all_missing_trajs.append(path)
            return all_missing_trajs
        

    # Step 1: Generate the script for each trajectory and trial
    def generate_script(self, Set="S1"):
        self.scriptList = []
        if Set == "S1":
            trajs = self.S1_trajectories
            print("Debug: trajs:", Set)
        elif Set == "S2":
            print("Debug: trajs:", Set)
            trajs = self.S2_trajectories
        for i, trajectory in enumerate(trajs):
            for j, trial in enumerate(self.trails):
                scriptDict = {}
                scriptDict["benchmark"] = self.benchmark
                scriptDict["trajectory"] = trajectory
                scriptDict["trial"] = trial
                scriptTemp = copy.deepcopy(self.scriptTemplate)
                scriptTemp = scriptTemp.format(self.root_dir, self.root_dir, self.root_dir, \
                                               self.root_dir, trajectory, trial, \
                                               self.root_dir, trajectory, trial)
                scriptDict["script"] = scriptTemp
                self.scriptList.append(scriptDict)

    def get_script(self):
        return self.scriptList
    
    def find_csv_with_prefix(self, folder_path, prefix):
        # Loop through all files in the directory
        for file_name in os.listdir(folder_path):
            # Check if the file name starts with the given prefix and has a .csv extension
            if file_name.startswith(prefix) and file_name.endswith('.csv'):
                # Return the full path of the matching file
                return os.path.join(folder_path, file_name)
        # Return None if no matching file is found
        return None
    

    # Step 2: Copy the ground truth trajectory
    def copy_ground_truth_traj(self, trajectory, trial):
        gt_csv_folder_path = "{}/Datasets/{}/{}/gt/"
        gt_csv_folder_path = gt_csv_folder_path.format(self.root_dir, trajectory, trial)
        # The ORBSLAM3 share the groundtruth with the AppleVisionPro
        gt_csv_path = self.find_csv_with_prefix(gt_csv_folder_path, "AppleVisionPro")
        
        self.traj_gt = file_interface.read_tum_trajectory_file(gt_csv_path)
        # perform the local transformation
        self.traj_gt.transform(t=self.localTransformMatrix, right_mul=True, propagate=False)
        # Save the transformed trajectory under the gt csv folder
        file_interface.write_tum_trajectory_file(
            file_path=gt_csv_folder_path + "gt_ORB.csv",
            traj=self.traj_gt
        )

    # Step 3: Copy the raw SLAM data    
    def process_raw_SLAM_data(self, benchmark,trajectory,trial):
        # Step 1: Read, adjust, and save the CSV log file
        raw_data_path = "{}/logs/log.csv".format(self.root_dir)
        # load the raw data from the raw data path into dataframe
        df_raw = pd.read_csv(raw_data_path,index_col=False)
        orb_last_timestamp = df_raw["TimeStamp"].iloc[-1]
        offset = self.traj_gt.timestamps[-1] - orb_last_timestamp
        # Adjust the timestamps
        df_raw["TimeStamp"] += offset
        #Drop the rows of initialization
        target = 2
        df_raw = df_raw[df_raw['TrackMode'] == 2].reset_index(drop=True)


        gt_first_timestamp = self.traj_gt.timestamps[0]
        # Drop rows with timestamps less than the first timestamp of the ground truth
        df_raw = df_raw[df_raw["TimeStamp"] >= gt_first_timestamp]

        # Save the adjusted dataframe to a new CSV file
        destination_folder_path = "{}/Datasets/{}/{}/xr/".format(self.root_dir, trajectory, trial)
        new_filename = "ORB_log.csv"
        df_raw.to_csv(destination_folder_path + new_filename, index=False)

        # Step 3: Select traj columns
        df_traj = copy.deepcopy(df_raw)
        selected_columns = ["TimeStamp","PX","PY","PZ","QX","QY","QZ","QW"]  # Replace with your desired column names
        df_traj = df_traj[selected_columns]

        # Step 4: Save the traj
        new_filename = "ORB_traj.csv"
        df_traj.to_csv(destination_folder_path+new_filename, sep=' ', index=False, header=False)  
        # You can change the separator as needed
        return df_raw, df_traj#, initial_rows

    def load_raw_SLAM_data(self, benchmark, trajectory, trial):
        # Load the ORB_log.csv file and the ORB_traj.csv file and return dataframes
        raw_data_path = "{}/Datasets/{}/{}/xr/ORB_log.csv"
        raw_data_path = raw_data_path.format(self.root_dir, trajectory, trial)
        #print("Debug: raw_data_path:", raw_data_path)
        # Load the raw data from the raw data path into dataframe
        df_raw = pd.read_csv(raw_data_path,index_col=False)
        #print("Debug: df_raw:", df_raw)
        #raw_data_path = "{}/Datasets/{}/{}/xr/ORB_traj.csv"
        traj_data_path = "{}/Datasets/{}/{}/xr/ORB_traj.csv"
        traj_data_path = traj_data_path.format(self.root_dir, trajectory, trial)
        #print("Debug: traj_data_path:", traj_data_path)
        # Load the raw data from the raw data path into dataframe
        df_traj = pd.read_csv(traj_data_path,index_col=False, sep=' ')
        #print("Debug: df_traj:", df_traj)
        # Return
        return df_raw, df_traj


benchmark_factory = {
    "XREVA": XREVA,
}

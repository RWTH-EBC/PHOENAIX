# PHOENAIX
PHOENAIX is a framework designed to enable the seamless integration of simulation models, prediction algorithms, and optimization routines through standardized data communication protocols. This platform-centric approach allows for the modular deployment of various energy system components and their operating strategies, while maintaining system-wide interoperability. The flexible architecture of the framework not only supports the integration of various simulation tools, but also enables the gradual transition from simulated to real components, making it particularly valuable for the planning and operational phases of urban energy systems.
**⚠️ Important: This repository uses Git LFS**

This project tracks large data files using Git Large File Storage (LFS). To clone and work with this repository correctly, you must have the Git LFS client installed on your machine.

1.  **Install Git LFS:**
    Download and install it from the [official website](https://git-lfs.github.com/).

2.  **Initialize LFS for your user account (only needs to be done once):**
    ```bash
    git lfs install
    ```

After completing these steps, you can clone the repository as usual, and the large files will be downloaded correctly.

## Components
1. Optimizer for a building neighborhood
2. Simulation model of a building neighborhoods model as an FMU
3. Communication interface for FIWARE

## Roadmaps
1. Set up the devices in a building neighborhood
2. Adjust the optimizer to the devices
3. Set up the data model on FIWARE
4. Create the interface between the simulation model and FIWARE
5. Create the interface between the optimizer and FIWARE

## Folder structure
data/: This folder contains all the input data, output data, and processed data that will be used by the project.\
phoenaix/: This folder contains all the core logic of the project, such as algorithms, models, and utility functions.\
examples/: This folder contains all the scripts that will be used to run the project.\
tests/: This folder contains all the test cases for the core logic of the project.\
